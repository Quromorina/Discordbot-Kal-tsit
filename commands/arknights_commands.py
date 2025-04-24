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
        else:
             print(f"✅ データベースファイル確認OK: {self.db_path}")

    # ★★★ /arknights_search スラッシュコマンド定義 ★★★
    @app_commands.command(name="arknights_search", description="アークナイツのオペレーター情報を検索します。")
    @app_commands.describe(operator_name="検索したいオペレーターの名前（例：ジェシカ）")
    async def arknights_search(self, interaction: discord.Interaction, operator_name: str):
        # Thinky face を表示 (処理に時間かかるかもなので)
        await interaction.response.defer(ephemeral=False) # ephemeral=True だと本人にしか見えない

        conn = None # データベース接続オブジェクト
        try:
            # DBファイルがない場合はエラーメッセージを返す
            if not os.path.exists(self.db_path):
                 await interaction.followup.send("🚨 データベースファイルが見つかりません。管理者に連絡してください。")
                 return

            # データベースに接続
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row # カラム名をキーにして結果にアクセスできるようになる (便利！)
            cursor = conn.cursor()

            # ★★★ オペレーター名を検索！ (完全一致) ★★★
            # name=? は SQL のプレースホルダ。ユーザー入力を安全に渡す
            cursor.execute("SELECT * FROM operators WHERE name = ?", (operator_name,))
            operator = cursor.fetchone() # 1件だけ結果を取得 (見つからなければ None)

            # オペレーターが見つからなかった場合
            if not operator:
                await interaction.followup.send(f"オペレーター「{operator_name}」に関する情報はない。")
                return

            # --- ▼▼▼ データベースから取得した情報を整形 ▼▼▼ ---
            # operator['カラム名'] で値にアクセスできる
            name = operator['name']
            rarity = operator['rarity']
            op_class = operator['operator_class']
            archetype = operator['archetype']
            affiliation = operator['affiliation']
            race = operator['race']
            birthplace = operator['birthplace']

            # Ability Stats はそのまま取り出し
            # (None の可能性があるので .get() で安全にアクセス)
            physical_strength = operator.get('physical_strength')
            combat_skill = operator.get('combat_skill')
            mobility = operator.get('mobility')
            endurance = operator.get('endurance')
            tactical_acumen = operator.get('tactical_acumen')
            arts_adaptability = operator.get('arts_adaptability')

            # Profile Summary と Lore Notes (結合されたテキスト) を取得
            full_profile_text = operator.get('profile_summary', '')
            full_lore_text = operator.get('lore_notes', '')

            # ★★★ 必要なセクションだけを抽出するロジック ★★★
            # DBに保存したテキストを、もう一度 "--- タイトル ---" で分割し直す
            # 今回表示したいセクションのタイトルリスト
            sections_to_include = ["基礎情報", "能力測定", "個人履歴", "健康診断", "第一資料"]
            extracted_text = ""

            # profile_summary と lore_notes を結合して全体テキストとして扱う
            combined_text = ""
            if full_profile_text: combined_text += full_profile_text + "\n\n"
            if full_lore_text: combined_text += full_lore_text

            if combined_text:
                # 各セクションのタイトルを正規表現で探す
                # 例: --- 基礎情報 --- にマッチ
                # re.DOTALL は . が改行も含むようにするフラグ
                section_pattern = re.compile(r'---\s*(.+?)\s*---\n(.*?)(?=\n---\s*.+?\s*---|\Z)', re.DOTALL)

                # 全体テキストから、セクションごとにマッチさせる
                for match in section_pattern.finditer(combined_text):
                    title = match.group(1).strip() # タイトル部分 (例: "基礎情報")
                    text = match.group(2).strip() # 本文部分

                    # 表示したいタイトルリストに含まれているかチェック
                    if title in sections_to_include:
                        # 見出し付きで抽出テキストに追加
                        extracted_text += f"--- {title} ---\n{text}\n\n"

            # 抽出したテキストが空だったら、 fallback として profile_summary 全体を表示する
            if not extracted_text and operator.get('profile_summary'):
                 extracted_text = operator['profile_summary']
                 # タイトルがないので見出しは付けない

            # --- ▼▼▼ Embed 作成 ▼▼▼ ---
            # 基本情報
            embed = discord.Embed(
                title=f"オペレーター情報: {name} (★{rarity})",
                description=f"**クラス/職分:** {op_class} / {archetype}\n**所属/出身:** {affiliation if affiliation else '不明'} / {birthplace if birthplace else '不明'}\n**種族:** {race if race else '不明'}",
                color=discord.Color.blue() # 好きな色
            )

            # Ability Stats フィールドを追加 (取得できていれば)
            stats_list = []
            # (各変数に値が入っているかチェックしてリストに追加)
            # None や 'N/A' みたいな文字列は除外したい
            if physical_strength and physical_strength != 'N/A': stats_list.append(f"物理強度:{physical_strength}")
            if combat_skill and combat_skill != 'N/A': stats_list.append(f"戦場機動:{combat_skill}")
            if mobility and mobility != 'N/A': stats_list.append(f"生理的耐性:{mobility}")
            if endurance and endurance != 'N/A': stats_list.append(f"戦術立案:{endurance}") # ★カラム名間違い注意！
            if tactical_acumen and tactical_acumen != 'N/A': stats_list.append(f"戦闘技術:{tactical_acumen}")
            if arts_adaptability and arts_adaptability != 'N/A': stats_list.append(f"アーツ適性:{arts_adaptability}")

            # ★注意: populate_db.py の ability stat カラム名と、ここで使う変数名が一致してるか確認！
            # 例: DBカラム名 tactical_acumen -> 変数 tactical_acumen

            if stats_list:
                embed.add_field(name="能力測定", value=" ".join(stats_list), inline=False)

            # 抽出したプロファイル・経歴テキストを追加
            if extracted_text:
                 # Embedのvalueは1024文字制限があるので分割が必要かも
                 # シンプルに、1024文字を超える場合は切り詰める
                 if len(extracted_text) > 1024:
                      embed.add_field(name="プロファイル・経歴", value=extracted_text[:1020] + "...", inline=False)
                 else:
                      embed.add_field(name="プロファイル・経歴", value=extracted_text, inline=False)
                 # もっとちゃんと分割するなら、テキストを1024文字以下に分割して、複数のフィールドを追加する必要がある

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