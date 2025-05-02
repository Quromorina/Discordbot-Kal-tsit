import json
import sqlite3
import os
import re

# --- ① パスの設定 (ここは自分の環境に合わせてね！) ---
script_dir = os.path.dirname(__file__)
# 家のラズパイなら...
data_repo_path = os.path.join(script_dir, 'ark_data')
print(f"データリポジトリのパス: {data_repo_path}")

db_path = os.path.join(script_dir, 'arknights_data.db')
print(f"データベースファイルのパス: {db_path}")

# --- ★★★ クラスID -> 日本語名 変換マップ (手動で作成！) ★★★ ---
class_jp_map = {
    "PIONEER": "先鋒", "WARRIOR": "前衛", "SNIPER": "狙撃", "CASTER": "術師",
    "SUPPORT": "補助", "MEDIC": "医療", "TANK": "重装", "SPECIAL": "特殊",
    # ★★★ JSONで使われているIDと日本語名を正確に！ 大文字/小文字も注意！ ★★★
}
print(f"読み込んだクラス日本語マップ: {len(class_jp_map)} 件")

# --- ★★★ 職分ID -> 日本語名 変換マップ  ★★★ ---
archetype_jp_map = {
    "agent": "偵察兵", "alchemist": "錬金士", "aoesniper" : "榴弾射手", "artsfghter" : "術戦士",
    "artsprotector": "術技衛士", "bard": "吟遊者", "bearer": "旗手", "blastcaster": "爆撃術師",
    "blessing": "祈祷師", "bombarder": "投擲手", "centurion": "強襲者", "chain": "連鎖術師",
    "chainhealer": "連鎖癒師", "charger": "突撃兵", "closerange": "精密射手", "corecaster": "中堅術師",
    "craftsman": "工匠", "crusher": "重剣士", "dollkeeper": "傀儡師", "duelist": "決闘者",
    "executor": "執行者", "fastshot": "速射手", "fearless": "勇士", "fighter": "闘士",
    "fortress": "堅城砲手", "funnel": "操機術師", "geek": "鬼才", "guardian": "庇護衛士",
    "hammer": "槌撃士", "healer": "療養師", "hookmaster": "鉤縄師", "hunter": "狩人",
    "incantationmedic": "呪癒師", "instructor": "教官", "librator": "解放者", "longrange": "戦術射手",
    "loopshooter": "旋輪射手", "lord": "領主", "merchant": "行商人", "musha": "武者",
    "mystic": "秘術師", "phalanx": "法陣術師", "physician": "医師", "pioneer": "先駆兵",
    "primcaster": "本源術師", "protector": "重盾衛士", "pusher": "推撃手", "reaper": "鎌撃士",
    "reaperrange": "散弾射手", "ringhealer": "群癒師", "ritualist": "祭儀師", "shotprotector": "哨戒衛士",
    "siegesniper": "破城射手", "slower": "緩速師", "splashcaster": "拡散術師", "stalker": "潜伏者",
    "summoner": "召喚師", "sword": "剣豪", "tactician": "戦術家", "traper": "罠師",
    "underminer": "呪詛師", "unyield": "破壊者", "wandermedic": "放浪医",
    # ★★★ 他にもあれば追加！キー名(英語ID)と日本語名を正確に！ ★★★
}
print(f"読み込んだ職分日本語マップ: {len(archetype_jp_map)} 件")

# --- レアリティ変換用辞書 ---
# "TIER_6" -> 6 のように変換するため
rarity_map = {
    "TIER_1": 1,
    "TIER_2": 2,
    "TIER_3": 3,
    "TIER_4": 4,
    "TIER_5": 5,
    "TIER_6": 6,
}

