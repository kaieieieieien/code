"""
Template AI Player

このファイルをコピーして、あなた独自のAIプレイヤーを実装してください。

使い方:
1. このファイルをコピー: cp template_player.py player_yourname.py
2. クラス名を変更: TemplatePlayer -> YourPlayerName
3. team_name() の返り値を変更
4. update() メソッドに戦略を実装
"""

from tcg.controller import Controller
import random


class MachinedPlayer(Controller):
    """
    テンプレートAIプレイヤー

    このクラスをベースに独自の戦略を実装してください。
    """

    # 防御的な設定（多くの部隊を溜められる）
    fortress_limit = [10, 10, 20, 30, 40, 50]

    # FORTRESS_IMPORTANCEの設定はとりあえず一緒
    FORTRESS_IMPORTANCE = {
        0: 10, 1: 10, 2: 10,      # 上側エリア
        3: 1, 4: 10, 5: 1,     # 中央上
        6: 4, 7: 10, 8: 1,     # 中央下
        9: 10, 10: 10, 11: 10     # 下側エリア
    }

    UP_FORTRESS_PRIORITY = [1, 2, 0, 4]
    DOWM_FORTRESS_PRIORITY = [10, 9, 11, 7]


    def __init__(self) -> None:
        super().__init__()
        self.step = 0
        self.prev_team_state = None # 前のターンのチーム状態を保存する変数
        self.attacking_fort = None # 攻撃中の砦ID
        self.target_fort = None # 攻撃目標の砦ID

    def team_name(self) -> str:
        """
        プレイヤー名を返す

        トーナメント結果の表示に使用されます。

        Returns:
            str: プレイヤー名
        """
        return "Machined Player"
    
    def update(self, info) -> tuple[int, int, int]:
        """
        戦略的な判断でコマンドを選択（改善版 - アップグレード優先）
        """
        team, state, moving_pawns, spawning_pawns, done = info
        self.step += 1

        # 優先度付きアクションリスト
        actions = []
        # considered_actions = set()  # 重複防止

        # 前フレームから今回までで「新しく自軍になった砦」を検出
        newly_captured = set()
        current_teams = [state[i][0] for i in range(12)]

        if self.prev_team_state is not None:
            for i in range(12):
                # 0(中立) or 2(敵) から 1(自軍) になったものを新規占領とみなす
                if self.prev_team_state[i] != 1 and current_teams[i] == 1:
                    newly_captured.add(i)

        # 今回の状態を保存
        self.prev_team_state = current_teams[:]

        # 自分の要塞と敵の要塞を分類
        my_fortresses = [i for i in range(12) if state[i][0] == 1]
        enemy_fortresses = [i for i in range(12) if state[i][0] == 2]
        neutral_fortresses = [i for i in range(12) if state[i][0] == 0]

        # --- 全兵士数の計算 ---
        
        # 1. 砦の中にいる兵士の総数 (state[i][3] が兵士数)
        # state[i][0] が所有チーム (0:中立, 1:自分, 2:敵 ※自分が2の場合は逆)
        total_in_forts = sum(int(s[3]) for s in state)

        # 2. 移動中の兵士の総数 (リストの長さがそのまま人数)
        total_moving = len(moving_pawns)

        # 3. 出撃待機中の兵士の総数 (spawning_pawns[i][2] が残りの出撃数)
        total_spawning = sum(int(p[2]) for p in spawning_pawns)

        # 全合計
        total_soldiers = total_in_forts + total_moving + total_spawning

        my_team_id = team
        enemy_team_id = 2 if team == 1 else 1
        
        # 自分の総兵力
        my_soldiers = (
            sum(int(s[3]) for s in state if s[0] == my_team_id) +
            len([p for p in moving_pawns if p[0] == my_team_id]) +
            sum(int(p[2]) for p in spawning_pawns if p[0] == my_team_id)
        )

        # 敵の総兵力
        enemy_soldiers = (
            sum(int(s[3]) for s in state if s[0] == enemy_team_id) +
            len([p for p in moving_pawns if p[0] == enemy_team_id]) +
            sum(int(p[2]) for p in spawning_pawns if p[0] == enemy_team_id)
        )

        # ゲームフェーズの判定 (取得要塞数で判断)
        my_fortress_num = len(my_fortresses)
        if my_fortress_num < 3:
            phase = "early"
        elif my_fortress_num < 4:
            phase = "mid"
        else:
            phase = "late"

        # デバッグ情報（序盤のみ表示）


        # === 緊急防御: 最優先 ===
        under_attack = {}
        incoming_threats = {}
        
        for pawn in moving_pawns:
            pawn_team, kind, from_, to, pos = pawn
            # pos がリストの場合に対応（例: [x, y]）
            if isinstance(pos, (list, tuple)):
                # 進行度が別で保存されていないなら、距離計算は「ざっくり1」として扱うか、
                # もしくは x,y から距離を近似して計算する
                # ここでは安全のため固定値扱いにして、「エラーを出さずに動かす」ことを優先
                distance = 1.0
            else:
                distance = max(1.0, 100 - float(pos))

            if pawn_team == 2 and state[to][0] == 1:
                if to not in under_attack:
                    under_attack[to] = []
                under_attack[to].append((from_, pos))

                threat = kind * 10 / distance
                incoming_threats[to] = incoming_threats.get(to, 0) + threat

        # 防御が必要な要塞への支援
        for target_fort, threats in under_attack.items():
            current_defenders = state[target_fort][3]
            total_threat = incoming_threats.get(target_fort, 0)

            if current_defenders < total_threat * 1.2:
                neighbors = state[target_fort][5]
                for my_fort in neighbors:
                    action_key = (1, my_fort, target_fort)
                    if (state[my_fort][0] == 1 and 
                        state[my_fort][3] >= 5 
                        # and action_key not in considered_actions
                        ):
                        priority = 200 + total_threat * 10
                        actions.append((priority, 1, my_fort, target_fort))
                        # considered_actions.add(action_key)

        # === アップグレード戦略（序盤最優先）===
        # 序盤は部隊を溜めるためにアップグレードを最優先
        if phase == "early":
            upgrade_priority_base = 250  # 攻撃より優先
        elif phase == "mid":
            upgrade_priority_base = 100
        else:
            upgrade_priority_base = 70
        
        max_upgrade_level = {
            "early": 4,
            "mid": 3,
            "late": 2
        }[phase]

        # 中央の重要拠点は最優先でアップグレード
        for fort_id in [4, 7]:
            if fort_id in my_fortresses:
                level = state[fort_id][2]
                troops = state[fort_id][3]
                
                if (state[fort_id][4] == -1 and 
                    (level < max_upgrade_level or my_soldiers > 400) and
                    level < 5 and
                    troops >= self.fortress_limit[level] * 0.4):  # 40%で開始
                    priority = upgrade_priority_base + 50 + level * 10
                    actions.append((priority, 2, fort_id, 0))

        # その他の要塞のアップグレード
        for my_fort in my_fortresses:
            if my_fort not in [4, 7]:
                level = state[my_fort][2]
                troops = state[my_fort][3]
                importance = self.FORTRESS_IMPORTANCE.get(my_fort, 5)
                enemy_neighbors = self.count_enemy_neighbors(my_fort, state)
                
                # 序盤は積極的にアップグレード
                troops_threshold = self.fortress_limit[level] * (0.5 if phase == "early" else 0.5)
                
                if (state[my_fort][4] == -1 and 
                    (level < max_upgrade_level or my_soldiers > 400) and
                    level < 5 and
                    troops >= troops_threshold):
                    priority = upgrade_priority_base + importance + level * 10 + enemy_neighbors * 8 + 50 # とりあえずアップグレードは高めに
                    # もし敵が近くにいないなら、アップグレードを更に優先
                    neighbors = state[my_fort][5]
                    near_enemy = False
                    for neighbor in neighbors:
                        if state[neighbor][0] == 2:
                            near_enemy = True
                    if (near_enemy == False):
                        priority += 1000
                    actions.append((priority, 2, my_fort, 0)) 
        
        # # === 新規占領要塞の優先アップグレード ===
        # for fort_id in newly_captured:
        #     if fort_id in my_fortresses:
        #         level = state[fort_id][2]
        #         troops = state[fort_id][3]
        #         # まだアップグレード中でない & レベル上限以下
        #         if state[fort_id][4] == -1 and level < max_upgrade_level:
        #             # 新規占領砦は、通常よりも低いしきい値でアップグレードを開始
        #             threshold = self.fortress_limit[level] * 0.3
        #             if troops >= threshold:
        #                 # かなり高い優先度を与えて、他の行動より優先させる
        #                 priority = upgrade_priority_base + 80 + level * 10
        #                 actions.append((priority, 2, fort_id, 0))
        #                 if self.step < 2000:
        #                     print(f"    新規占領アップグレード計画: 要塞{fort_id} Lv{level}→{level+1} (優先度{priority}, 部隊{troops})")


        # === 序盤戦略: ターゲット集中一斉攻撃 ===
        if (phase in ["early", "mid"]):
            # 1. ターゲット状態の更新
            if self.target_fort is not None:
                # ターゲットが既に自分のものになったかチェック
                if state[self.target_fort][0] == 1:
                    self.target_fort = None
            
            # 2. 新規ターゲットの探索 (ターゲットがない場合のみ)
            if self.target_fort is None:
                best_trigger_fort = None
                best_target = None
                best_score = -float('inf')

                for my_fort in my_fortresses:
                    level = state[my_fort][2]
                    troops = state[my_fort][3]
                    max_troops = self.fortress_limit[level]
                    
                    # 攻撃開始の口火を切る条件: レベルMAX かつ 兵力90%以上
                    if (phase == "early" and level == 4 and troops >= max_troops * 0.9) or (phase == "mid" and level >= 3 and troops >= max_troops * 0.9):
                        neighbors = state[my_fort][5]
                        
                        for neighbor in neighbors:
                            if state[neighbor][0] == 0: # 中立のみ対象
                                neutral_troops = state[neighbor][3]
                                
                                # 評価関数
                                score = 0
                                multiplier = 1.5
                                if (neighbor in [4, 7] and my_fortress_num == 3):
                                    # 戦略的に重要拠点は4番目にとってほしい
                                    score += 1000 # 重要拠点
                                    # 取れるならすぐに取ってほしい
                                    if (my_soldiers > 100):
                                        multiplier = 1.0
                                    #print("IMPORTANT TARGET!")
                                score -= neutral_troops # 敵が少ない方がいい
                                
                                # 兵力差チェック (1.5倍以上)
                                if troops >= neutral_troops * multiplier:
                                    if score > best_score:
                                        best_score = score
                                        best_target = neighbor
                                        best_trigger_fort = my_fort
                
                if best_target is not None:
                    self.target_fort = best_target
            # 3. 一斉攻撃の実行 (ターゲットがある場合)
            if self.target_fort is not None:
                target = self.target_fort
                
                # 全味方要塞をチェックし、ターゲットに隣接していれば攻撃参加
                for my_fort in my_fortresses:
                    neighbors = state[my_fort][5]
                    if target in neighbors:
                        troops = state[my_fort][3]
                        # 兵力が少しでもあれば攻撃参加 (協力して倒す)
                        if troops >= 1:
                            # 兵力が多い順に優先度を高くする
                            # これにより、特定の砦だけが攻撃し続けるのを防ぎ、
                            # 兵力が多い砦から順次攻撃コマンドが発行される（自然なラウンドロビンになる）
                            priority = 10000 + troops
                            actions.append((priority, 1, my_fort, target))

        # if phase == "mid":
        #     for my_fort in my_fortresses:
        #         level = state[my_fort][2]
        #         troops = state[my_fort][3]
        #         max_troops = self.fortress_limit[level]
                
        #         # 収容量の90%以上溜まっている場合、収容量が10%になるまで攻撃
        #         if (troops >= max_troops * 0.9 and self.isAttack == False) or (troops >= 0.1 and self.isAttack == True):
        #             neighbors = state[my_fort][5]
        #             self.isAttack = True
        #             for neighbor in neighbors:
        #                 action_key = (1, my_fort, neighbor)
        #                 # if state[neighbor][0] == 0 and action_key not in considered_actions:
        #                 if state[neighbor][0] == 0:
        #                     neutral_troops = state[neighbor][3]
                            
        #                     # 十分な兵力比があるか確認
        #                     if troops >= neutral_troops * 1.5:
        #                         importance = self.FORTRESS_IMPORTANCE.get(neighbor, 5)
        #                         ease = max(0, 30 - neutral_troops)
        #                         # already_attacking = self.is_already_attacking(my_fort, neighbor, spawning_pawns, moving_pawns)
        #                         already_attacking = False # とりあえず無視
                                
        #                         if not already_attacking:
        #                             priority = 150 + importance * 8 + ease
        #                             actions.append((priority, 1, my_fort, neighbor))
        #                             # considered_actions.add(action_key)
        #                             if self.step < 500:
        #                                 print(f"    序盤攻撃計画: {my_fort}({troops})→{neighbor}({neutral_troops}) (優先度{priority})")
        #         elif (troops <= 0.1 and self.isAttack == True):
        #             self.isAttack = False
        
        # if

        # # === 中立要塞への計算された攻撃（中盤以降）===
        # # if ((phase == "late") or (phase == "mid")):
        # if( phase in ["late"] ):
        #     for my_fort in my_fortresses:
        #         if state[my_fort][3] >= 30:
        #             neighbors = state[my_fort][5]
        #             for neighbor in neighbors:
        #                 action_key = (1, my_fort, neighbor)
        #                 # if state[neighbor][0] == 0 and action_key not in considered_actions:
        #                 if state[neighbor][0] == 0:
        #                     my_troops = state[my_fort][3]
        #                     neutral_troops = state[neighbor][3]
        #                     success_ratio = my_troops / max(neutral_troops, 1)
        #                     success_threshold = 1.2 if my_soldiers > 1500 else 3.0
                            
        #                     if success_ratio >= success_threshold:
        #                         importance = self.FORTRESS_IMPORTANCE.get(neighbor, 5)
        #                         priority = 120 + importance * 5 + int(success_ratio * 10)
        #                         if neighbor in [4, 7]:
        #                             priority += 1000  # 重要拠点は更に優先
        #                         actions.append((priority, 1, my_fort, neighbor))
        #                         # considered_actions.add(action_key)

        # === 敵要塞への戦略的攻撃 ===
        for my_fort in my_fortresses:
            level = state[my_fort][2]
            min_troops = max(15, self.fortress_limit[level] * 0.5)
            
            if state[my_fort][3] >= min_troops:
                neighbors = state[my_fort][5]
                for neighbor in neighbors:
                    action_key = (1, my_fort, neighbor)
                    # if state[neighbor][0] == 2 and action_key not in considered_actions:
                    if state[neighbor][0] == 2:
                        my_troops = state[my_fort][3]
                        enemy_troops = state[neighbor][3]
                        enemy_level = state[neighbor][2]
                        
                        defense_multiplier = 1 + enemy_level * 0.15
                        adjusted_enemy_strength = enemy_troops * defense_multiplier
                        success_ratio = my_troops / max(adjusted_enemy_strength, 1)
                        # 取られて間もない要塞なら問題なく攻撃を開始する
                        success_threshold = 0.5 if (my_soldiers > enemy_soldiers * 10) else 3.0
                        
                        if success_ratio >= success_threshold:  # 敵はより慎重に
                            importance = self.FORTRESS_IMPORTANCE.get(neighbor, 5)
                            weakness = max(0, 25 - enemy_troops)
                            priority = 120 + importance * 2 + weakness + int(success_ratio * 5)
                            actions.append((priority, 1, my_fort, neighbor))
                            # considered_actions.add(action_key)

        # === 部隊の戦略的再配置（バケツリレー改善版）===
        for my_fort in my_fortresses:
            level = state[my_fort][2]
            troops = state[my_fort][3]
            max_troops = self.fortress_limit[level]
            enemy_neighbors = self.count_enemy_neighbors(my_fort, state)
            
            # しきい値の動的設定
            has_enemy_neighbor = enemy_neighbors > 0
            threshold = 0.9 if has_enemy_neighbor else 0.4  # 前線は90%、後方は40%
            
            # 溢れ判定
            is_overflowing = troops >= max_troops * 0.9
            
            # しきい値を超えている場合のみ処理
            if troops > max_troops * threshold: 
                neighbors = state[my_fort][5]
                best_target = None
                best_priority = 0
                
                for neighbor in neighbors:
                    action_key = (1, my_fort, neighbor)
                    
                    # 味方要塞のみが対象
                    # if state[neighbor][0] == 1 and action_key not in considered_actions: 
                    if state[neighbor][0] == 1:
                        # # 序盤は中央（4,7）への移動は避ける
                        # if phase == "early" and neighbor in [4, 7]:
                        #     continue
                        
                        neighbor_enemy_count = self.count_enemy_neighbors(neighbor, state)
                        
                        # その味方要塞が前線（敵の隣）にいる場合
                        if neighbor_enemy_count > 0:
                            # 溢れている場合は超高優先
                            priority = 500 if is_overflowing else 60
                            
                            if priority > best_priority:
                                best_priority = priority
                                best_target = neighbor
                                break  # 前線要塞が見つかったら即決定
                
                # 前線要塞が見つからなかったが、溢れている場合
                if best_target is None and is_overflowing: 
                    for neighbor in neighbors:
                        action_key = (1, my_fort, neighbor)
                        # if state[neighbor][0] == 1 and action_key not in considered_actions:
                        if state[neighbor][0] == 1:
                            # if phase == "early" and neighbor in [4, 7]:
                            #     continue
                            # とにかく溢れを防ぐための移動
                            best_priority = 300
                            best_target = neighbor
                            break
                
                # 移動先が決まったら actions に追加
                if best_target is not None:
                    action_key = (1, my_fort, best_target)
                    # 優先度に微小なランダム値を加えて、順番をばらけさせる
                    randomized_priority = best_priority + random.uniform(0, 0.1)
                    actions.append((best_priority, 1, my_fort, best_target))
                    # considered_actions.add(action_key)

        # 最も優先度の高いアクションを実行
        if actions:
            actions.sort(reverse=True, key=lambda x: x[0])
            _, command, subject, to = actions[0]
            

            return command, subject, to

        # 何もすることがない場合
        return 0, 0, 0

    def is_already_attacking(self, from_fort, to_fort, spawning_pawns, moving_pawns):
        """指定された経路で既に攻撃部隊を送っているか確認"""
        for pawn in spawning_pawns:
            try:
                if len(pawn) == 4:
                    pawn_team, kind, pawn_from, pawn_to = pawn
                elif len(pawn) >= 5:
                    pawn_team, kind, pawn_from, pawn_to = pawn[0], pawn[1], pawn[2], pawn[3]
                else:
                    continue
                
                if pawn_team == 1 and pawn_from == from_fort and pawn_to == to_fort:
                    return True
            except (ValueError, IndexError):
                continue
        
        for pawn in moving_pawns:
            try:
                pawn_team, kind, pawn_from, pawn_to, pos = pawn
                if pawn_team == 1 and pawn_from == from_fort and pawn_to == to_fort:
                    return True
            except (ValueError, IndexError):
                continue
        
        return False


    def count_enemy_neighbors(self, fort_id, state):
        """指定された要塞に隣接する敵要塞の数を数える"""
        neighbors = state[fort_id][5]
        return sum(1 for n in neighbors if state[n][0] == 2)
