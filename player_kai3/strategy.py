"""
strategy.py - Kai Player Ver.Hybrid (戦闘ロジック搭載)
"""
MIRROR_MAP = {
    0: 11, 11: 0,
    1: 10, 10: 1,
    2: 9,  9: 2,
    3: 8,  8: 3,
    4: 7,  7: 4,
    5: 6,  6: 5
}
HARD_LIMITS = [10, 10, 20, 30, 40, 50]

class Strategy:
    def __init__(self):
        pass

    def get_mirror_id(self, fortress_id) -> int:
        return MIRROR_MAP.get(fortress_id, 0)

    def can_upgrade(self, fortress_state) -> bool:
        level = fortress_state[2]
        pawn = fortress_state[3]
        if level >= 5 or fortress_state[4] > 0: return False
        cost = (HARD_LIMITS[level + 1] if level + 1 < 6 else 50) // 2
        return pawn >= cost

    def is_frontline(self, state, fid, my_team) -> bool:
        """隣に敵がいるか？"""
        neighbors = state[fid][5]
        for nid in neighbors:
            if state[nid][0] != my_team and state[nid][0] != 0: # 敵(2 or 1)
                return True
        return False

    def is_overflowing(self, state, fid) -> bool:
        """兵があふれそうか？"""
        level = state[fid][2]
        limit = HARD_LIMITS[level]
        return state[fid][3] >= limit * 0.8

    def get_combat_move(self, state, fid, my_team) -> tuple[int, int, int]:
        """前線用の戦闘ロジック"""
        my_f = state[fid]
        my_pawns = my_f[3]
        level = my_f[2]
        limit = HARD_LIMITS[level]

        # 1. 強化優先 (余裕があれば)
        if self.can_upgrade(my_f):
            # 敵が近くにいて兵数が負けてるなら強化しない
            is_safe_to_upgrade = True
            for nid in my_f[5]:
                n = state[nid]
                if n[0] != my_team and n[0] != 0: # 敵
                    if n[3] > my_pawns: is_safe_to_upgrade = False
            
            if is_safe_to_upgrade:
                return 2, fid, 0

        # 攻撃/移動力の計算 (半分移動)
        attack_power = my_pawns // 2
        if attack_power < 1: return 0, 0, 0

        neighbors = my_f[5]
        best_target = None
        best_score = -9999

        for nid in neighbors:
            n = state[nid]
            n_team = n[0]
            n_pawns = n[3]
            
            score = -9999
            
            if n_team != my_team and n_team != 0: # 敵
                # 勝てる見込みがある (1.2倍以上の差)
                if attack_power > n_pawns * 1.2:
                    score = 1000 + (100 - n_pawns) # 弱い敵を優先
                # 拮抗しているなら牽制 (あふれ防止)
                elif self.is_overflowing(state, fid):
                    score = 500
                else:
                    score = -100 # 負けるなら攻めない(防衛専念)

            elif n_team == 0: # 中立
                # 確実に取れるなら取る
                if attack_power > n_pawns + 2:
                    score = 2000 - n_pawns # コストが安い順
                
            elif n_team == my_team: # 味方
                # 前線への補給 (自分が安全地帯、または自分が溢れそうな時)
                # 送り先が前線なら加点
                if self.is_frontline(state, nid, my_team):
                    t_limit = HARD_LIMITS[n[2]]
                    if n[3] < t_limit * 0.8: # 満タンでなければ
                        score = 100
                
            if score > best_score:
                best_score = score
                best_target = nid

        if best_target is not None and best_score > 0:
            return 1, fid, best_target
            
        return 0, 0, 0