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


class NewComer(Controller):
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
        return "New Comer"

    def execute_bucket_brigade(self, target_id, state, my_fortresses, actions, priority_base=10000, troops_threshold=5, ignore_direct_neighbors=True):
        """
        ターゲットに向けてバケツリレーで兵士を輸送する
        Args:
            target_id: 目標となる要塞ID (前線)
            state: ゲーム状態
            my_fortresses: 自軍の要塞リスト
            actions: 行動リスト (ここにコマンドを追加する)
            priority_base: 優先度の基準値
            troops_threshold: 移動を開始する最低兵力
            ignore_direct_neighbors: ターゲットに隣接する要塞からの移動を除外するか
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
            
            # フラグがTrueなら、ターゲットに隣接している場合は移動指示を出さない (攻撃ロジック等に任せる)
            if ignore_direct_neighbors and target_id in neighbors:
                continue

            # ターゲットに近づく方向の味方要塞を
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
                
                # 溢れそうな場合は優先度を上げる (Smart Logistics)
                overflow_bonus = 0
                if max_troops > 0 and troops >= max_troops * 0.9:
                    overflow_bonus = 300 # 溢れ防止はかなり重要

                # しきい値チェック (溢れそうなときはしきい値無視)
                if troops >= troops_threshold or overflow_bonus > 0:
                    priority = priority_base + troops + overflow_bonus + random.uniform(0, 1)
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
        elif my_fortress_num < 7:
            phase = "mid-late"
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

        # === 緊急防御: 改良版 (Concrete Defense + Bucket Brigade) ===
        under_attack_info = {} # key: target_fort_id, value: {total_enemy: int, min_dist: float}
        incoming_reinforcements = {} # key: target_fort_id, value: total_friendly_troops

        # 1. 移動中の部隊を分析（敵の攻撃と、味方の援軍）
        for pawn in moving_pawns:
            pawn_team, kind, from_, to, pos = pawn
            
            # 距離計算
            if isinstance(pos, (list, tuple)):
                dist = 1.0
            else:
                dist = max(1.0, 100 - float(pos))

            # ケースA: 敵軍(2) -> 自軍(1) への攻撃
            if pawn_team == 2 and state[to][0] == 1:
                if to not in under_attack_info:
                    under_attack_info[to] = {"total_enemy": 0, "min_dist": 999.0}
                
                under_attack_info[to]["total_enemy"] += kind
                if dist < under_attack_info[to]["min_dist"]:
                    under_attack_info[to]["min_dist"] = dist
            
            # ケースB: 自軍(1) -> 自軍(1) への移動（既存の援軍）
            elif pawn_team == 1 and state[to][0] == 1:
                incoming_reinforcements[to] = incoming_reinforcements.get(to, 0) + kind

        # 2. 防御アクションの生成
        worst_target = None
        max_shortage = 0

        for target_fort, info in under_attack_info.items():
            total_enemy_troops = info["total_enemy"]
            min_dist = info["min_dist"] # 最も近い敵までの距離（緊急度の指標）
            
            current_defenders = state[target_fort][3]
            already_coming = incoming_reinforcements.get(target_fort, 0)
            
            # 防衛に必要な兵力計算（敵総兵力の1.2倍を安全圏とする）
            # 現在の兵力 + 既にや向かっている援軍 で足りているか？
            needed_troops = (total_enemy_troops * 1.2) - (current_defenders + already_coming)
            
            # 兵力が不足している場合のみ援軍を要請
            if needed_troops > 0:
                # 最もピンチな要塞を記録
                if needed_troops > max_shortage:
                    max_shortage = needed_troops
                    worst_target = target_fort

                neighbors = state[target_fort][5]
                for my_fort in neighbors:
                    # 援軍元として適切かチェック
                    # 1. 自軍である
                    # 2. 兵力が一定以上ある (最低でも5)
                    # 3. 自身も攻撃されていない（under_attack_infoに含まれていないこと）
                    if (state[my_fort][0] == 1 and 
                        state[my_fort][3] >= 5 and 
                        my_fort not in under_attack_info): 
                        
                        urgency_bonus = 500 / max(1.0, min_dist * 0.1)
                        priority = 200 + urgency_bonus + needed_troops
                        actions.append((priority, 1, my_fort, target_fort))

        # 3. 深刻な危機の場合、バケツリレーで遠方からも支援する
        if worst_target is not None and max_shortage >= 15:
             # バケツリレー関数を利用して、全軍に支援要請（優先度はbucket_brigade内で10000+で設定される）
             self.execute_bucket_brigade(worst_target, state, my_fortresses, actions)
             if self.step < 500:
                 print(f"  防衛バケツリレー発動: ターゲット{worst_target} (不足{max_shortage:.1f})")

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
            "mid-late": 2,
            "late": 2
        }[phase]

        # 中央の重要拠点は最優先でアップグレード
        for fort_id in [4, 7]:
            if fort_id in my_fortresses:
                level = state[fort_id][2]
                troops = state[fort_id][3]
                
                if (state[fort_id][4] == -1 and 
                    (level < max_upgrade_level or my_soldiers > 200) and
                    level < 5 and
                    troops >= self.fortress_limit[level] * 0.4):  # 40%で開始
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
                troops_threshold = self.fortress_limit[level] * (0.5 if phase == "early" else 0.5)
                
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


        # === 序盤戦略: ターゲット集中一斉攻撃 ===
        if (phase in ["early", "mid"]):
            # 1. ターゲット状態の更新
            if self.target_fort is not None:
                # ターゲットが既に自分のものになったかチェック
                if state[self.target_fort][0] == 1:
                    # 占領完了！ターゲット解除
                    if self.step < 500:
                        print(f"    占領完了: {self.target_fort} を確保しました")
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
                    if (phase == "early" and level == 3 and troops >= max_troops * 0.9) or (phase == "mid" and level >= 2 and troops >= max_troops * 0.9):
                        neighbors = state[my_fort][5]
                        
                        for neighbor in neighbors:
                            if state[neighbor][0] == 0: # 中立のみ対象
                                neutral_troops = state[neighbor][3]
                                
                                # 評価関数
                                score = 0
                                multiplier = 1.5
                                if (neighbor in [6, 8] and (my_fortress_num == 3 or my_fortress_num == 4)):
                                    # 戦略的に重要拠点は4番目にとってほしい
                                    score += 1000 # 重要拠点
                                    # 取れるならすぐに取ってほしい
                                    if (my_soldiers > 100):
                                        multiplier = 1.0
                                    print("IMPORTANT TARGET!")
                                score -= neutral_troops # 敵が少ない方がいい
                                
                                # 兵力差チェック (1.5倍以上)
                                if troops >= neutral_troops * multiplier:
                                    if score > best_score:
                                        best_score = score
                                        best_target = neighbor
                                        best_trigger_fort = my_fort
                
                if best_target is not None:
                    self.target_fort = best_target
                    if self.step < 500:
                        print(f"    新規ターゲット設定: {best_target} (トリガー: {best_trigger_fort})")

            # 3. 一斉攻撃の実行 (ターゲットがある場合)
            if self.target_fort is not None:
                target = self.target_fort
                
                # 全味方要塞をチェックし、ターゲットに隣接していれば攻撃参加
                neighbor_fort = []
                for my_fort in my_fortresses:
                    neighbors = state[my_fort][5]
                    if target in neighbors:
                        troops = state[my_fort][3]
                        # 兵力が少しでもあれば攻撃参加 (協力して倒す)
                        if troops >= 1:
                            # 隣り合う要塞の番号を保存
                            neighbor_fort.append(my_fort)
                            # 兵力が多い順に優先度を高くする
                            # これにより、特定の砦だけが攻撃し続けるのを防ぎ、
                            # 兵力が多い砦から順次攻撃コマンドが発行される（自然なラウンドロビンになる）
                            priority = 10000 + troops
                            actions.append((priority, 1, my_fort, target))
                            if self.step < 500:
                                print(f"    一斉攻撃参加: {my_fort}→{target} (兵力{troops})")
                
                # バケツリレーを実行
                self.execute_bucket_brigade(target, state, my_fortresses, actions)

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
                    if state[neighbor][0] == 2 or (state[neighbor][0] == 0 and phase == "late"):
                        my_troops = state[my_fort][3]
                        enemy_troops = state[neighbor][3]
                        enemy_level = state[neighbor][2]
                        
                        defense_multiplier = 1 + enemy_level * 0.15
                        adjusted_enemy_strength = enemy_troops * defense_multiplier
                        success_ratio = my_troops / max(adjusted_enemy_strength, 1)
                        # 取られて間もない要塞なら問題なく攻撃を開始する
                        if (state[neighbor][0] == 2):
                            success_threshold = 0.5 if (my_soldiers > enemy_soldiers * 3) else 3.0
                        elif (state[neighbor][0] == 0 and phase == "late"):
                            success_threshold = 0.5 if (my_soldiers > enemy_soldiers * 4) else 2.0
                        
                        if success_ratio >= success_threshold:  # 敵はより慎重に
                            importance = self.FORTRESS_IMPORTANCE.get(neighbor, 5)
                            weakness = max(0, 25 - enemy_troops)
                            priority = 120 + importance * 2 + weakness + int(success_ratio * 5)
                            actions.append((priority, 1, my_fort, neighbor))
                            # considered_actions.add(action_key)

        # === 常時補給 (Logistics Supply) ===
        # ターゲットや防御対象がない場合でも、常に前線に兵を送る
        # 敵に隣接する自軍要塞を「前線」とみなす
        front_lines = [f for f in my_fortresses if self.count_enemy_neighbors(f, state) > 0]
        
        # 前線要塞それぞれに対してバケツリレーを設定
        if front_lines:
            for fort in front_lines:
                self.execute_bucket_brigade(fort, state, my_fortresses, actions, 
                                          priority_base=50, 
                                          troops_threshold=10, 
                                          ignore_direct_neighbors=False)

        # === オーバーフロー防止 (Overflow Protection) ===
        # 前線の要塞などが満杯になった場合、隣接する味方へ兵を逃がす
        for my_fort in my_fortresses:
            level = state[my_fort][2]
            troops = state[my_fort][3]
            max_troops = self.fortress_limit[level]
            
            # 90%以上で溢れそうなら対策発動
            if max_troops > 0 and troops >= max_troops * 0.9:
                neighbors = state[my_fort][5]
                friendly_neighbors = [n for n in neighbors if state[n][0] == 1]
                
                if friendly_neighbors:
                    best_receiver = None
                    best_score = -float('inf')
                    
                    for receiver in friendly_neighbors:
                        r_level = state[receiver][2]
                        r_troops = state[receiver][3]
                        r_max = self.fortress_limit[r_level]
                        
                        # 評価基準:
                        # 1. 空き容量が多いこと (充填率が低い)
                        # 2. 前線に近い、あるいは前線そのものであること
                        
                        vacancy_rate = 1.0 - (r_troops / r_max) if r_max > 0 else 0
                        is_front = self.count_enemy_neighbors(receiver, state) > 0
                        
                        score = vacancy_rate * 10
                        if is_front:
                            score += 5 # 前線なら優先的に受け入れてもらう
                        
                        if score > best_score:
                            best_score = score
                            best_receiver = receiver
                    
                    if best_receiver is not None:
                        # execute_bucket_brigadeでアクションが生成されなかった場合（行き止まりなど）
                        # または生成されていても、こちらのほうが優先度が高くなるように設定(300+α)
                        # バケツリレーのoverflow_bonus(300)と同等の優先度を持たせる
                        priority = 300 + best_score
                        actions.append((priority, 1, my_fort, best_receiver))
                        if self.step < 500 and self.step % 10 == 0:
                             print(f"  オーバーフロー防止: {my_fort}→{best_receiver} (score:{best_score:.1f})")

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
