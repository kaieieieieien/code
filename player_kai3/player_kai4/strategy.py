"""
strategy.py - Kai Player Ver.34 (拡張・侵略ロジック修正版)
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

    def get_upgrade_move(self, state, my_team, enemy_team) -> tuple[int, int, int]:
        """ADAPTIVEモード時の強化判断"""
        my_forts = [i for i in range(12) if state[i][0] == my_team]
        for fid in my_forts:
            if not self.can_upgrade(state[fid]): continue
            
            f = state[fid]
            # 周囲に敵がいるか確認
            has_enemy_neighbor = False
            enemy_threat = 0
            for nid in f[5]:
                if state[nid][0] == enemy_team:
                    has_enemy_neighbor = True
                    enemy_threat += state[nid][3]
            
            # Lv3以下なら、敵がいようが強化を優先する (生産力確保)
            if f[2] < 3:
                return 2, fid, 0
            
            # 敵がいないなら強化
            if not has_enemy_neighbor:
                return 2, fid, 0
            
            # 敵がいても、脅威が少なければ強化
            if enemy_threat < f[3]:
                return 2, fid, 0
                
        return 0, 0, 0

    def get_adaptive_move(self, state, my_team, enemy_team) -> tuple[int, int, int]:
        """ADAPTIVEモード時の移動判断 (拡張優先)"""
        dist_map = self.calculate_distance(state, enemy_team)
        neutral_dist_map = self.calculate_distance(state, 0)

        my_forts = [i for i in range(12) if state[i][0] == my_team]
        best_cmd = (0, 0, 0)
        best_score = -9999

        for fid in my_forts:
            if state[fid][3] < 1: continue

            # --- 安全在庫の計算 ---
            has_enemy_neighbor = False
            for nid in state[fid][5]:
                if state[nid][0] == enemy_team:
                    has_enemy_neighbor = True
                    break
            
            # 敵が隣にいる時だけ兵を残す。いなければゼロでOK（拡張優先）
            safety_margin = 0
            if has_enemy_neighbor:
                safety_margin = HARD_LIMITS[state[fid][2]] * 0.4 # 40%残す

            # 攻撃可能兵力
            available_pawns = state[fid][3] - safety_margin
            if available_pawns < 2: continue # 最低2体いないと移動で1にならない
            
            attack_power = available_pawns // 2

            my_dist = dist_map[fid]

            for nid in state[fid][5]:
                n_state = state[nid]
                score = -9999

                # 1. 敵への攻撃 (勝てる時だけ)
                if n_state[0] == enemy_team:
                    if attack_power > n_state[3] * 1.1:
                        score = 1000 + (100 - n_state[3])
                
                # 2. 中立への攻撃 (最優先拡張)
                elif n_state[0] == 0:
                    # 【修正】中立は +1 でも勝てれば取る！
                    if attack_power > n_state[3] + 1:
                        # 敵に近い中立ほど価値が高い
                        score = 2000 - (n_state[3] * 10) - (dist_map[nid] * 100)
                
                # 3. 味方への輸送
                elif n_state[0] == my_team:
                    # 敵に近い方へ
                    if dist_map[nid] < my_dist:
                        limit = HARD_LIMITS[n_state[2]]
                        # 相手が溢れていないなら
                        if n_state[3] < limit * 0.9:
                            score = 100 + (10 - dist_map[nid])
                    
                    # 敵がいないなら中立に近い方へ (拡張支援)
                    elif my_dist > 10 and neutral_dist_map[nid] < neutral_dist_map[fid]:
                         score = 50

                if score > best_score:
                    best_score = score
                    best_cmd = (1, fid, nid)

        if best_score > 0:
            return best_cmd
            
        return 0, 0, 0
