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
                # 簡単なクエリでテーブルが存在するか確認 (DBファイルはあってもテーブルがない場合も)
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

    # ★★★ /search スラッシュコマンド定義 ★★★
    @app_commands.command(name="search", description="アークナイツのオペレーター情報を検索します。")
    @app_commands.describe(operator_name="検索したいオペレーターの名前（例：ケルシー）")
    async def arknights_search(self, interaction: discord.Interaction, operator_name: str):
        await interaction.response.defer(ephemeral=False)

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

            operators = cursor.fetchall() # 条件に合うもの全部を取得！ リストになる！

            # --- 結果の表示を件数で切り分ける ---
            num_results = len(operators) # 見つかった件数

            # ▼▼▼ 0件の場合 ▼▼▼
            if not operators: # リストが空かどうかでチェック
                await interaction.followup.send(f"オペレーター「{operator_name}」に関する情報はない。名称を再確認してくれ。")
                return

            # ▼▼▼ 複数件見つかった場合 (2件以上) ▼▼▼
            if num_results > 1:
                # Embed を新しく作って、見つかったオペレーターをリストアップする！
                embed = discord.Embed(
                    title=f"オペレーター検索結果 ({num_results}件): 「{operator_name}」",
                    description="以下のオペレーターが見つかった。\n詳細を知りたい場合は、より正確な名称で再度検索したまえ。", # ケルシー風メッセージ
                    color=discord.Color.orange() # オレンジ色とか？
                )

            # 見つかったオペレーターのリストを Embed のフィールドに追加
                # 全部追加すると長すぎるかもしれないので、例えば最初の10件とかに制限
                max_display_results = 15 # 表示する最大件数
                for i, op_row in enumerate(operators[:max_display_results]): # 最初の数件だけループ
                    name = op_row['name']
                    rarity = op_row['rarity']
                    op_class = op_row['operator_class']
                    archetype = op_row['archetype']

                    # フィールド名を連番にする (1. オペレーター名)
                    field_name = f"{i+1}. {name}"
                    # フィールドの値に、基本情報を表示 (簡潔に！)
                    field_value = f"★{rarity} / {op_class} {archetype}"
                    if op_row['affiliation']: field_value += f" / 所属: {op_row['affiliation']}" # None なら表示しない
                    if op_row['birthplace']: field_value += f" / 出身: {op_row['birthplace']}" # None なら表示しない

                    embed.add_field(name=field_name, value=field_value, inline=False) # インラインは Falseで見やすく

                # もし表示制限件数より多く見つかったら補足
                if num_results > max_display_results:
                     embed.set_footer(text=f"他 {num_results - max_display_results} 件の結果がある。より絞り込んだ名称で再度検索せよ。") # ケルシー風

                # この Embed をユーザーに送信！
                await interaction.followup.send(embed=embed)

                return # 複数件表示で処理終了

            # ▼▼▼ 1件だけ見つかった場合 (Implicit else) ▼▼▼
            # operators リストには1件だけ入ってるので、operator = operators[0] として処理開始
            operator = operators[0] # ★ リストから唯一の行を取り出す

            # 各カラムから値を取り出す
            name = operator['name']
            rarity = operator['rarity']
            op_class = operator['operator_class']
            archetype = operator['archetype']
            affiliation = operator['affiliation']
            team = operator['team'] # ★team カラムも追加したはず！
            race = operator['race']
            birthplace = operator['birthplace']

            physical_strength = operator['physical_strength']
            combat_skill = operator['combat_skill']
            mobility = operator['mobility']
            endurance = operator['endurance']
            tactical_acumen = operator['tactical_acumen']
            arts_adaptability = operator['arts_adaptability']

            # Profile Summary と Lore Notes (結合されたテキスト) を取得
            full_profile_text = operator['profile_summary']
            full_lore_text = operator['lore_notes']

            # 今回表示したいセクションのタイトルリスト (能力測定は除外)
            sections_to_include_in_text = ["基礎情報", "個人履歴", "能力測定", "健康診断", "第一資料"]

            extracted_text = ""
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


            # 抽出したテキストが空で、かつ profile_summary 自体には何かテキストが入ってる場合、fallback として profile_summary 全体を表示する
            fallback_profile = operator['profile_summary'] # DBから取得 (Noneになる可能性あり)
            if not extracted_text and fallback_profile: # 何も抽出できなかった & fallback がNoneでないか空でない
                extracted_text = fallback_profile # fallback として profile_summary 全体を入れる

            # --- ▼▼▼ Embed 作成 ▼▼▼ ---
            # 基本情報
            embed = discord.Embed(
                title=f"オペレーター情報: {name} (★{rarity})",
                description=f"**クラス/職分:** {op_class} / {archetype}\n**所属/出身:** {affiliation if affiliation else '不明'} / {birthplace if birthplace else '不明'}\n**種族:** {race if race else '不明'}",
                color=discord.blue() # 好きな色
            )
            # team もあれば description に追加しても良いかも
            if team:
                embed.description += f"\n**チーム:** {team}" # affiliation/birthplace の後に追加
            
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
                    # フィールド名は分割に合わせて変更が必要
                    embed.add_field(name="プロファイル・経歴 (続き)", value=extracted_text[:1020] + "...", inline=False)
                else:
                    embed.add_field(name="プロファイル・経歴", value=extracted_text, inline=False)

            # --- ▼▼▼ Embed 応答 ▼▼▼ ---
            await interaction.followup.send(embed=embed)

        except Exception as e:
            # エラー発生時はログに出力して、ユーザーにも通知
            print(f"❌ /arknights_search コマンド実行中にエラー: {e}", flush=True)
            await interaction.followup.send("検索中にエラーが発生しました。", ephemeral=True)

        finally:
            # データベース接続を必ず閉じる
            if conn:
                conn.close()

# ★★★ Cogをロードするための setup 関数 ★★★
# main.py の load_extensions で 'commands.arknights_commands' を追加すること！
async def setup(bot: commands.Bot):
    await bot.add_cog(ArknightsCommands(bot))