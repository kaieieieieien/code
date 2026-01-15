"""
strategy.py - Kai Player Ver.53 (Hive Mind / 全体誘導)
"""
from collections import deque

MIRROR_MAP = {
    0: 11, 11: 0, 1: 10, 10: 1, 2: 9,  9: 2,
    3: 8,  8: 3, 4: 7,  7: 4, 5: 6,  6: 5
}
HARD_LIMITS = [10, 10, 20, 30, 40, 50]

class Strategy:
    def __init__(self):
        self.target_fort = None # 全体目標

    def get_mirror_id(self, fortress_id) -> int:
        return MIRROR_MAP.get(fortress_id, 0)

    def can_upgrade(self, f_state) -> bool:
        if f_state[2] >= 5 or f_state[4] > 0: return False
        cost = (HARD_LIMITS[f_state[2] + 1] if f_state[2] < 5 else 50) // 2
        return f_state[3] >= cost

    def count_enemy_neighbors(self, state, fid, enemy_team) -> int:
        count = 0
        for nid in state[fid][5]:
            if state[nid][0] == enemy_team:
                count += 1
        return count

    def get_hive_mind_move(self, state, pawn, my_team, enemy_team) -> tuple[int, int, int]:
        """
        ハイブマインド: 全体で一つのターゲットを狙い、そこへ向かう最短ルートで兵を送る
        """
        # 1. ターゲットの決定・更新
        self.update_target(state, my_team, enemy_team)
        
        target = self.target_fort
        if target is None: return 0, 0, 0

        # 2. ターゲットへの距離マップ作成 (BFS)
        dist_map = {i: 999 for i in range(12)}
        dist_map[target] = 0
        queue = deque([target])
        
        while queue:
            curr = queue.popleft()
            for n in state[curr][5]:
                if dist_map[n] > dist_map[curr] + 1:
                    dist_map[n] = dist_map[curr] + 1
                    queue.append(n)

        # 3. 全砦の行動決定
        my_forts = [i for i in range(12) if state[i][0] == my_team]
        best_cmd = (0, 0, 0)
        best_priority = -9999

        for fid in my_forts:
            if state[fid][3] < 2: continue # 最低2体
            
            # 自分がターゲットに隣接しているなら攻撃！
            if target in state[fid][5]:
                attack_power = state[fid][3] // 2
                target_power = state[target][3]
                
                # 勝てる、またはターゲットが敵なら削るために攻撃
                score = 10000
                if state[target][0] == enemy_team: score += 500
                if attack_power > target_power * 1.1: score += 1000
                
                if score > best_priority:
                    best_priority = score
                    best_cmd = (1, fid, target)
                continue

            # 隣接していないなら、ターゲットに近づく方向へ輸送 (バケツリレー)
            my_dist = dist_map[fid]
            for nid in state[fid][5]:
                if state[nid][0] == my_team:
                    if dist_map[nid] < my_dist:
                        # 輸送スコア (距離が縮まるなら高評価)
                        priority = 5000 + (20 - dist_map[nid]) * 100
                        
                        # 溢れ防止 (ただしターゲットへ向かうルートは太くする)
                        limit = HARD_LIMITS[state[nid][2]]
                        if state[nid][3] > limit * 2.0:
                            priority -= 2000 
                        
                        if priority > best_priority:
                            best_priority = priority
                            best_cmd = (1, fid, nid)

        if best_priority > 0:
            return best_cmd
        return 0, 0, 0

    def update_target(self, state, my_team, enemy_team):
        """最適なターゲットを選定"""
        # 既にターゲットがあり、まだ自分のものになっていないなら維持
        if self.target_fort is not None:
            if state[self.target_fort][0] != my_team:
                return
            else:
                self.target_fort = None # 確保完了、次へ

        # 新規ターゲット探索
        best_score = -9999
        best_target = None
        
        # 候補: 中立 または 敵の砦
        candidates = [i for i in range(12) if state[i][0] != my_team]
        
        for cand in candidates:
            # 評価関数:
            # 1. 敵より中立を優先 (コスト安)
            # 2. 自分の領土から近い (孤立していない)
            # 3. 兵数が少ない (弱い)
            
            score = 0
            if state[cand][0] == 0: score += 2000 # 中立優先
            score -= state[cand][3] * 10 # 弱い方がいい
            
            # 自分の砦からの最小距離
            min_dist = 999
            for i in range(12):
                if state[i][0] == my_team and cand in state[i][5]:
                    min_dist = 1
                    break
            
            # 隣接していない遠くの砦は後回し
            if min_dist > 1: score -= 5000
            
            if score > best_score:
                best_score = score
                best_target = cand
        
        self.target_fort = best_target

    def get_upgrade_move(self, state, my_team, enemy_team) -> tuple[int, int, int]:
        my_forts = [i for i in range(12) if state[i][0] == my_team]
        for fid in my_forts:
            if not self.can_upgrade(state[fid]): continue
            
            # 敵の脅威度チェック (簡易版)
            threat = 0
            for nid in state[fid][5]:
                if state[nid][0] == enemy_team:
                    threat += state[nid][3]
            
            if threat < state[fid][3]:
                return 2, fid, 0
        return 0, 0, 0
