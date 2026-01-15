"""
strategy.py - Kai Player Ver.40 (危機判定・粘り腰)
"""
from collections import deque

MIRROR_MAP = {
    0: 11, 11: 0, 1: 10, 10: 1, 2: 9,  9: 2,
    3: 8,  8: 3, 4: 7,  7: 4, 5: 6,  6: 5
}
HARD_LIMITS = [10, 10, 20, 30, 40, 50]

class Strategy:
    def __init__(self):
        pass

    def get_mirror_id(self, fortress_id) -> int:
        return MIRROR_MAP.get(fortress_id, 0)

    def can_upgrade(self, f_state) -> bool:
        if f_state[2] >= 5 or f_state[4] > 0: return False
        cost = (HARD_LIMITS[f_state[2] + 1] if f_state[2] < 5 else 50) // 2
        return f_state[3] >= cost

    def is_touching_real_enemy(self, state, fid, my_team, enemy_team) -> bool:
        for nid in state[fid][5]:
            if state[nid][0] == enemy_team:
                return True
        return False
        
    def is_critical_danger(self, state, fid, my_team, enemy_team) -> bool:
        """本当に危険な状態か？ (ミラーを中断してでも守るべきか)"""
        if not self.is_touching_real_enemy(state, fid, my_team, enemy_team):
            return False
        
        my_pawns = state[fid][3]
        enemy_power = 0
        for nid in state[fid][5]:
            if state[nid][0] == enemy_team:
                enemy_power += state[nid][3]
        
        # 敵の総兵力が自分の1.5倍を超えていたら危険
        return enemy_power > my_pawns * 1.5

    def is_overflowing(self, state, fid) -> bool:
        limit = HARD_LIMITS[state[fid][2]]
        return state[fid][3] >= limit * 0.9

    def calculate_distance(self, state, target_team) -> dict:
        distances = {i: 999 for i in range(12)}
        queue = deque()
        for i in range(12):
            if state[i][0] == target_team:
                distances[i] = 0
                queue.append(i)
        while queue:
            curr = queue.popleft()
            for n in state[curr][5]:
                if distances[n] > distances[curr] + 1:
                    distances[n] = distances[curr] + 1
                    queue.append(n)
        return distances

    def get_battery_move(self, state, my_team, enemy_team) -> tuple[int, int, int]:
        # (Ver.39と同じ、限界突破ロジック)
        my_forts = [i for i in range(12) if state[i][0] == my_team]
        for fid in my_forts:
            if self.is_touching_real_enemy(state, fid, my_team, enemy_team): continue
            targets = []
            for nid in state[fid][5]:
                n_state = state[nid]
                if n_state[0] == enemy_team:
                    if (state[fid][3] // 2) > n_state[3] + 5:
                        targets.append((nid, 1000))
                elif n_state[0] == my_team and self.is_touching_real_enemy(state, nid, my_team, enemy_team):
                    limit = HARD_LIMITS[n_state[2]]
                    current = n_state[3]
                    if current < limit * 0.3: targets.append((nid, 600))
                    elif current < limit * 0.9: targets.append((nid, 500))
                    elif current < limit * 10.0: targets.append((nid, 300))
            if targets:
                targets.sort(key=lambda x: x[1], reverse=True)
                if state[fid][3] >= 5: return 1, fid, targets[0][0]
            limit = HARD_LIMITS[state[fid][2]]
            if state[fid][3] > limit * 3.0:
                for nid in state[fid][5]:
                    if self.is_touching_real_enemy(state, nid, my_team, enemy_team):
                        return 1, fid, nid
        return 0, 0, 0

    def get_combat_move(self, state, fid, my_team, enemy_team) -> tuple[int, int, int]:
        # 戦闘ロジック (1.1倍で攻撃)
        my_f = state[fid]
        my_pawns = my_f[3]
        if self.can_upgrade(my_f):
            safe = True
            for nid in my_f[5]:
                if state[nid][0] == enemy_team and state[nid][3] > my_pawns: safe = False
            if safe: return 2, fid, 0
        attack_power = my_pawns // 2
        if attack_power < 1: return 0, 0, 0
        best_target = None
        best_score = -9999
        for nid in my_f[5]:
            n = state[nid]
            score = -9999
            if n[0] == enemy_team:
                if attack_power > n[3] * 1.1: score = 1000
                elif self.is_overflowing(state, fid): score = 500
                else: score = -100 
            elif n[0] == 0:
                if attack_power > n[3] + 2: score = 200
            if score > best_score:
                best_score = score
                best_target = nid
        if best_target and best_score > 0: return 1, fid, best_target
        return 0, 0, 0
    
    def get_adaptive_move(self, state, my_team, enemy_team) -> tuple[int, int, int]:
        # 拡張ロジック (Ver.39と同じ)
        dist_map = self.calculate_distance(state, enemy_team)
        neutral_dist_map = self.calculate_distance(state, 0)
        my_forts = [i for i in range(12) if state[i][0] == my_team]
        for fid in my_forts:
            if state[fid][3] < 2: continue
            curr_dist = dist_map[fid]
            for nid in state[fid][5]:
                if state[nid][0] == 0:
                    if (state[fid][3]//2) > state[nid][3] + 1: return 1, fid, nid
            for nid in state[fid][5]:
                if state[nid][0] == my_team:
                    if dist_map[nid] < curr_dist:
                        t_state = state[nid]
                        limit = HARD_LIMITS[t_state[2]]
                        if t_state[3] < limit * 5.0: return 1, fid, nid
                    elif curr_dist > 10 and neutral_dist_map[nid] < neutral_dist_map[fid]:
                         return 1, fid, nid
        return 0, 0, 0
