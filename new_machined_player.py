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


class NewMachinedPlayer(Controller):
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
        return "New Machined Player"

    def execute_bucket_brigade(self, target_id, state, my_fortresses, actions):
        """
        ターゲットに向けてバケツリレーで兵士を輸送する
        Args:
            target_id: 目標となる要塞ID (前線)
            state: ゲーム状態
            my_fortresses: 自軍の要塞リスト
            actions: 行動リスト (ここにコマンドを追加する)
        """
        if target_id is None:
            return

        # 1. ターゲットからの距離マップを作成 (BFS)
        dist_map = {i: 999 for i in range(12)}
        dist_map[target_id] = 0
        queue = [target_id]
        visited = {target_id}
        
        while queue:
            curr = queue.pop(0)
            d = dist_map[curr]
            neighbors = state[curr][5] # 5番目が隣接リスト
            for n in neighbors:
                if n not in visited:
                    visited.add(n)
                    dist_map[n] = d + 1
                    queue.append(n)

        # 2. 各要塞について、よりターゲットに近い味方要塞へ移動
        for my_fort in my_fortresses:
            neighbors = state[my_fort][5]
            
            # ターゲットに直接攻撃できる（隣接している）場合は、ここでは移動指示を出さない
            # (一斉攻撃ロジックに任せる)
            if target_id in neighbors:
                continue

            # ターゲットに近づく方向の味方要塞を探す
            current_dist = dist_map[my_fort]
            best_next_hop = None
            min_dist = current_dist
            
            for neighbor in neighbors:
                # 味方要塞 かつ 距離が近づく
                if state[neighbor][0] == state[my_fort][0]:
                    if dist_map[neighbor] < min_dist:
                        min_dist = dist_map[neighbor]
                        best_next_hop = neighbor
            
            # 移動実行
            if best_next_hop is not None:
                troops = state[my_fort][3]
                level = state[my_fort][2]
                max_troops = self.fortress_limit[level]
                
                # 閾値設定: 収容量の30% または 最小10人。ただし緊急時等のために最低5は確保
                # これにより「ちょこちょこ移動」を防ぎ「まとめて輸送」を行う
                send_threshold = max(5, int(max_troops * 0.3))
                
                if troops >= send_threshold:
                    priority = 10000 + troops # 攻撃よりは低いが、移動優先度は高め
                    actions.append((priority, 1, my_fort, best_next_hop))
                    # print(f"    バケツリレー: {my_fort}→{best_next_hop}")
    
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
        elif my_fortress_num < 5:
            phase = "mid"
        else:
            phase = "late"

        # デバッグ情報（序盤のみ表示）
        if self.step % 1000 == 0:
            print(f"\n=== Step {self.step} ({phase}) ===")
            print(f"自分の要塞数: {len(my_fortresses)}, 敵の要塞数: {len(enemy_fortresses)}, 中立: {len(neutral_fortresses)}")
            for my_fort in my_fortresses:
                level = state[my_fort][2]
                troops = state[my_fort][3]
                max_troops = self.fortress_limit[level]
                flag = " (NEW)" if my_fort in newly_captured else ""
                print(f"  要塞{my_fort}{flag}: Lv{level}, 部隊{troops}/{max_troops}, 充填率{troops/max_troops*100:.1f}%")
            print(f"全兵士数: {total_soldiers} (砦内: {total_in_forts}, 移動中: {total_moving}, 出撃待機: {total_spawning})")
            print(f"自分の総兵力: {my_soldiers}, 敵の総兵力: {enemy_soldiers}")

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
            "early": 3,
            "mid": 2,
            "late": 2
        }[phase]

        # ターゲット攻撃中は兵士供給を優先するため、アップグレード基準を厳しくする
        is_attacking_target = (self.target_fort is not None)
        upgrade_troop_ratio = 0.8 if is_attacking_target else 0.4
        upgrade_troop_ratio_neutral = 0.8 if is_attacking_target else 0.5

        # 中央の重要拠点は最優先でアップグレード
        for fort_id in [4, 7]:
            if fort_id in my_fortresses:
                level = state[fort_id][2]
                troops = state[fort_id][3]
                
                if (state[fort_id][4] == -1 and 
                    (level < max_upgrade_level or my_soldiers > 200) and
                    level < 5 and
                    troops >= self.fortress_limit[level] * upgrade_troop_ratio):  # 攻撃中は80%, 通常40%
                    priority = upgrade_priority_base + 50 + level * 10
                    actions.append((priority, 2, fort_id, 0))
                    # print("LAUNCH UPGRADE")
                    if self.step < 500:
                        print(f"    重要拠点アップグレード計画: 要塞{fort_id} Lv{level}→{level+1} (優先度{priority})")

        # その他の要塞のアップグレード
        for my_fort in my_fortresses:
            if my_fort not in [4, 7]:
                level = state[my_fort][2]
                troops = state[my_fort][3]
                importance = self.FORTRESS_IMPORTANCE.get(my_fort, 5)
                enemy_neighbors = self.count_enemy_neighbors(my_fort, state)
                
                # 序盤は積極的にアップグレード
                basic_threshold = self.fortress_limit[level] * upgrade_troop_ratio_neutral
                troops_threshold = basic_threshold * (0.5 if phase == "early" else 1.0) # early補正は維持しつつベースを変更
                
                if (state[my_fort][4] == -1 and 
                    (level < max_upgrade_level or my_soldiers > 200) and
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
                    # print("LAUNCH UPGRADE")
                    if self.step < 500:
                        print(f"    アップグレード計画: 要塞{my_fort} Lv{level}→{level+1} (優先度{priority})")
        
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


        # === ターゲット集中一斉攻撃（全フェーズ統合版） ===
        
        # 1. ターゲット状態の更新
        if self.target_fort is not None:
            # ターゲットが既に自分のものになったかチェック
            if state[self.target_fort][0] == 1:
                if self.step < 500:
                    print(f"    占領完了: {self.target_fort} を確保しました")
                self.target_fort = None
            # 他にも、ターゲットが極端に強化されて勝てなくなった場合などの解除条件を入れると良い

        # 2. 新規ターゲットの探索 (ターゲットがない場合)
        if self.target_fort is None:
            best_target = None
            best_score = -float('inf')
            best_trigger_fort = None

            # --- A. 中立要塞の評価 (序盤・中盤で優先) ---
            if phase in ["early", "mid"]:
                for my_fort in my_fortresses:
                    level = state[my_fort][2]
                    troops = state[my_fort][3]
                    max_troops = self.fortress_limit[level]
                    
                    # 攻撃開始トリガー: レベルと兵力条件
                    if (phase == "early" and level == 3 and troops >= max_troops * 0.9) or \
                       (phase == "mid" and level >= 2 and troops >= max_troops * 0.9):
                        
                        neighbors = state[my_fort][5]
                        for neighbor in neighbors:
                            if state[neighbor][0] == 0: # 中立のみ
                                neutral_troops = state[neighbor][3]
                                score = 0
                                multiplier = 1.5
                                
                                # 重要拠点ボーナス
                                if neighbor in [6, 8] and (my_fortress_num in [3, 4]):
                                    score += 1000
                                    if my_soldiers > 100: multiplier = 1.0
                                
                                score -= neutral_troops
                                
                                # 勝てる見込みがあるか
                                if troops >= neutral_troops * multiplier:
                                    if score > best_score:
                                        best_score = score
                                        best_target = neighbor
                                        best_trigger_fort = my_fort

            # --- B. 敵要塞の評価 (中立ターゲットが決まらなかった場合) ---
            if best_target is None:
                # 現在の総兵力の差を見る
                advantage_mode = False
                if (my_soldiers > enemy_soldiers * 3) and (phase == "late"):
                    # 自分が圧倒的に有利な場合は、より積極的に攻撃を仕掛ける
                    advantage_mode = True
                
                # 敵要塞ごとに「隣接する味方の総戦力」を集計
                enemy_attack_power = {} # enemy_id -> total_my_troops
                
                for my_fort in my_fortresses:
                    # 攻撃に参加できる最低兵力
                    if state[my_fort][3] >= 5:
                        for neighbor in state[my_fort][5]:
                            if state[neighbor][0] == 2: # 敵要塞
                                enemy_attack_power[neighbor] = enemy_attack_power.get(neighbor, 0) + state[my_fort][3]
                            elif (state[neighbor][0] == 0  and advantage_mode == True): # 中立要塞も少し加味
                                enemy_attack_power[neighbor] = enemy_attack_power.get(neighbor, 0) + state[my_fort][3]

                # 最適な敵ターゲットを選定
                best_enemy_score = -float('inf')
                
                for enemy_id, total_power in enemy_attack_power.items():
                    enemy_troops = state[enemy_id][3]
                    enemy_level = state[enemy_id][2]
                    
                    defense_multiplier = 1 + enemy_level * 0.15
                    adjusted_enemy_strength = enemy_troops * defense_multiplier
                    
                    # 勝率 (総戦力 vs 敵戦力)
                    ratio = total_power / max(adjusted_enemy_strength, 1)
                    
                    # 閾値設定 (確実に勝てるときだけ行く)
                    threshold = 1.2

                    # 自分の総兵力が極端に多い場合は閾値を大きく下げる
                    if advantage_mode == True:
                        threshold = 0.1
                    
                    if ratio >= threshold:
                        importance = self.FORTRESS_IMPORTANCE.get(enemy_id, 5)
                        # スコア: 重要度と勝率、敵の兵力(少ない方が良い)で評価
                        score = importance * 10 + ratio * 5 - enemy_troops * 0.1
                        
                        if score > best_enemy_score:
                            best_enemy_score = score
                            best_target = enemy_id
                            best_trigger_fort = -1 # 特定のトリガーなし

            # ターゲット決定
            if best_target is not None:
                self.target_fort = best_target
                if self.step < 500:
                    type_str = "中立" if state[best_target][0] == 0 else "敵"
                    print(f"    新規ターゲット({type_str}): {best_target} (予想戦力比などを加味)")

        # 3. 一斉攻撃の実行 (ターゲットがある場合)
        if self.target_fort is not None:
            target = self.target_fort
            
            # 全味方要塞をチェックし、ターゲットに隣接していれば攻撃参加
            for my_fort in my_fortresses:
                neighbors = state[my_fort][5]
                if target in neighbors:
                    troops = state[my_fort][3]
                    level = state[my_fort][2]
                    
                    # 敵要塞への攻撃時は、最低限の守りを残すと安全かも（任意）
                    min_remain = 0
                    if state[target][0] == 2:
                        min_remain = int(self.fortress_limit[level] * 0.50) # 50%だけ残す

                    if troops > min_remain:
                        priority = 10000 + troops
                        actions.append((priority, 1, my_fort, target))
                        if self.step < 500:
                            print(f"    一斉攻撃参加: {my_fort}→{target} (兵力{troops})")
            
            # バケツリレーを実行
            self.execute_bucket_brigade(target, state, my_fortresses, actions)

        # === 部隊の戦略的再配置（バケツリレー改善版）===
        for my_fort in my_fortresses:
            level = state[my_fort][2]
            troops = state[my_fort][3]
            max_troops = self.fortress_limit[level]
            enemy_neighbors = self.count_enemy_neighbors(my_fort, state)
            
            # しきい値の動的設定
            has_enemy_neighbor = enemy_neighbors > 0
            threshold = 0.9 if has_enemy_neighbor else 0.5  # 前線は90%、後方は50%
            
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
            
            # デバッグ出力
            if self.step < 500:
                if command == 1:
                    action_type = "攻撃" if state[to][0] != 1 else "支援"
                    print(f"  → 実行: {action_type} {subject}→{to} (優先度{actions[0][0]})")
                elif command == 2:
                    print(f"  → 実行: アップグレード 要塞{subject} (優先度{actions[0][0]})")
            
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
