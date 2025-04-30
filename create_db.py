# create_db.py
import sqlite3
import os

DB_FILENAME = 'arknights_data.db'
OPERATORS_TABLE = 'operators'
script_dir = os.path.dirname(__file__) # このスクリプトがある場所
db_path = os.path.join(script_dir, DB_FILENAME)
print(f"データベースファイルのパス: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# operators テーブルを作成 (IF NOT EXISTS で安全に)
create_table_sql = f"""
CREATE TABLE IF NOT EXISTS {OPERATORS_TABLE} (
    name TEXT PRIMARY KEY,
    rarity INTEGER,
    operator_class TEXT,
    archetype TEXT,
    affiliation TEXT,
    team TEXT,
    race TEXT,
    birthplace TEXT,
    physical_strength TEXT,
    combat_skill TEXT,
    mobility TEXT,
    endurance TEXT,
    tactical_acumen TEXT,
    arts_adaptability TEXT,
    profile_summary TEXT,
    lore_notes TEXT,
    skill1_name TEXT, skill1_desc TEXT,
    skill2_name TEXT, skill2_desc TEXT,
    skill3_name TEXT, skill3_desc TEXT,
    talent1_name TEXT, talent1_desc TEXT,
    talent2_name TEXT, talent2_desc TEXT
)
"""

# ★★★ 新しい organizations テーブルを作成！ ★★★
ORGANIZATIONS_TABLE = 'organizations'

create_organizations_table_sql = f"""
CREATE TABLE IF NOT EXISTS {ORGANIZATIONS_TABLE} (
    id TEXT PRIMARY KEY,     -- 'ursus', 'rhodes', 'penguin' みたいなID
    name TEXT UNIQUE,        -- 'ウルサス', 'ロドス・アイランド', 'ペンギン急便' みたいな日本語名
    type TEXT,               -- 'Nation' (国), 'Faction' (勢力), 'Team' (チーム) みたいな分類
    description TEXT,        -- 組織の簡単な説明 (もしあれば)
    lore TEXT,               -- 組織に関する詳細な設定や歴史 (もしあれば)
    color TEXT,
    order_num INTEGER
);
"""
try:
    cursor.execute(create_organizations_table_sql) # ★新しいテーブルの作成を実行！
    print(f"テーブル '{ORGANIZATIONS_TABLE}' を確認/作成しました。")
except sqlite3.Error as e:
    print(f"テーブル '{ORGANIZATIONS_TABLE}' 作成中にエラーが発生しました: {e}")

try:
    cursor.execute(create_table_sql)
    print(f"テーブル '{OPERATORS_TABLE}' を確認/作成しました。")
except sqlite3.Error as e:
    print(f"テーブル作成中にエラーが発生しました: {e}")

conn.commit()
conn.close()
print("データベースの初期化処理が完了しました。")