# blackboard_list を引数で受け取るように変更！
def replace_skill_value(match, blackboard_list):
    """スキル説明の {...} を blackboard の値で置換する関数 (ver 4: 大文字小文字無視)"""
    full_match = match.group(0)
    key_with_format = match.group(1)
    parts = key_with_format.split(':')
    key_from_desc = parts[0] # 説明文から取ったキー (例: 大文字混じり)
    format_str = parts[1] if len(parts) > 1 else None

    # blackboard から lookup_key で値を探す
    value = None
    # ★★★ 大文字・小文字を無視して blackboard を検索！ ★★★
    key_from_desc_lower = key_from_desc.lower() # 検索キーを小文字に変換
    for item in blackboard_list:
        bb_key = item.get('key')
        if bb_key and bb_key.lower() == key_from_desc_lower: # blackboardのキーも小文字にして比較！
            value = item.get('value')
            break # 見つかったらループ終了

    if value is not None:
        try:
            # フォーマット指定に基づいて数値を文字列に変換 (符号は元の値に従う)
            num_value = float(value) # 数値に変換
            if format_str == '0%': return f"{num_value:.0%}" # 例: -0.6 -> -60%
            elif format_str == '0.0%': return f"{num_value:.1%}" # 例: 0.155 -> 15.5%
            elif format_str == '0':
                 if num_value == int(num_value): return f"{int(num_value)}"
                 else: return f"{num_value}" # 小数点以下も表示
            elif format_str == '0.0': return f"{num_value:.1f}"

            else:
                 if num_value == int(num_value): return f"{int(num_value)}"
                 else: return f"{num_value}"

        except (ValueError, TypeError) as format_e:
             print(f"  Warning: Formatting error for key '{key}', value '{value}', format '{format_str}': {format_e}")
             return f"{value}" # フォーマット失敗時は元の値(数値)を文字列にして返す

    else:
        # Blackboard にキーがなかった場合
        print(f"  Warning: Key '{key}' not found in blackboard for placeholder '{full_match}'")
        return full_match # 元の {...} をそのまま返す

char_table_path = os.path.join(data_repo_path, 'ja_JP', 'gamedata', 'excel', 'character_table.json')
skill_table_path = os.path.join(data_repo_path, 'ja_JP', 'gamedata', 'excel', 'skill_table.json')
handbook_table_path = os.path.join(data_repo_path, 'ja_JP', 'gamedata', 'excel', 'handbook_info_table.json')
team_table_path = os.path.join(data_repo_path, 'ja_JP', 'gamedata', 'excel', 'handbook_team_table.json')
# 他に uniequip_table.json (モジュール), talent_table.json (素質) なども必要なら追加

# --- ② JSONファイル読み込み ---
try:
    with open(char_table_path, 'r', encoding='utf-8') as f:
        character_data = json.load(f)
    print(f"読み込み成功: {os.path.basename(char_table_path)}")

    # スキルデータも読み込む (IDで参照するため)
    with open(skill_table_path, 'r', encoding='utf-8') as f:
        skill_data = json.load(f)
    print(f"読み込み成功: {os.path.basename(skill_table_path)}")

    # ハンドブックデータも読み込む (IDで参照するため)
    with open(handbook_table_path, 'r', encoding='utf-8') as f:
        handbook_data = json.load(f)
    print(f"読み込み成功: {os.path.basename(handbook_table_path)}")

    # 所属・出身テーブルの読み込み
    with open(team_table_path, 'r', encoding='utf-8') as f: 
        team_data = json.load(f)
    print(f"読み込み成功: {os.path.basename(team_table_path)}")

    # 他のJSONも必要なら読み込む
    # with open(talent_table_path, 'r', encoding='utf-8') as f:
    #     talent_data = json.load(f)

except FileNotFoundError as e:
    print(f"エラー: JSONファイルが見つかりません！ パス設定を確認してください。: {e}")
    exit()
except json.JSONDecodeError as e:
    print(f"エラー: JSONファイルの形式が正しくありません。: {e}")
    exit()

# ---  データベース接続 ---
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# --- ★★★ 新しい organizations テーブルにデータを挿入 ★★★ ---
print(f"--- organizations テーブルにデータを挿入中 ---")
org_insert_count = 0
ORGANIZATIONS_TABLE = 'organizations' # テーブル名 (create_db.py と合わせる)

