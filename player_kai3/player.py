"""
player.py - Kai Player Ver.Hybrid (後方は鏡、前線は鬼)
"""
from tcg.controller import Controller
from .strategy import Strategy

class Kai3Player(Controller):
    def __init__(self):
        super().__init__()
        self.strategy = Strategy()
        self.step_count = 0
        
        self.seen_spawn_ids = set()
        self.prev_enemy_upgrade_timers = {}
        self.action_queue = []
        
        # ログ設定 (今回は軽量化のためコンソールのみ)
        self.log_file = "game_log.txt"
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("=== Game Start (Hybrid Ver) ===\n")

    def team_name(self) -> str:
        return "KaiHybrid"

    def log_to_file(self, message):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")

    def update(self, info) -> tuple[int, int, int]:
        self.step_count += 1
        team, state, pawn, SpawnPoint, done = info
        
        my_team = team
        enemy_team = 2 if team == 1 else 1

        # --- リアルタイム兵力表示 ---
        if self.step_count % 10 == 0:
            my_s = sum(int(s[3]) for s in state if s[0] == my_team) + \
                   len([p for p in pawn if p[0] == my_team])
            en_s = sum(int(s[3]) for s in state if s[0] == enemy_team) + \
                   len([p for p in pawn if p[0] == enemy_team])
            print(f"Step {self.step_count:5d} | 自: {my_s} vs 敵: {en_s}")

        # === 1. 敵の行動検知 (ミラーリング用) ===
        # ただし、前線に関する動きは無視する
        
        current_enemy_spawns = [p for p in SpawnPoint if p[0] == enemy_team]
        for sp in current_enemy_spawns:
            sp_id = id(sp)
            if sp_id not in self.seen_spawn_ids:
                self.seen_spawn_ids.add(sp_id)
                
                e_from, e_to = sp[3], sp[4]
                m_src = self.strategy.get_mirror_id(e_from)
                m_dst = self.strategy.get_mirror_id(e_to)
                
                # 【重要】自分が「前線」ならミラー予約しない (自律戦闘に任せる)
                if self.strategy.is_frontline(state, m_src, my_team):
                    self.log_to_file(f"[IGNORE] ID:{m_src}は前線のためミラー拒否")
                    continue

                # 重複チェック
                if self.action_queue:
                    last = self.action_queue[-1]
                    if last["type"] == "MOVE" and last["src"] == m_src and last["dst"] == m_dst:
                        continue

                self.action_queue.append({
                    "type": "MOVE",
                    "src": m_src,
                    "dst": m_dst,
                    "expire": self.step_count + 50
                })

        # 強化検知 (強化は前線でもミラーして良い場合が多いが、兵士を使うので一応チェック)
        for fid in [i for i in range(12) if state[i][0] == enemy_team]:
            current = state[fid][4]
            prev = self.prev_enemy_upgrade_timers.get(fid, -1)
            if prev == -1 and current > 0:
                m_src = self.strategy.get_mirror_id(fid)
                # 前線でも強化は有効だが、戦闘中なら無視したほうがいいかも？
                # ここでは「余裕があればやる」程度に予約に入れる
                self.action_queue.append({
                    "type": "UPGRADE",
                    "src": m_src,
                    "dst": 0,
                    "expire": self.step_count + 200
                })
            self.prev_enemy_upgrade_timers[fid] = current


        # === 2. 行動実行フェーズ ===

        # (A) 自律戦闘 (前線 & 余剰兵力)
        # ミラー予約より先に、前線の判断を優先させる
        my_fortresses = [i for i in range(12) if state[i][0] == my_team]
        for fid in my_fortresses:
            # 前線、または満タンに近い後方基地
            if self.strategy.is_frontline(state, fid, my_team) or \
               self.strategy.is_overflowing(state, fid):
                
                cmd, src, dst = self.strategy.get_combat_move(state, fid, my_team)
                if cmd != 0:
                    self.log_to_file(f"[COMBAT] 自律行動: {src} -> {dst}")
                    return cmd, src, dst

        # (B) ミラー予約の実行
        # 期限切れ削除
        if self.action_queue:
            if self.action_queue[0]["expire"] < self.step_count:
                self.action_queue.pop(0)

        # 実行
        for i, action in enumerate(self.action_queue):
            src = action["src"]
            dst = action["dst"]
            cmd_type = action["type"]

            if state[src][0] != my_team: continue

            # 前線になっていたら予約破棄 (戦闘優先)
            if self.strategy.is_frontline(state, src, my_team):
                self.action_queue.pop(i)
                return 0, 0, 0

            if cmd_type == "MOVE":
                if state[src][3] >= 1: # 1体でもいれば即ミラー
                    self.action_queue.pop(i)
                    self.log_to_file(f"[MIRROR] 実行: {src} -> {dst}")
                    return 1, src, dst
            elif cmd_type == "UPGRADE":
                if self.strategy.can_upgrade(state[src]):
                    self.action_queue.pop(i)
                    return 2, src, 0
            
            if i >= 3: break # 見すぎない

        return 0, 0, 0