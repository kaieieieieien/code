"""
player.py - Kai Player Ver.53 (Hive Mind / 全体意思)
"""
from tcg.controller import Controller
from .strategy import Strategy
import os

class Kai5Player(Controller):
    def __init__(self):
        super().__init__()
        self.strategy = Strategy()
        self.step_count = 0
        self.seen_spawn_ids = set()
        self.action_queue = []
        self.prev_enemy_upgrade_timers = {}
        
        self.mode = "MIRROR" 

        self.log_file = "game_log_full.txt"
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("=== Game Start (Ver.53 Hive Mind) ===\n")

    def team_name(self) -> str:
        return "KaiHiveMind"

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

        if self.step_count % 10 == 0:
            my_s = sum(int(s[3]) for s in state if s[0] == my_team)
            en_s = sum(int(s[3]) for s in state if s[0] == enemy_team)
            print(f"Step {self.step_count:5d} [{self.mode[0]}] | 自: {my_s} vs 敵: {en_s}")

        # === 0. モード切替 ===
        if self.mode == "MIRROR":
            my_forts = len([i for i in range(12) if state[i][0] == my_team])
            en_forts = len([i for i in range(12) if state[i][0] == enemy_team])
            # 砦数で2つ以上差がついたら解除
            if my_forts <= en_forts - 2:
                self.mode = "ADAPTIVE"
                self.log(f"[SWITCH] 砦数大差(2差以上): MIRROR -> ADAPTIVE")

        # === 1. ミラー予約 (経済のみ) ===
        if self.mode == "MIRROR":
            # 敵の「拡張(中立への攻撃)」と「強化」だけをミラーする
            # (戦闘移動はミラーしない)
            
            # 拡張検知
            current_enemy_spawns = [p for p in SpawnPoint if p[0] == enemy_team]
            for sp in current_enemy_spawns:
                sp_id = id(sp)
                if sp_id not in self.seen_spawn_ids:
                    self.seen_spawn_ids.add(sp_id)
                    e_from, e_to = sp[3], sp[4]
                    
                    # 行き先が中立なら真似する
                    if state[e_to][0] == 0:
                        m_src = self.strategy.get_mirror_id(e_from)
                        m_dst = self.strategy.get_mirror_id(e_to)
                        self.action_queue.append({
                            "type": "MOVE", "src": m_src, "dst": m_dst,
                            "expire": self.step_count + 500
                        })
                        self.log(f"[DETECT-EXPAND] 敵拡張: {e_from}->{e_to} | 予約: {m_src}->{m_dst}")

            # 強化検知
            for fid in range(12):
                if state[fid][0] == enemy_team:
                    curr = state[fid][4]
                    prev = self.prev_enemy_upgrade_timers.get(fid, -1)
                    if prev == -1 and curr > 0:
                        m_src = self.strategy.get_mirror_id(fid)
                        self.action_queue.insert(0, {
                            "type": "UPGRADE", "src": m_src, "dst": 0,
                            "expire": self.step_count + 500
                        })
                        self.log(f"[DETECT-UPGRADE] 敵強化: {fid} | 予約: {m_src}")
                    self.prev_enemy_upgrade_timers[fid] = curr

        # === 2. 行動実行 ===
        
        # (A) ハイブマインド攻撃 (全体意思による集中攻撃)
        cmd, src, dst = self.strategy.get_hive_mind_move(state, pawn, my_team, enemy_team)
        if cmd != 0:
            self.log(f"[HIVE] 集中攻撃/輸送: {src} -> {dst}")
            return cmd, src, dst

        # (B) ミラー実行 (経済のみ)
        if self.mode == "MIRROR":
            if self.action_queue and self.action_queue[0]["expire"] < self.step_count:
                self.action_queue.pop(0)

            for i, action in enumerate(self.action_queue):
                src = action["src"]
                dst = action["dst"]
                if state[src][0] != my_team: continue

                if action["type"] == "MOVE":
                    if state[src][3] >= 1:
                        self.action_queue.pop(i)
                        self.log(f"[EXEC-MIRROR] 拡張: {src}->{dst}")
                        return 1, src, dst
                    else:
                        return 0, 0, 0 

                elif action["type"] == "UPGRADE":
                    if self.strategy.can_upgrade(state[src]):
                        self.action_queue.pop(i)
                        self.log(f"[EXEC-MIRROR] 強化: {src}")
                        return 2, src, 0
                    else:
                        return 0, 0, 0
                
                if i >= 0: break

        # (C) 強化 (独自判断)
        if not self.action_queue:
            cmd, src, dst = self.strategy.get_upgrade_move(state, my_team, enemy_team)
            if cmd != 0:
                self.log(f"[ADAPTIVE] 強化: {src}")
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
            msg += f"{i:2d} | {owner:3s} | {s[2]}  | {s[3]:4.1f}\n"
        self.log(msg)
