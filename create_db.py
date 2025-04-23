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
try:
    cursor.execute(create_table_sql)
    print(f"テーブル '{OPERATORS_TABLE}' を確認/作成しました。")
except sqlite3.Error as e:
    print(f"テーブル作成中にエラーが発生しました: {e}")

conn.commit()
conn.close()
print("データベースの初期化処理が完了しました。")
