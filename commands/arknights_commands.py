# commands/arknights_commands.py
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3 # データベース用
import os # パス指定用
import re # テキスト解析用 (section抜き出しとか)

# データベースファイルのパス (my_bot フォルダにあるはず)
# このファイルは commands/ の中なので、../ で一つ上に戻る
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'arknights_data.db')

# ★★★ スキル/素質説明の {} を blackboard の値で置換する関数 (populate_db.py から移動) ★★★
# populate_db.py にも同じ関数が必要なら、そっちにも置いてね！
# この関数は populate_db.py と同じロジックだけど、黒板データを引数で受け取る
def replace_skill_value(match, blackboard_list):
    """スキル説明の {...} を blackboard の値で置換する関数"""
    full_match = match.group(0)
    key_with_format = match.group(1)
    parts = key_with_format.split(':')
    key = parts[0]
    format_str = parts[1] if len(parts) > 1 else None

    value = None
    # Blackboard から key で値を探す (大文字小文字無視)
    key_lower = key.lower()
    for item in blackboard_list:
        bb_key = item.get('key')
        if bb_key and bb_key.lower() == key_lower:
            value = item.get('value')
            break

    if value is not None:
        try:
            # フォーマット処理 (符号は元の値に従う)
            num_value = float(value)
            if format_str == '0%': return f"{num_value:.0%}"
            elif format_str == '0.0%': return f"{num_value:.1%}"
            elif format_str == '0':
                 if num_value == int(num_value): return f"{int(num_value)}"
                 else: return f"{num_value}"
            elif format_str == '0.0': return f"{num_value:.1f}"
            else:
                 if num_value == int(num_value): return f"{int(num_value)}"
                 else: return f"{num_value}"
        except (ValueError, TypeError):
             return f"{value}"
    else:
        # Blackboard にキーがなかった場合
        # print(f"  Warning: Key '{key}' not found in blackboard for placeholder '{full_match}'") # コマンド実行ログには出さない方が良いかも
        return full_match

class ArknightsCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = DB_PATH # データベースパスを保持

        # ★★★ 起動時にデータベースファイルが存在するか確認 (任意だけど推奨) ★★★
        if not os.path.exists(self.db_path):
             print(f"🚨 データベースファイルが見つかりません: {self.db_path}。Arknights検索コマンドは無効です。")
             self.db_available = False # DBが使えないフラグ
        else:
             try:
                 conn = sqlite3.connect(self.db_path)
                 cursor = conn.cursor()
                 cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='operators'")
                 table_exists = cursor.fetchone()
                 conn.close()
                 if table_exists:
                    print(f"✅ データベースファイル確認OK: {self.db_path}")
                    self.db_available = True # DBが使えるフラグ
                 else:
                    print(f"🚨 データベースファイル '{self.db_path}' は存在しますが、'operators' テーブルが見つかりません。populate_db.py は実行しましたか？")
                    self.db_available = False
             except sqlite3.Error as e:
                 print(f"🚨 データベース接続またはテーブル確認中にエラー: {e}")
                 print("🚨 Arknights検索コマンドは無効です。")
                 self.db_available = False


    # ★★★ /arknights_search (または /search) スラッシュコマンド定義 ★★★
    @app_commands.command(name="search", description="アークナイツのオペレーター情報を検索します。")
    @app_commands.describe(operator_name="検索したいオペレーターの名前（例：ジェシカ、ケルシー）")
    async def search(self, interaction: discord.Interaction, operator_name: str):
        await interaction.response.defer(ephemeral=False) # Thinky face を表示

        # DBが利用できない場合はここで終了
        if not self.db_available:
             await interaction.followup.send("🚨 データベースが利用できないため、オペレーター情報を検索できません。管理者に連絡してください。")
             return

        conn = None # データベース接続オブジェクト
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row # カラム名をキーにして結果にアクセスできるようになる (便利！)
            cursor = conn.cursor()

            # ★★★ オペレーター名を検索！(部分一致 & 大文字小文字区別なし) ★★★
            search_term = f"%{operator_name}%" # 前後に % を付けて部分一致
            # name LIKE ? で部分一致検索、COLLATE NOCASE で大文字小文字を区別しない
            cursor.execute("SELECT * FROM operators WHERE name LIKE ? COLLATE NOCASE", (search_term,))

            # ★★★ 結果の取得を fetchall に変更！ ★★★
            operators = cursor.fetchall() # 条件に合う行全てをリストで取得！

            # --- 結果の表示を件数で切り分ける ---
            num_results = len(operators) # 見つかった件数

            # ▼▼▼ 0件の場合 ▼▼▼
            if not operators: # リストが空かどうか (件数が0件) でチェック
                await interaction.followup.send(f"オペレーター「{operator_name}」に関する情報はない。名称を再確認してくれ。")
                return # 0件の場合はここで終了

            # ▼▼▼ 複数件見つかった場合 (2件以上) の最初メッセージ (任意) ▼▼▼
            if num_results > 1:
                 await interaction.followup.send(f"{num_results} 件のオペレーターが見つかった。それぞれの情報を表示する。")

            # ▼▼▼ 1件以上見つかった場合 (全てのオペレーターについてループして詳細表示) ▼▼▼
            # 見つかったオペレーターの数だけループして、一人ずつ詳細情報を表示する！
            # 0件の場合は上で return してるので、ここに来るのは1件以上の場合のみ。
            for i, op_row in enumerate(operators): # 見つかった全オペレーターについてループ
                # op_row がリストの中の各行データになる (sqlite3.Row オブジェクト)
                operator = op_row # 以降のコードで operator 変数が使えるように代入 (分かりやすさのため)


                # --- ▼▼▼ ここから、一人分の詳細情報を取り出す処理 (populate_db.py のロジックを移植！) ▼▼▼ ---
                # operator['カラム名'] で値にアクセスできる (sqlite3.Row は .get() 持ってないので注意)

                # 各カラムから値を取り出す
                name = operator['name']
                rarity = operator['rarity']
                op_class = operator['operator_class']
                archetype = operator['archetype']
                affiliation = operator['affiliation']
                team = operator['team'] # ★team カラムも追加したはず！
                race = operator['race']
                birthplace = operator['birthplace']

                # Ability Stats
                # None の可能性があるので、後で Embed に追加する前にチェックが必要
                physical_strength = operator['physical_strength']
                combat_skill = operator['combat_skill']
                mobility = operator['mobility']
                endurance = operator['endurance']
                tactical_acumen = operator['tactical_acumen']
                arts_adaptability = operator['arts_adaptability']

                # Profile Summary と Lore Notes (DBに結合されて保存されてるテキスト) を取得
                full_profile_text = operator['profile_summary'] # None になりうる
                full_lore_text = operator['lore_notes']       # None になりうる

                # ★★★ 必要なセクションだけを抽出するロジック ★★★
                # DBに保存したテキストを、もう一度 "--- タイトル ---" で分割し直す
                # 表示したいセクションのタイトルリスト (能力測定は除外)
                sections_to_include_in_text = ["基礎情報", "個人履歴", "健康診断"] # ★必要な資料のタイトルリスト

                extracted_text = "" # 表示用に抽出・整形したテキストを入れる変数

                # profile_summary と lore_notes を結合して全体テキストとして扱う (None チェックも含む)
                combined_text = ""
                if full_profile_text:
                    combined_text += full_profile_text
                if full_lore_text:
                    if combined_text: combined_text += "\n\n" # profile_summary と lore_notes の間に区切り線
                    combined_text += full_lore_text

                if combined_text:
                     # 各セクションのタイトルを正規表現で探す
                     section_pattern = re.compile(r'---\s*(.+?)\s*---\n(.*?)(?=\n---\s*.+?\s*---|\Z)', re.DOTALL)

                     # 全体テキストから、指定のタイトルにマッチするセクションを抽出
                     for match in section_pattern.finditer(combined_text):
                         title = match.group(1).strip() # タイトル部分 (例: "基礎情報")
                         text = match.group(2).strip()  # そのタイトルの下の本文

                         # 表示したいタイトルリストに含まれているかチェック
                         if title in sections_to_include_in_text:
                             # 見出し付きで抽出テキストに追加
                             if text: # 本文が空でなければ追加
                                 extracted_text += f"--- {title} ---\n{text}\n\n"

                # 抽出したテキストが空で、かつ fallback (profile_summary全体) が利用可能な場合
                fallback_profile = operator['profile_summary'] # DBから取得 (Noneになりうる)
                if not extracted_text and fallback_profile:
                     extracted_text = fallback_profile # fallback として profile_summary 全体を入れる
                     # タイトルがないので見出しは付けない

                # --- ▼▼▼ Embed 作成 ▼▼▼ ---
                # オペレーター一人につき Embed を一つ作成！
                embed = discord.Embed(
                    # タイトル: オペレーター名 (レアリティ)
                    title=f"オペレーター情報: {name} (★{rarity})",
                    # 基本情報: クラス/職分, 所属/出身地/種族/チームを description にまとめる
                    description=f"**クラス/職分:** {op_class} / {archetype}\n"
                                f"**所属:** {affiliation if affiliation else '不明'}" + (f" / **チーム:** {team}" if team else "") +
                                f"\n**出身:** {birthplace if birthplace else '不明'}" +
                                f"\n**種族:** {race if race else '不明'}",
                    color=discord.Color.blue() # 好きな色
                )

                # Ability Stats フィールドを追加 (取得できていれば)
                stats_list_text = [] # 表示用の文字列リスト
                # 各変数に値が入っているかチェックしてリストに追加
                # None や 'N/A' みたいな文字列は除外したい
                if physical_strength is not None and physical_strength != 'N/A': stats_list_text.append(f"物理強度:{physical_strength}")
                if combat_skill is not None and combat_skill != 'N/A': stats_list_text.append(f"戦場機動:{combat_skill}")
                if mobility is not None and mobility != 'N/A': stats_list_text.append(f"生理的耐性:{mobility}")
                if endurance is not None and endurance != 'N/A': stats_list_text.append(f"戦術立案:{endurance}")
                if tactical_acumen is not None and tactical_acumen != 'N/A': stats_list_text.append(f"戦闘技術:{tactical_acumen}")
                if arts_adaptability is not None and arts_adaptability != 'N/A': stats_list_text.append(f"アーツ適性:{arts_adaptability}")

                if stats_list_text:
                    embed.add_field(name="能力測定", value=" ".join(stats_list_text), inline=False)


                # 抽出したプロファイル・経歴テキストを Embed フィールドに追加
                if extracted_text:
                     # Embedのvalueは1024文字制限があるので分割が必要かも
                     # シンプルに、1024文字を超える場合は切り詰める
                     if len(extracted_text) > 1024:
                          # フィールド名は分割に合わせて変更が必要 (例: プロファイル・経歴 (続き))
                          # ここは Part 1, Part 2 とかに分割するロジックを入れるともっと良いけど、まずは簡易版
                          embed.add_field(name="プロファイル・経歴", value=extracted_text[:1020] + "...", inline=False)
                     else:
                          embed.add_field(name="プロファイル・経歴", value=extracted_text, inline=False)

                # スキル情報、素質情報も Embed フィールドとして追加するならここ！
                # populate_db.py で保存した sX_name, sX_desc, tX_name, tX_desc を利用
                if operator['skill1_name']:
                    embed.add_field(name=f"S1: {operator['skill1_name']}", value=operator['skill1_desc'] if operator['skill1_desc'] else "説明なし", inline=False)
                if operator['skill2_name']:
                    embed.add_field(name=f"S2: {operator['skill2_name']}", value=operator['skill2_desc'] if operator['skill2_desc'] else "説明なし", inline=False)
                if operator['skill3_name']:
                    embed.add_field(name=f"S3: {operator['skill3_name']}", value=operator['skill3_desc'] if operator['skill3_desc'] else "説明なし", inline=False)
                if operator['talent1_name']:
                    embed.add_field(name=f"素質1: {operator['talent1_name']}", value=operator['talent1_desc'] if operator['talent1_desc'] else "説明なし", inline=False)
                if operator['talent2_name']:
                    embed.add_field(name=f"素質2: {operator['talent2_name']}", value=operator['talent2_desc'] if operator['talent2_desc'] else "説明なし", inline=False)


                # --- ▼▼▼ Embed 応答 ▼▼▼ ---
                # ループの中なので、オペレーター一人につきEmbedを一つ送信！
                await interaction.followup.send(embed=embed)


        except Exception as e:
            # エラー発生時はログに出力して、ユーザーにも通知
            print(f"❌ /search コマンド実行中にエラー: {e}", flush=True)
            await interaction.followup.send("検索中にエラーが発生しました。", ephemeral=True)

        finally:
            # データベース接続を必ず閉じる
            if conn:
                conn.close()

# ★★★ Cogをロードするための setup 関数 ★★★
# main.py の load_extensions で 'commands.arknights_commands' を追加すること！
async def setup(bot: commands.Bot):
    await bot.add_cog(ArknightsCommands(bot))