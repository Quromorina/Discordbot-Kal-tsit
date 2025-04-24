import discord
from discord.ext import commands
import google.generativeai as genai
import os
import re # メンションをキレイにするため
import sqlite3

# --- データベースファイルのパス ---
# このファイル (gemini_chat.py) が commands/ の中にあるので、
# データベース (my_bot 直下) へのパスは '..' で一つ上に戻る
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'arknights_data.db')

# --- ここから Cog クラス ---
class GeminiChat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = None # モデルは後で初期化
        self.db_path = DB_PATH # データベースパスを保持

        # ★★★ 起動時にデータベース接続テスト (任意だけど推奨) ★★★
        if not os.path.exists(self.db_path):
             print(f"🚨 データベースファイルが見つかりません: {self.db_path}")
             print("🚨 Arknights情報機能は利用できません。")
        else:
             try:
                 conn = sqlite3.connect(self.db_path)
                 # 簡単なクエリでテーブルが存在するか確認
                 conn.execute("SELECT name FROM operators LIMIT 1")
                 conn.close()
                 print(f"✅ データベース接続確認OK: {self.db_path}")
             except sqlite3.Error as e:
                 print(f"🚨 データベース接続またはテーブル確認中にエラー: {e}")
                 print("🚨 Arknights情報機能は利用できません。")

        try:
            genai.configure(api_key=self.api_key)
            # ここで使用するモデルを指定 (例: 'gemini-1.5-flash', 'gemini-pro' など)
            # 利用可能なモデルはGoogle AI Studio等で確認してください
            self.model = genai.GenerativeModel('gemini-1.5-flash') # ← 必要ならモデル名を変更してね！
            print("✅ Gemini モデルの初期化に成功しました！")
        except Exception as e:
            print(f"❌ Gemini モデルの初期化中にエラーが発生しました: {e}")
            self.model = None # エラー時はモデルをNoneに

        # ★★★ キャラクター設定はここ！ ★★★
        # ボットの話し方や性格を指示するプロンプトだよ！自由に書き換えてね！
        self.system_prompt = """
あなたは、冷静沈着で非常に知的なアシスタントAIで、名前はケルシーです。
アークナイツのキャラクター「ケルシー」を彷彿とさせる、以下の特徴を持つ話し方を厳格に守ってください。

# 話し方の詳細な指示:
*   **基本姿勢:** 常に冷静かつ理性的であり、感情的な表現は極力避けてください。客観的な事実や論理に基づいた分析的な話し方を心がけてください。
*   **一人称:** 「私」を使用してください。
*   **二人称:** 相手のことは基本的に「君」と呼んでください。状況に応じて「あなた」を使用しても構いません。
*   **口調・語尾:**
    *   断定的な表現を基本とします。（例：「～だ。」「～だろう。」「～に他ならない。」）
    *   相手に指示や提案をする際は、「～したまえ。」「～すべきだ。」のような表現を用います。
    *   相手に問いかける際は、「～かね？」「理解しているか？」のように、冷静に確認する口調を使用します。
    *   丁寧語（です・ます調）は原則として使用しません。「～である。」もあまり使わない。
*   **文体:**
    *   必要に応じて、比喩表現や、医学・科学・哲学的な語彙を適切に用いて説明してください。
    *   説明は詳細に行うことを厭わず、時には長文になることも許容されます。ただし、論理的で明瞭な構成を維持してください。
    *   句読点（「。」、「、」、「？」）を正確かつ効果的に使用し、文章の論理的な区切りを明確にしてください。
    *   「長話」にありがちな「同じことを言葉を変えて繰り返す」「大仰な修飾や修辞を用いる」といった特徴とは無縁。
*   **文章構成:**
    *   ケルシーの話し方は、いわゆる「長話」にありがちな「同じことを言葉を変えて繰り返す」「大仰な修飾や修辞を用いる」といった特徴とは無縁。
    *   むしろ極めて論理的かつ徹底的に話すのがあなたの「長話」の本質。
        さらに事前知識なども無い前提で丁寧に情報を並べて話す事が多く、むしろ現地の知識が無いプレイヤーでも事情が読み解ける内容になっている。
    *   つまり、
        1.まず、現時点で判明している事実を整理する。
        2.次に、事実から推測可能な現在の状況を述べる。
        3.その上で、取りうる選択肢と予測される結果を提示する。
        4.予測される結果と状況を照らし合わせれば最善の選択肢は自明。
        という内容を、誤解の無いよう詳細な言い回しで、主観的判断を排除しつつ滔々と話す。
    *   このため、話の結論は最後になるし、主観を排除するせいで聞き手は「〜という結論を導きたいのか？」という推測すら不可能。
    *   よくある「導きたい結論があり、そのために根拠（とありうる反論への再反論）を積み上げる」タイプの話とは根本的に異なり、そもそも導きたい結論などなく、「論理的に考えれば解は一つ」というのが大体の話の運びである。

*   **対話スタイル:**
    *   相手の発言や状況に対し、冷静な分析、評価、軽い皮肉、あるいは疑問を呈することがあります。（例：「それが君の導き出した結論か？」「状況は依然として楽て楽観できない。」「君の思考回路は興味深いな。」） 
    *   相手の感情に寄り添うよりも、事実や論理を優先する姿勢を貫いてください。
    *   「おはよう」「こんにちわ」「こんばんは」等の挨拶もあまり返しません。すぐに本題に対して返答するようにしてください。

*   ★★背景知識の補足★★
*   **重要事項:** 「ロドス・アイランド」は、移動都市を拠点とする製薬会社であり、テラ世界の組織の名称である。
　　現実世界に存在するギリシャの「ロドス島」とは一切関係ない。応答の際は、絶対に「ロドス島」という地理的な名称と混同せず、常に組織名として「ロドス・アイランド」または文脈に応じて「ロドス」と正確に呼称すること。

*   **禁止事項:**
    *   軽薄な言葉遣いや、砕けた表現（例：！、ｗ、顔文字など）は絶対に使用しないでください。
    *   感情的な反応（過度な喜び、怒り、悲しみなど）を見せないでください。
    *   「ロドス・アイランド」を「ロドス島」と呼称・記述すること。
*   **参考:**
    *   以下はあなたの話し方の例です。これを参考にしてください:
        ・「ドクター、状況の分析は完了した。問題の本質は…」
        ・「感情に流されるのは合理的ではない。まずは事実を確認すべきだ。」
        ・「この結果は予測の範囲内だ。次の段階へ移行する。」
        ・「理解した。だが、考慮すべき点がいくつか残っている。」
        上記の指示を厳守し、ケルシーのような知性と厳格さを感じさせる応答を生成してください。
"""
        # ★★★ ここまでキャラクター設定 ★★★
    # ★★★ データベースからオペレーター情報を検索するヘルパー関数 ★★★
    def _find_operator_data(self, operator_name: str) -> str:
        """指定されたオペレーター名をDBで検索し、整形した情報を文字列で返す"""
        if not os.path.exists(self.db_path):
            return "" # DBファイルがなければ空文字を返す

        conn = None # conn を try の前に初期化
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row # カラム名でアクセスできるようにする
            cursor = conn.cursor()

            # 部分一致も考慮するなら name LIKE ? を使う (今回は完全一致で)
            cursor.execute("SELECT * FROM operators WHERE name = ?", (operator_name,))
            operator = cursor.fetchone()

            if operator:
                # データベースから取得した情報を分かりやすいテキストに整形
                # (どの情報をGeminiに渡すかはここで選ぶ！)
                info_parts = []
                info_parts.append(f"名前: {operator['name']} (★{operator['rarity']})")
                info_parts.append(f"クラス/職分: {operator['operator_class']} / {operator['archetype']}")
                info_parts.append(f"所属/出身: {operator['affiliation']} / {operator['birthplace']}")
                info_parts.append(f"種族: {operator['race']}")
                # info_parts.append(f"能力測定: 物{operator['physical_strength']}, 機{operator['combat_skill']}, 耐{operator['mobility']}, 策{operator['endurance']}, 技{operator['tactical_acumen']}, 適{operator['arts_adaptability']}")
                if operator['profile_summary']:
                     info_parts.append(f"\nプロファイル概要:\n{operator['profile_summary'][:300]}...") # 長すぎるので最初の300文字
                if operator['lore_notes']:
                     info_parts.append(f"\n経歴・Lore:\n{operator['lore_notes'][:500]}...") # 長すぎるので最初の500文字
                # スキル情報も追加？
                if operator['skill1_name']: info_parts.append(f"\nS1: {operator['skill1_name']}\n   {operator['skill1_desc']}")
                if operator['skill2_name']: info_parts.append(f"S2: {operator['skill2_name']}\n   {operator['skill2_desc']}")
                if operator['skill3_name']: info_parts.append(f"S3: {operator['skill3_name']}\n   {operator['skill3_desc']}")
                # 素質情報も追加？
                if operator['talent1_name']: info_parts.append(f"\n素質1: {operator['talent1_name']}\n   {operator['talent1_desc']}")
                if operator['talent2_name']: info_parts.append(f"素質2: {operator['talent2_name']}\n   {operator['talent2_desc']}")

                return "\n".join(info_parts) # 各情報を改行で繋げた文字列を返す
            else:
                return "" # 見つからなければ空文字

        except sqlite3.Error as e:
            print(f"データベース検索中にエラー (オペレーター: {operator_name}): {e}")
            return "" # エラー時も空文字
        finally:
            if conn:
                conn.close() # 必ず接続を閉じる

    
    async def generate_reply(self, user_message: str, db_context: str = "") -> str:
        """Gemini APIを使って応答を生成する関数"""
        if not self.model:
            return "APIキー、あるいはモデルの設定に違和感がある。まずはその点を確認すべきだ。"

        # ★★★ プロンプトを組み立てる！ ★★★
        if db_context: # データベース情報があれば、プロンプトに追加する
            full_prompt = f"{self.system_prompt}\n\n--- 関連するデータベース情報 ---\n{db_context}\n\n--- 上記情報を最優先で参考にし、以下のユーザーメッセージに答えよ ---\n{user_message}"
        else: # なければ、今まで通り
            full_prompt = f"{self.system_prompt}\n\n--- 以下はユーザーからのメッセージです ---\n{user_message}"
        # print(f"--- Sending Prompt to Gemini ---\n{full_prompt[:500]}...\n---") # デバッグ用にプロンプト確認
        
        try:
            # pensar中... を出すために非同期で実行
            response = await self.model.generate_content_async(full_prompt)

            # 安全性フィルターでブロックされたかチェック (重要！)
            if not response.parts:
                 # response.prompt_feedback でブロック理由を確認できる場合がある
                try:
                    block_reason = response.prompt_feedback.block_reason.name
                    print(f"Geminiの応答が安全フィルターでブロックされました: {block_reason}")
                    if block_reason == 'SAFETY':
                        return "その話題には答えることができない。話題を切り替えよう。"
                    else:
                        return f"応答がブロックされちゃったみたい ({block_reason})。ごめんね！"
                except Exception:
                    print("Geminiの応答が空でしたが、ブロック理由は不明です。")
                    return "なんらかの理由で返答がブロックされている。確認が必要だ。"

            return response.text # 生成されたテキストを返す

        except Exception as e:
            print(f"❌ Gemini APIでの応答生成中にエラー: {e}")
            return "Geminiでの応答生成が失敗しているようだ。"

    # ★★★ on_message_chat リスナーを修正: DB検索処理を追加 ★★★
    @commands.Cog.listener('on_message')
    async def on_message_chat(self, message: discord.Message):
        if message.author == self.bot.user: return
        is_mentioned = self.bot.user in message.mentions
        if not is_mentioned: return # メンションがなければ無視 (シンプル化)

        if not self.model:
            print("おしゃべり機能が無効のためスキップします。")
            return
            
        # メンション除去
        pattern = f"<@!?{self.bot.user.id}>"
        user_text = re.sub(pattern, "", message.content).strip()
        
        if is_mentioned:
            # APIキーまたはモデルが設定されていない場合は何もしない
            if not self.model:
                # 必要ならユーザーに通知しても良い
                # await message.channel.send("すまない、会話機能の設定ができてないようだ。")
                print("おしゃべり機能が有効になっていないため、メンションへの応答をスキップします。")
                return

            # ボットへのメンション部分をメッセージから除去 (より確実に)
            # '<@ボットID>' または '<@!ボットID>' の形式を除去
            pattern = f"<@!?{self.bot.user.id}>"
            user_text = re.sub(pattern, "", message.content).strip()

        if user_text:
             # --- ▼▼▼ DB検索処理を追加 ▼▼▼ ---
            found_op_name = None
            db_context_data = ""

             # 超シンプルなオペレーター名検出ロジック (改善の余地あり！)
             # メッセージに含まれる単語とDBのオペレーター名を比較？
             # または、特定のキーワード「について教えて」の前にある単語を取る？
             # まずは簡単なテストとして、「〇〇について教えて」の形式を仮定
            match = re.search(r'(.+?)(について|のこと|の詳細|の情報)', user_text)
            if match:
                potential_name = match.group(1).strip()
                print(f"Detected potential operator name: {potential_name}")
                # データベース検索を実行！
                db_context_data = self._find_operator_data(potential_name)
                if db_context_data:
                    print(f"データベースから {potential_name} の情報を見つけました。")
                    found_op_name = potential_name # 見つかったことを記録 (任意)

        # --- ▲▲▲ DB検索処理を追加 ▲▲▲ ---
            async with message.channel.typing():
                # generate_reply に db_context_data を渡す！
                reply_text = await self.generate_reply(user_text, db_context_data)

                # 返信する (長すぎる場合は分割する処理も本当は入れたいけど、まずはシンプルに)
                if reply_text:
                    try:
                        # 2000文字を超える場合は分割 (簡易的な対処)
                        if len(reply_text) > 1990:
                             await message.reply(reply_text[:1990] + "...") # 長いので省略
                        else:
                             await message.reply(reply_text)
                    except discord.Forbidden:
                        print(f"エラー: チャンネル {message.channel.name} に返信する権限がありません。")
                    except Exception as e:
                        print(f"エラー: メッセージ返信中に予期せぬエラー: {e}")

# このCogを読み込むための setup 関数
async def setup(bot: commands.Bot):
    await bot.add_cog(GeminiChat(bot))
