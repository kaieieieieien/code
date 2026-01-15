"""
player.py - Kai Player Ver.40 (ネバネバ・ミラー)
"""
from tcg.controller import Controller
from .strategy import Strategy
import os

class Kai6Player(Controller):
    def __init__(self):
        super().__init__()
        self.strategy = Strategy()
        self.step_count = 0
        self.seen_spawn_ids = set()
        self.action_queue = []
        self.prev_enemy_upgrade_timers = {}
        
        self.mode = "MIRROR" 
        self.mirror_failure_count = 0 

        self.log_file = "game_log_full.txt"
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("=== Game Start (Ver.40 Sticky Mirror) ===\n")

    def team_name(self) -> str:
        return f"KaiSticky"

    def log(self, message):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")

    def update(self, info) -> tuple[int, int, int]:
        self.step_count += 1
        team, state, pawn, SpawnPoint, done = info
        my_team = team
        enemy_team = 2 if team == 1 else 1

        if self.step_count % 50 == 0 or self.step_count < 100:
            self.write_full_log(state, pawn, SpawnPoint, my_team, enemy_team)

        # --- コンソール ---
        if self.step_count % 10 == 0:
            my_s = sum(int(s[3]) for s in state if s[0] == my_team) + \
                   len([p for p in pawn if p[0] == my_team])
            en_s = sum(int(s[3]) for s in state if s[0] == enemy_team) + \
                   len([p for p in pawn if p[0] == enemy_team])
            print(f"Step {self.step_count:5d} [{self.mode[0]}] | 自: {my_s} vs 敵: {en_s}")

        # === 0. モード切替判定 (修正: 超・粘り強く) ===
        if self.mode == "MIRROR":
            my_forts = len([i for i in range(12) if state[i][0] == my_team])
            en_forts = len([i for i in range(12) if state[i][0] == enemy_team])
            
            # 【修正】砦差が2つ開くまではミラー継続！ (1つ差なら誤差)
            if my_forts < en_forts - 1:
                self.mode = "ADAPTIVE"
                self.log(f"[SWITCH] 砦数大差(2つ以上): MIRROR -> ADAPTIVE")
            
            # 失敗カウントによる解除も廃止（遅れてもついていく）
            # if self.mirror_failure_count > 20: ...

        # === 1. 検知 ===
        current_enemy_spawns = [p for p in SpawnPoint if p[0] == enemy_team]
        for sp in current_enemy_spawns:
            sp_id = id(sp)
            if sp_id not in self.seen_spawn_ids:
                self.seen_spawn_ids.add(sp_id)
                e_from, e_to = sp[3], sp[4]
                m_src = self.strategy.get_mirror_id(e_from)
                m_dst = self.strategy.get_mirror_id(e_to)
                
                # 接敵中でもミラーは予約する（実行時に判断）
                if self.mode == "MIRROR":
                    # 期限を大幅延長 (1000ステップ待つ)
                    self.action_queue.append({
                        "type": "MOVE", "src": m_src, "dst": m_dst,
                        "expire": self.step_count + 1000
                    })
                    self.log(f"[DETECT] 敵移動: {e_from}->{e_to} | 予約: {m_src}->{m_dst}")

        for fid in range(12):
            if state[fid][0] == enemy_team:
                curr = state[fid][4]
                prev = self.prev_enemy_upgrade_timers.get(fid, -1)
                if prev == -1 and curr > 0:
                    m_src = self.strategy.get_mirror_id(fid)
                    if self.mode == "MIRROR":
                        self.action_queue.insert(0, {
                            "type": "UPGRADE", "src": m_src, "dst": 0,
                            "expire": self.step_count + 1000
                        })
                        self.log(f"[DETECT] 敵強化: {fid} | 予約: {m_src}")
                self.prev_enemy_upgrade_timers[fid] = curr

        # === 2. 実行 ===
        
        # (A) 緊急戦闘・強化 (最優先)
        # ただし、ミラー中は「本当に危険な時」だけ介入する
        my_fortresses = [i for i in range(12) if state[i][0] == my_team]
        for fid in my_fortresses:
            if self.mode == "ADAPTIVE" or self.strategy.is_critical_danger(state, fid, my_team, enemy_team):
                cmd, src, dst = self.strategy.get_combat_move(state, fid, my_team, enemy_team)
                if cmd != 0:
                    self.log(f"[COMBAT] 戦闘: {src} -> {dst}")
                    return cmd, src, dst

        # (B) バッテリー解放 (ADAPTIVE時のみ)
        if self.mode == "ADAPTIVE":
            cmd, src, dst = self.strategy.get_battery_move(state, my_team, enemy_team)
            if cmd != 0:
                self.log(f"[BATTERY] 放出: {src} -> {dst}")
                return cmd, src, dst

        # (C) ミラー実行 (粘り強く待つ)
        if self.mode == "MIRROR":
            if self.action_queue and self.action_queue[0]["expire"] < self.step_count:
                self.action_queue.pop(0) # さすがに古すぎるのは捨てる

            # 先頭の命令だけを見る (順序厳守)
            if self.action_queue:
                action = self.action_queue[0]
                src = action["src"]
                dst = action["dst"]
                
                # 持っていない砦の命令はスキップして次へ
                if state[src][0] != my_team:
                    self.action_queue.pop(0)
                    self.log(f"[SKIP] 未所持のためスキップ: {src}")
                    return 0, 0, 0

                if action["type"] == "MOVE":
                    if state[src][3] >= 1:
                        self.action_queue.pop(0)
                        self.log(f"[EXEC-MIRROR] 移動: {src}->{dst}")
                        return 1, src, dst
                    # 兵不足なら return 0 で待つ (次のフレームでまたチェック)

                elif action["type"] == "UPGRADE":
                    if self.strategy.can_upgrade(state[src]):
                        self.action_queue.pop(0)
                        self.log(f"[EXEC-MIRROR] 強化: {src}")
                        return 2, src, 0
                    # コスト不足なら待つ

            # 暇ならレベル同期
            for fid in range(12):
                if state[fid][0] == enemy_team:
                    m_src = self.strategy.get_mirror_id(fid)
                    if state[m_src][0] == my_team:
                        if state[m_src][2] < state[fid][2] and self.strategy.can_upgrade(state[m_src]):
                             self.log(f"[AUTO-SYNC] レベル同期: {m_src}")
                             return 2, m_src, 0

        # (D) ADAPTIVE
        else:
            cmd, src, dst = self.strategy.get_adaptive_move(state, my_team, enemy_team)
            if cmd != 0:
                self.log(f"[ADAPTIVE] 拡張: {src} -> {dst}")
                return cmd, src, dst

        return 0, 0, 0

    def write_full_log(self, state, pawn, SpawnPoint, my_team, enemy_team):
        # ログ出力（前回と同じ）
        my_s = sum(int(s[3]) for s in state if s[0] == my_team)
        en_s = sum(int(s[3]) for s in state if s[0] == enemy_team)
        msg = f"\n=== Step {self.step_count} [{self.mode}] (My:{my_s} vs En:{en_s}) ===\n"
        for i in range(12):
            s = state[i]
            owner = "MY" if s[0] == my_team else ("EN" if s[0] == enemy_team else "NU")
            end = "\n" if i % 2 == 1 else "  |  "
            msg += f"ID:{i:2d} [{owner}] Lv:{s[2]} 兵:{s[3]:4.1f}{end}"
        if self.action_queue:
            msg += f"Queue Top: {self.action_queue[0]}\n"
        self.log(msg)