# team_data (handbook_team_table.jsonの中身) をループして organizations テーブルに挿入
if team_data: # team_data が読み込めていれば処理
    try:
        for org_id, org_info in team_data.items():
            # ★ handbook_team_table.json の構造に合わせてキー名を確認・修正！ ★
            # id, name, color, order_num は handbook_team_table にあるはず
            id = org_info.get('powerId')      # 'ursus' とか 'rhodes' とか
            name = org_info.get('powerName')    # 'ウルサス' とか 'ロドス・アイランド' とか
            color = org_info.get('color')       # 色コード
            order_num = org_info.get('orderNum') # 並び順

            # ★★★ description, lore, type は handbook_team_table.json だけでは分からない！ ★★★
            # 後で add_org_details.py などで手動または別のデータソースから補完する前提。
            # ここでは一旦 None を入れる。
            type = None       # 組織のタイプ ('Nation', 'Faction', 'Team' など)
            description = None # 簡単な説明
            lore = None        # 詳細な設定や歴史

            # ID と Name は必須なので、もし取れなかったらスキップ
            if not id or not name:
                 print(f"  Warning: Skipping organization with missing ID or name: ID='{id}', Name='{name}'")
                 continue

            # ★★★ データベースに挿入 ★★★
            # organizations テーブルのCREATE TABLE 文とカラム名を合わせる！ (7個のカラム)
            sql = f"""
                INSERT OR REPLACE INTO {ORGANIZATIONS_TABLE}
                (id, name, type, description, lore, color, order_num)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            # タプルに値を順番に詰める (None もそのまま渡す)
            cursor.execute(sql, (id, name, type, description, lore, color, order_num))
            org_insert_count += 1

        # organizations テーブルへの変更をコミット (operators と一緒に最後にまとめてもOK)
        # conn.commit()
        print(f"organizations テーブルに {org_insert_count} 件挿入/置換しました。")

    except Exception as e:
        print(f"--- エラー発生 --- organizations テーブル挿入中 ---")
        print(f"エラー内容: {e}")
        print("------------------------------------------------")


# --- ⑤ データ処理と挿入 (オペレーターのループ) ---
insert_count = 0
for char_id, op_data in character_data.items():
    # トークンや召喚物などをスキップする条件を入れる (例: 'char_xxx' 形式じゃないIDは飛ばす)
    if not char_id.startswith('char_') or op_data.get('isNotObtainable', False) or not op_data.get('name'):
        continue
    # isNotObtainable が True のキャラ (敵とか？) も飛ばす？
    if op_data.get('isNotObtainable', False):
        continue
    # 名前がないデータは基本的におかしいのでスキップ
    if not op_data.get('name'):
        continue

    try:
        # === ③character_table.json から取得 ===
        name = op_data.get('name')
        rarity_str = op_data.get('rarity')
        rarity = rarity_map.get(rarity_str)
        op_class_id = op_data.get('profession')
        archetype_id = op_data.get('subProfessionId')
        item_usage = op_data.get('itemUsage', '')
        item_desc = op_data.get('itemDesc', '')
        group_id = op_data.get('groupId') # 例: 'penguin'
        nation_id = op_data.get('nationId') # 例: 'lungmen'
        team_id = op_data.get('teamId') # 'action4' などを取得

        # 手作り辞書(archetype_jp_map)を使って日本語名を取得 (なければ元のID)
        archetype_name_jp = archetype_jp_map.get(archetype_id, archetype_id)
        # ↓↓↓ この行を追加！ class_jp_map を使って日本語名を取得！ ↓↓↓
        op_class_jp = class_jp_map.get(op_class_id, op_class_id)

        # team_data は事前に読み込んでおく (前のコード参照)
        affiliation_name = team_data.get(group_id, {}).get('powerName') if group_id else None
        # groupId がなければ nationId を所属とする (ロドスなど)
        if not affiliation_name and nation_id:
            affiliation_name = team_data.get(nation_id, {}).get('powerName')

        birthplace_name = team_data.get(nation_id, {}).get('powerName') if nation_id else None

        team_name = None # 初期値は None
        team_name = team_data.get(team_id, {}).get('powerName') if team_id else None

        # === handbook_info_table.json から取得 ===
        op_handbook = handbook_data.get('handbookDict', {}).get(char_id)
        # 初期値を設定
        race = None # ★★★ character_table から race を取得するのをやめて、ここで初期化 ★★★
        physical_strength, combat_skill, mobility, endurance, tactical_acumen, arts_adaptability = [None] * 6 # 初期化
        profile_summary_parts = []
        lore_notes_parts = [item_usage, item_desc] # itemUsage/Desc を最初に入れる

        if op_handbook and op_handbook.get('storyTextAudio'):
            print(f"\n--- Processing Handbook for: {name} ---") # ★ デバッグ: ハンドブック処理開始
            for section in op_handbook['storyTextAudio']:
                title = section.get('storyTitle')
                story_text = section.get('stories', [{}])[0].get('storyText', '')
                if not title or not story_text: continue

                print(f"  Found Section: '{title}'") # ★ デバッグ: 見つかったセクション名

                # --- ★★★ 基礎情報から種族を抽出 ★★★ ---
                if title == "基礎情報":
                    print(f"    Parsing '基礎情報'...") # ★ デバッグ
                    try:
                        lines = story_text.strip().split('\n')
                        # print(f"      Lines: {lines}") # ★ デバッグ: 行リスト確認
                        for line in lines:
                            if line.startswith('【種族】'):
                                race = line.split('】', 1)[1].strip() # 【種族】の後ろを取得
                                print(f"      ---> Race Found: {race}") # ★ デバッグ: 取得した種族を表示
                                found_race = True
                                break # 見つかったらループを抜ける
                        if not found_race:
                             print("      ---> Race keyword '【種族】' not found in lines.") # ★ デバッグ
                    except Exception as parse_e:
                        print(f"      ---> Error parsing 種族: {parse_e}")

                # 能力測定のパース
                if title == "能力測定":
                    print(f"    Parsing '能力測定'...") # ★ デバッグ
                    try:
                        stats = {}
                        lines = story_text.strip().split('\n')
                        # print(f"      Lines: {lines}") # ★ デバッグ: 行リスト確認
                        for line in lines:
                            if '】' in line:
                                key_part, value_part = line.split('】', 1)
                                stats[key_part.strip('【')] = value_part.strip()

                                # print(f"        Parsed Stat - Key: '{key}', Value: '{value}'") # ★ デバッグ: パースした値
                        print(f"      Stats Dict: {stats}") # ★ デバッグ: stats辞書の中身確認
                        physical_strength = stats.get('物理強度')
                        combat_skill = stats.get('戦場機動')
                        mobility = stats.get('生理的耐性')
                        endurance = stats.get('戦術立案')
                        tactical_acumen = stats.get('戦闘技術')
                        arts_adaptability = stats.get('アーツ適性')

                    except Exception as parse_e:
                        print(f"  Warning: Failed to parse 能力測定 for {name}: {parse_e}")

                # プロファイル要約用
                elif title in ["個人履歴", "第一資料"]:
                    profile_summary_parts.append(story_text)
                # Lore用
                elif title in ["第二資料", "第三資料", "第四資料", "昇進記録"]:
                    lore_notes_parts.append(f"--- {title} ---\n{story_text}")
            else:
                # ★★★ ハンドブックデータが見つからなかった時に表示 ★★★
                print(f"\n--- No Handbook Data found for: {name} ({char_id}) ---")

        profile_summary = "\n\n".join(filter(None, profile_summary_parts))
        lore_notes = "\n\n".join(filter(None, lore_notes_parts))

        # === ④skill_table.json からスキル情報を取得 ===
        skills = op_data.get('skills', [])
        s1_name, s1_desc = None, None
        s2_name, s2_desc = None, None
        s3_name, s3_desc = None, None
        # skill_data は事前に読み込んでおく
        # --- スキル1 ---
        if len(skills) >= 1 and skills[0] and skills[0].get('skillId'):
            skill_id = skills[0]['skillId']
            skill_info = skill_data.get(skill_id)
            if skill_info and skill_info.get('levels') and len(skill_info['levels']) > 0:
                last_level_data = skill_info['levels'][-1]
                s1_name = last_level_data.get('name')
                raw_desc = last_level_data.get('description')
                blackboard = last_level_data.get('blackboard', []) # このスキルのblackboardを取得

                if raw_desc:
                    cleaned_desc = re.sub(r'<.*?>', '', raw_desc)
                    cleaned_desc = re.sub(r'\$.*?>', '', cleaned_desc)

                    # ★★★ lambda を使って、現在の blackboard を関数に渡す！ ★★★
                    final_desc = re.sub(r'{([^}:]+(?::[\w.%]+)?)}',
                                        lambda m: replace_skill_value(m, blackboard), # ここ！
                                        cleaned_desc)
                    s1_desc = final_desc.strip()

        # --- スキル2 (同様に) ---
        if len(skills) >= 2 and skills[1] and skills[1].get('skillId'):
             skill_id = skills[1]['skillId']
             skill_info = skill_data.get(skill_id)
             if skill_info and skill_info.get('levels') and len(skill_info['levels']) > 0:
                 last_level_data = skill_info['levels'][-1]
                 s2_name = last_level_data.get('name')
                 raw_desc = last_level_data.get('description')
                 blackboard = last_level_data.get('blackboard', []) # スキル2のblackboard
                 if raw_desc:
                     cleaned_desc = re.sub(r'<.*?>', '', raw_desc)
                     cleaned_desc = re.sub(r'\$.*?>', '', cleaned_desc)
                     # ★★★ lambda を使って、現在の blackboard を関数に渡す！ ★★★
                     final_desc = re.sub(r'{([^}:]+(?::[\w.%]+)?)}',
                                         lambda m: replace_skill_value(m, blackboard), # ここ！
                                         cleaned_desc)
                     s2_desc = final_desc.strip()

        # --- スキル3 (同様に) ---
        if len(skills) >= 3 and skills[2] and skills[2].get('skillId'):
             skill_id = skills[2]['skillId']
             skill_info = skill_data.get(skill_id)
             if skill_info and skill_info.get('levels') and len(skill_info['levels']) > 0:
                 last_level_data = skill_info['levels'][-1]
                 s3_name = last_level_data.get('name')
                 raw_desc = last_level_data.get('description')
                 blackboard = last_level_data.get('blackboard', []) # スキル3のblackboard
                 if raw_desc:
                     cleaned_desc = re.sub(r'<.*?>', '', raw_desc)
                     cleaned_desc = re.sub(r'\$.*?>', '', cleaned_desc)
                     # ★★★ lambda を使って、現在の blackboard を関数に渡す！ ★★★
                     final_desc = re.sub(r'{([^}:]+(?::[\w.%]+)?)}',
                                         lambda m: replace_skill_value(m, blackboard), # ここ！
                                         cleaned_desc)
                     s3_desc = final_desc.strip()

        # === ⑤talent_table.json などから素質を取得 ===
        # talents キーがあるはずなので、スキルと同じように処理する
        talents = op_data.get('talents', [])
        t1_name, t1_desc = None, None
        t2_name, t2_desc = None, None
        # ... 素質データを talent_table.json (仮) から取得する処理 ...
        # --- 1つ目の素質 ---
        if len(talents) >= 1 and talents[0] and talents[0].get('candidates'):
            # candidates リストが空でないことを確認
            if len(talents[0]['candidates']) > 0:
                # candidates リストの最後の要素 (最新の強化状態) を取得
                last_candidate = talents[0]['candidates'][-1]
                t1_name = last_candidate.get('name')
                raw_talent_desc = last_candidate.get('description')
                talent_blackboard = last_candidate.get('blackboard', []) # 素質用のblackboardを取得

                if raw_talent_desc:
                    # スキル説明と同じようにクリーニング＆置換
                    cleaned_talent_desc = re.sub(r'<.*?>', '', raw_talent_desc)
                    cleaned_talent_desc = re.sub(r'\$.*?>', '', cleaned_talent_desc)
                    # ★★★ 前に作った replace_skill_value 関数を再利用！ ★★★
                    final_talent_desc = re.sub(r'{([^}:]+(?::[\w.%]+)?)}',
                                               lambda m: replace_skill_value(m, talent_blackboard),
                                               cleaned_talent_desc)
                    t1_desc = final_talent_desc.strip()

        # --- 2つ目の素質 (1つ目と全く同じロジック) ---
        if len(talents) >= 2 and talents[1] and talents[1].get('candidates'):
            if len(talents[1]['candidates']) > 0:
                last_candidate = talents[1]['candidates'][-1]
                t2_name = last_candidate.get('name')
                raw_talent_desc = last_candidate.get('description')
                talent_blackboard = last_candidate.get('blackboard', []) # 2つ目の素質用のblackboard
                if raw_talent_desc:
                    cleaned_talent_desc = re.sub(r'<.*?>', '', raw_talent_desc)
                    cleaned_talent_desc = re.sub(r'\$.*?>', '', cleaned_talent_desc)
                    # ★★★ replace_skill_value 関数を再利用！ ★★★
                    final_talent_desc = re.sub(r'{([^}:]+(?::[\w.%]+)?)}',
                                               lambda m: replace_skill_value(m, talent_blackboard),
                                               cleaned_talent_desc)
                    t2_desc = final_talent_desc.strip()

        # === ⑥ データベースに挿入 ===
        # SQL文: operatorsテーブルの全カラム名を指定し、VALUES に ? をカラム数分書く！ (26個！)
        sql = """
            INSERT OR REPLACE INTO operators (
                name, rarity, operator_class, archetype, affiliation, team, race, birthplace,
                physical_strength, combat_skill, mobility, endurance, tactical_acumen, arts_adaptability,
                profile_summary, lore_notes,
                skill1_name, skill1_desc, skill2_name, skill2_desc, skill3_name, skill3_desc,
                talent1_name, talent1_desc, talent2_name, talent2_desc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        # 実行: 上のSQL文のカラム名の順番に合わせて、取得した変数を入れたタプルを渡す！
        #      取得できなかった情報は None が入るので、DBには NULL として保存される
        cursor.execute(sql, (
            name,              # 1. name
            rarity,            # 2. rarity
            op_class_jp,       # 3. operator_class
            archetype_name_jp, # 4. archetype (日本語名)
            affiliation_name,  # 5. affiliation (日本語名)
            team_name,         # 6. team (日本語名)
            race,              # 7. race (基礎情報から取得)
            birthplace_name,   # 8. birthplace (日本語名)
            physical_strength, # 9. physical_strength (能力測定から取得)
            combat_skill,      # 10. combat_skill (能力測定から取得)
            mobility,          # 11. mobility (能力測定から取得)
            endurance,         # 12. endurance (能力測定から取得)
            tactical_acumen,   # 13. tactical_acumen (能力測定から取得)
            arts_adaptability, # 14. arts_adaptability (能力測定から取得)
            profile_summary,   # 15. profile_summary (ハンドブックから結合)
            lore_notes,        # 16. lore_notes (ハンドブック等から結合)
            s1_name,           # 17. skill1_name
            s1_desc,           # 18. skill1_desc (クリーニング後)
            s2_name,           # 19. skill2_name
            s2_desc,           # 20. skill2_desc (クリーニング後)
            s3_name,           # 21. skill3_name
            s3_desc,           # 22. skill3_desc (クリーニング後)
            t1_name,           # 23. talent1_name
            t1_desc,           # 24. talent1_desc (クリーニング後)
            t2_name,           # 25. talent2_name
            t2_desc            # 26. talent2_desc (クリーニング後)
        ))
        insert_count += 1
        # print(f"挿入/置換: {name}") # デバッグ時以外はコメントアウト

    except Exception as e:
        operator_name_for_error = name if 'name' in locals() and name else f"char_id: {char_id}"
        print(f"--- エラー発生 --- オペレーター: {operator_name_for_error} ---")
        print(f"エラー内容: {e}")
        print("------------------------------------------------")


# --- ⑥ 完了処理 ---
conn.commit()
conn.close()
print(f"処理完了！ {insert_count} 件のオペレーター情報をデータベースに挿入/置換しました。")
