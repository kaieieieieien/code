"""
player.py - Kai Player Ver.33 (強化優先ロジック適用)
"""
from tcg.controller import Controller
from .strategy import Strategy
import os

class Kai4Player(Controller):
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
            f.write("=== Game Start (Ver.33 Economy First) ===\n")

    def team_name(self) -> str:
        return f"Kai{self.mode}"

    def log(self, message):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")

    def update(self, info) -> tuple[int, int, int]:
        self.step_count += 1
        team, state, pawn, SpawnPoint, done = info
        my_team = team
        enemy_team = 2 if team == 1 else 1

        self.write_step_log(state, pawn, SpawnPoint, my_team, enemy_team)

        # === 0. モード切替 ===
        if self.mode == "MIRROR":
            my_forts = len([i for i in range(12) if state[i][0] == my_team])
            en_forts = len([i for i in range(12) if state[i][0] == enemy_team])
            
            if my_forts < en_forts:
                self.mode = "ADAPTIVE"
                self.log(f"[SWITCH] 砦数劣勢: MIRROR -> ADAPTIVE")
            
            if self.mirror_failure_count > 10:
                self.mode = "ADAPTIVE"
                self.log(f"[SWITCH] ミラー失敗多数: MIRROR -> ADAPTIVE")

        # === 1. 検知 (MIRROR) ===
        current_enemy_spawns = [p for p in SpawnPoint if p[0] == enemy_team]
        for sp in current_enemy_spawns:
            sp_id = id(sp)
            if sp_id not in self.seen_spawn_ids:
                self.seen_spawn_ids.add(sp_id)
                e_from, e_to = sp[3], sp[4]
                m_src = self.strategy.get_mirror_id(e_from)
                m_dst = self.strategy.get_mirror_id(e_to)
                
                if self.mode == "MIRROR":
                    self.action_queue.append({
                        "type": "MOVE", "src": m_src, "dst": m_dst,
                        "expire": self.step_count + 100
                    })
                    self.log(f"[DETECT] 敵移動 {e_from}->{e_to} | 予約 {m_src}->{m_dst}")

        for fid in range(12):
            if state[fid][0] == enemy_team:
                curr = state[fid][4]
                prev = self.prev_enemy_upgrade_timers.get(fid, -1)
                if prev == -1 and curr > 0:
                    m_src = self.strategy.get_mirror_id(fid)
                    if self.mode == "MIRROR":
                        self.action_queue.append({
                            "type": "UPGRADE", "src": m_src, "dst": 0,
                            "expire": self.step_count + 300
                        })
                        self.log(f"[DETECT] 敵強化 {fid} | 予約 {m_src}")
                self.prev_enemy_upgrade_timers[fid] = curr

        # === 2. 実行 ===
        if self.mode == "MIRROR":
            if self.action_queue and self.action_queue[0]["expire"] < self.step_count:
                self.action_queue.pop(0)
                self.mirror_failure_count += 1

            for i, action in enumerate(self.action_queue):
                src = action["src"]
                dst = action["dst"]
                if state[src][0] != my_team: continue

                if action["type"] == "MOVE":
                    if state[src][3] >= 1:
                        self.action_queue.pop(i)
                        self.log(f"[EXEC-MIRROR] 移動 {src}->{dst}")
                        return 1, src, dst
                elif action["type"] == "UPGRADE":
                    if self.strategy.can_upgrade(state[src]):
                        self.action_queue.pop(i)
                        self.log(f"[EXEC-MIRROR] 強化 {src}")
                        return 2, src, 0
                if i >= 3: break
            
            # 暇ならレベル同期
            for fid in range(12):
                if state[fid][0] == enemy_team:
                    m_src = self.strategy.get_mirror_id(fid)
                    if state[m_src][0] == my_team:
                        if state[m_src][2] < state[fid][2] and self.strategy.can_upgrade(state[m_src]):
                             self.log(f"[AUTO-SYNC] レベル同期 {m_src}")
                             return 2, m_src, 0

        else: # ADAPTIVE
            self.action_queue = []
            
            # 1. 強化 (最優先)
            cmd, src, dst = self.strategy.get_upgrade_move(state, my_team, enemy_team)
            if cmd != 0:
                self.log(f"[ADAPTIVE] 強化 {src}")
                return cmd, src, dst

            # 2. 移動
            cmd, src, dst = self.strategy.get_adaptive_move(state, my_team, enemy_team)
            if cmd != 0:
                self.log(f"[ADAPTIVE] 行動 {src}->{dst}")
                return cmd, src, dst

        return 0, 0, 0

    def write_step_log(self, state, pawn, SpawnPoint, my_team, enemy_team):
        my_s = sum(int(s[3]) for s in state if s[0] == my_team) + \
               len([p for p in pawn if p[0] == my_team])
        en_s = sum(int(s[3]) for s in state if s[0] == enemy_team) + \
               len([p for p in pawn if p[0] == enemy_team])
        
        if self.step_count % 10 == 0:
            print(f"Step {self.step_count:5d} [{self.mode[0]}] | 自: {my_s} vs 敵: {en_s}")

        fort_str = ""
        for i in range(12):
            owner = "M" if state[i][0] == my_team else ("E" if state[i][0] == enemy_team else "N")
            fort_str += f"{i}:{owner}L{state[i][2]}P{int(state[i][3])} "
        self.log(f"STEP:{self.step_count} MODE:{self.mode} MY:{my_s} EN:{en_s} | {fort_str}")
