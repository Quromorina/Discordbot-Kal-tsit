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

# ★★★ スキル/素質説明の {} を blackboard の値で置換する関数 (populate_db.py にも必要なら置いてね) ★★★
def replace_skill_value(match, blackboard_list):
    # ... (前のコードと同じ。populate_db.py と共通の関数) ...
    full_match = match.group(0)
    key_with_format = match.group(1)
    parts = key_with_format.split(':')
    key = parts[0]
    format_str = parts[1] if len(parts) > 1 else None

    value = None
    key_lower = key.lower()
    for item in blackboard_list:
        bb_key = item.get('key')
        if bb_key and bb_key.lower() == key_lower:
            value = item.get('value')
            break

    if value is not None:
        try:
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
    @app_commands.command(name="search", description="アークナイツのオペレーター情報を検索します（完全一致）。") # 説明文を変更
    @app_commands.describe(operator_name="検索したいオペレーターの名前（例：ジェシカ）")
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

            # ★★★ オペレーター名を検索！(完全一致に戻す) ★★★
            # name=? で完全一致検索
            cursor.execute("SELECT * FROM operators WHERE name = ? COLLATE NOCASE", (operator_name,)) # COLLATE NOCASE はそのまま使う

            # ★★★ 結果の取得を fetchone に戻す！ ★★★
            operator = cursor.fetchone() # ヒットした最初の1件だけを取得！

            # --- 結果の表示 ---
            # ▼▼▼ オペレーターが見つからなかった場合 ▼▼▼
            if not operator: # 結果が None かどうかでチェック
                await interaction.followup.send(f"オペレーター「{operator_name}」に関する情報はない。名称が正確か再確認してくれ。") # メッセージ変更
                return # 見つからなかった場合はここで終了

            # ▼▼▼ オペレーターが1件見つかった場合 (検索結果が None でなかった場合) ▼▼▼
            # ここに、前のコードの「--- ▼▼▼ データベースから取得した情報を整形 ▼▼▼ ---」以降の全てが入る！

            # --- ▼▼▼ データベースから取得した情報を整形 ▼▼▼ ---
            # operator['カラム名'] で値にアクセス！ .get() や () は使わない！

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
            # None の可能性があるので、Embed に追加する前にチェックが必要
            physical_strength = operator['physical_strength']
            combat_skill = operator['combat_skill']
            mobility = operator['mobility']
            endurance = operator['endurance']
            tactical_acumen = operator['tactical_acumen']
            arts_adaptability = operator['arts_adaptability']

            # Profile Summary と Lore Notes (DBに結合されて保存されてるテキスト) を取得
            full_profile_text = operator['profile_summary'] # None になりうる
            full_lore_text = operator['lore_notes']       # None になりうる

            # ★★★ 必要なセクションだけを抽出するロジック (修正版) ★★★
            # 今回表示したいセクションのタイトルリスト (能力測定は除外)
            sections_to_include_in_text = ["基礎情報", "個人履歴", "健康診断"] # ★★★ ここを修正！ ★★★

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
            if not extracted_text and fallback_profile: # 何も抽出できなかった & fallback がNoneでないか空でない
                extracted_text = fallback_profile # fallback として profile_summary 全体を入れる
                # タイトルがないので見出しは付けない

            # --- ▼▼▼ Embed 作成 ▼▼▼ ---
            # オペレーター一人につき Embed を一つ作成！
            embed = discord.Embed(
                title=f"オペレーター情報: {name} (★{rarity})",
                description=f"**クラス/職分:** {op_class} / {archetype}\n"
                            f"**所属:** {affiliation if affiliation else '不明'}" + (f" / **チーム:** {team}" if team else "") +
                            f"\n**出身:** {birthplace if birthplace else '不明'}" +
                            f"\n**種族:** {race if race else '不明'}",
                color=discord.Color.blue() # 好きな色
            )
            # team もあれば description に追加しても良いかも (上の f-string に組み込み済み)

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
                    embed.add_field(name="プロファイル・経歴", value=extracted_text[:1020] + "...", inline=False)
                else:
                    embed.add_field(name="プロファイル・経歴", value=extracted_text, inline=False)
                # もっとちゃんと分割するなら、テキストを1024文字以下に分割して、複数のフィールドを追加する必要がある
                # (例: title="プロファイル・経歴 Part 1", value=..., title="プロファイル・経歴 Part 2", value=...)

            # スキル情報、素質情報も Embed フィールドとして追加するならここ！
            # populate_db.py で保存した sX_name, sX_desc, tX_name, tX_desc を利用
            # DBから s1_name, s1_desc なども operator[...] で取得
            s1_name = operator['skill1_name']
            s1_desc = operator['skill1_desc']
            s2_name = operator['skill2_name']
            s2_desc = operator['skill2_desc']
            s3_name = operator['skill3_name']
            s3_desc = operator['skill3_desc']
            t1_name = operator['talent1_name']
            t1_desc = operator['talent1_desc']
            t2_name = operator['talent2_name']
            t2_desc = operator['talent2_desc']

            if s1_name:
                embed.add_field(name=f"S1: {s1_name}", value=s1_desc if s1_desc else "説明なし", inline=False)
            if s2_name:
                embed.add_field(name=f"S2: {s2_name}", value=s2_desc if s2_desc else "説明なし", inline=False)
            if s3_name:
                embed.add_field(name=f"S3: {s3_name}", value=s3_desc if s3_desc else "説明なし", inline=False)
            if t1_name:
                embed.add_field(name=f"素質1: {t1_name}", value=t1_desc if t1_desc else "説明なし", inline=False)
            if t2_name:
                embed.add_field(name=f"素質2: {t2_name}", value=t2_desc if t2_desc else "説明なし", inline=False)


            # --- ▼▼▼ Embed 応答 ▼▼▼ ---
            # 1件表示なので、Embed は最後に1つだけ送信！
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