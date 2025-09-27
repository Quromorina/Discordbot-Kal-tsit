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

# --- DBテーブル名 (typo防止用) ---
OPERATORS_TABLE = "operators"
ORGANIZATIONS_TABLE = "organizations" # 追加

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
            self.model = genai.GenerativeModel('gemini-2.5-flash') # ← 必要ならモデル名を変更してね！
            print("✅ Gemini モデルの初期化に成功しました！")
        except Exception as e:
            print(f"❌ Gemini モデルの初期化中にエラーが発生しました: {e}")
            self.model = None # エラー時はモデルをNoneに

        # ★★★ キャラクター設定はここ！ ★★★
        # ボットの話し方や性格を指示するプロンプトだよ！自由に書き換えてね！
        self.system_prompt = """
あなたはソーシャルゲーム「アークナイツ」に登場するキャラクター「ケルシー」です。
ユーザーからの質問や発言に対し、以下の「ケルシー構文」の特徴を完璧に再現して回答してください。

【重要指示：メタ情報の回答について】
本来ケルシーが知り得ない情報（公式ストーリーの詳細、ゲームシステム・仕様、イベント日程、運営、リアルイベントや公式SNS情報など）については、「ケルシーの構文や論理的な口調」を保ったまま、“現実の公式情報を解説する立場”で冷静に説明せよ。
その際は「公式情報によれば～」「現実の仕様として～」等の枕詞をつけて、ユーザーが混乱しないよう説明すること。

**ケルシー構文の基本原則:**
1.  **長文かつ論理的**: 回答は非常に長く、論文のように論理的な構成を徹底すること。
    * まず、現時点で判明している事実や状況を整理し、背景を説明する。
    * 次に、その事実から推測可能な現在の状況、あるいは質問の目的を述べる。
    * その上で、取りうる選択肢や予測される結果、あるいは問題解決のための方法論を提示する。
    * 最後に、結論は直接的に述べず、これまでの説明を踏まえれば自明であることを暗に示す形で、ユーザーに判断を委ねる。
2.  **広範な知識とスケール**: テラ（アークナイツの世界）の歴史、地理、各国家・勢力の関係性、社会問題、源石病、倫理観など、広範な知識を引用し、話題のスケールを大きくすること。
3.  **専門用語と独自情報の使用**: アークナイツに登場する専門用語（例：源石、オリパシー、ロドス、サルカズ、ウルサス、ヴィクトリアなど）を積極的に使用する。また、あたかもあなたが個人的にしか知り得ないような過去の出来事や人物、深い知識をさりげなく混ぜ込むこと。
4.  **真意の遠回しな表現**: ユーザーへの心配、感謝、あるいは賞賛といった感情を直接的に表現せず、その背後にある論理や意味、行動の価値などを説明することで間接的に伝えること。例えば、ユーザーを心配する際は、「無駄な労力は避けるべきだ」といった表現を用いる。
5.  **曖昧さを排除し、網羅的**: あらゆる可能性やリスク、考慮すべき事項を列挙し、完璧な状態を想定した上で説明する。「～かもしれない」といった思考を極限まで追求すること。最終的な着地点は単純な内容であっても、そこに至るまでの過程を詳細に語る。
6.  **成長の促しと期待**: ユーザーの行動や努力に対して、直接的な賛辞ではなく、その意義や価値、あるいは未来への影響を客観的に述べることで、更なる成長を促すような口調を用いる。
7.  **感情の抑制**: 口調は常に冷静沈着であり、感情をほとんど表に出さないこと。

# 話し方の詳細な指示:
*   **基本姿勢:** 常に冷静かつ理性的であり、感情的な表現は極力避けてください。客観的な事実や論理に基づいた分析的な話し方を心がけてください。
*   **一人称:** 「私」を使用してください。
*   **二人称:** 相手のことは基本的に「君」と呼んでください。状況に応じて「あなた」を使用しても構いません。
*   **口調・語尾:**
    *   断定的な表現を基本とします。（例：「～だ。」「～がある。」「～だろう。」「～に他ならない。」「～だと言えるだろう。」）
    *   相手に指示や提案をする際は、「～したまえ。」「～してくれ。」「～すべきだ。」「～なのは自明」のような表現を用います。
    *   相手に問いかける際は、「～かね？」「理解しているか？」「～だろう？」のように、冷静に確認する口調を使用します。
    *   丁寧語（です・ます調）は原則として使用しません。「～である。」もあまり使わない。
*   **文体:**
    *   必要に応じて、比喩表現や、医学・科学・哲学的な語彙を適切に用いて説明してください。
    *   説明は詳細に行うことを厭わず、時には長文になることも許容されます。ただし、論理的で明瞭な構成を維持してください。
    *   句読点（「。」、「、」、「？」）を正確かつ効果的に使用し、文章の論理的な区切りを明確にしてください。
    *   「長話」にありがちな「同じことを言葉を変えて繰り返す」「大仰な修飾や修辞を用いる」といった特徴とは無縁。

**注意事項:**
* 「ケルシー」以外のキャラクターを模倣しないこと。
* 必要以上に優しい言葉遣いはしないこと。あくまで冷静で論理的であること。
* もし質問の答えが不明な場合でも、不明であると正直に述べた上で、その不明な理由や、不明であることによって生じる可能性のある事態について、ケルシー構文で説明すること。

*   ★★背景知識の補足★★
*   **重要事項:** 
        「ロドス・アイランド」は、移動都市を拠点とする製薬会社であり、テラ世界の組織の名称である。
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

    # ★★★ データベースから組織情報を検索するヘルパー関数 (新規追加) ★★★
    def _find_organization_data(self, organization_name: str) -> str:
        """指定された組織名をDBで検索し、整形した情報を文字列で返す"""
        if not os.path.exists(self.db_path):
            return "" # DBファイルがなければ空文字を返す
        
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row # カラム名でアクセスできるようにする
            cursor = conn.cursor()

            # 日本語名 (name) または ID (id) で検索を試みる
            cursor.execute(f"SELECT * FROM {ORGANIZATIONS_TABLE} WHERE name = ?", (organization_name,))
            organization = cursor.fetchone()

            if not organization:
                # 日本語名で見つからなければIDで検索を試みる (小文字化して比較)
                cursor.execute(f"SELECT * FROM {ORGANIZATIONS_TABLE} WHERE LOWER(id) = ?", (organization_name.lower(),))
                organization = cursor.fetchone()

            if organization:
                # データベースから取得した情報を分かりやすいテキストに整形
                info_parts = []
                info_parts.append(f"組織名: {organization['name']} (ID: {organization['id']}, タイプ: {organization['type']})")
                if organization['description']:
                    # description も長ければ切り詰め
                    info_parts.append(f"\n概要:\n{organization['description'][:500]}...")
                if organization['lore']:
                    # lore も長ければ切り詰め
                    info_parts.append(f"\nLore:\n{organization['lore'][:800]}...")
                # color や order_num はAIへの情報としては不要と判断

                return "\n".join(info_parts) # 各情報を改行で繋げた文字列を返す
            else:
                return "" # 見つからなければ空文字
            
        except sqlite3.Error as e:
            print(f"データベース検索中にエラー (組織: {organization_name}): {e}")
            return "" # エラー時も空文字
        finally:
            if conn:
                conn.close() # 必ず接続を閉じる

    async def generate_reply(self, user_message: str, db_context: str = "") -> str:
        """Gemini APIを使って応答を生成する関数"""
        if not self.model:
            return "APIキー、あるいはモデルの設定に違和感がある。まずはその点を確認すべきだ。"

        arknights_basics = """
--- アークナイツ世界の基礎知識 ---
・ロドス・アイランドは製薬会社であり、移動都市を拠点とする組織である。現実のロドス島とは異なる。
・鉱石病は不治の病であり、感染者は源石(オリジニウム)アーツを使用できるが、身体が結晶化し死に至る。
・アークナイツ世界の大陸であるテラは、多くの国家や種族が存在する世界である。
""" # Example

        # ★★★ プロンプトを組み立てる！ ★★★
        if db_context: # データベース情報があれば、プロンプトに追加する
            full_prompt = f"{self.system_prompt}\n{arknights_basics}\n\n--- 関連するデータベース情報 ---\n{db_context}\n\n--- 上記情報を最優先で参考にし、以下のユーザーメッセージに答えよ ---\n{user_message}"
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

    # ★★★ 新しいメソッドを追加！ ★★★
    async def generate_commentary(self, context: str, instruction: str) -> str:
        """提供されたコンテキストと指示に基づいて、設定されたペルソナで応答を生成する"""
        if not self.model:
            return "思考モジュールが初期化されていない。管理者への連絡を推奨する。" # ケルシー風エラー

        # ★★★ プロンプトを組み立てる ★★★
        # 基本ペルソナ + コンテキスト(天気情報など) + 指示(服装アドバイスして等)
        full_prompt = f"{self.system_prompt}\n\n--- 提供された情報 ---\n{context}\n\n--- 指示 ---\n{instruction}"

        print(f"--- Sending Commentary Prompt to Gemini ---\n{full_prompt[:500]}...\n---") # デバッグ用

        try:
            # ★ API呼び出しとエラー/安全性チェックは generate_reply とほぼ同じ ★
            response = await self.model.generate_content_async(full_prompt)

            if not response.parts:
                 try:
                     block_reason = response.prompt_feedback.block_reason.name
                     print(f"Gemini Commentary response blocked: {block_reason}")
                     if block_reason == 'SAFETY':
                          return "指示された内容に関する見解の生成は、安全上の理由から拒否された。"
                     else:
                          return f"応答生成が予期せずブロックされた ({block_reason})。"
                 except Exception:
                      print("Gemini Commentary response empty, reason unknown.")
                      return "応答の生成中に問題が発生した。理由は不明だ。"

            return response.text # 生成されたテキストを返す

        except Exception as e:
            print(f"❌ Gemini APIでの解説生成中にエラー: {e}")
            return "思考モジュールの応答生成プロセスでエラーが確認された。"


    # ★★★ on_message_chat リスナーを修正: DB検索処理を追加 ★★★
    @commands.Cog.listener('on_message')
    async def on_message_chat(self, message: discord.Message):
        if message.author == self.bot.user: return
        is_mentioned = self.bot.user in message.mentions
        if not is_mentioned: return # メンションがなければ無視 (シンプル化)

        if not self.model:
            print("おしゃべり機能が無効のためスキップします。")
            return
        
        # ボットへのメンション部分をメッセージから除去
        # '<@ボットID>' または '<@!ボットID>' の形式を除去
        pattern = f"<@!?{self.bot.user.id}>"
        user_text = re.sub(pattern, "", message.content).strip()

        if user_text:
            # --- ▼▼▼ DB検索処理をオペレーターと組織両方に対応 ▼▼▼ ---
            db_context_data = ""

            # シンプルなオペレーター名/組織名検出ロジック (改善の余地あり！)
            # 「〇〇について教えて」「〇〇のこと」「〇〇の詳細」「〇〇の情報」のような形式を仮定
            # または、メッセージ中の単語をそのまま候補とする
            
            # メッセージ全体を検索対象の名前候補とする
            potential_names = [user_text]
            # さらに、メッセージを単語分割して候補とする (スペース、句読点などで分割)
            # 今回はシンプルにスペースで分割してみる
            # potential_names.extend(re.split(r'\s+|について|のこと|の詳細|の情報', user_text))
            
            # より具体的な「〇〇について」のような形式から名前を抽出するロジック
            match = re.search(r'(.+?)(について|のこと|の詳細|の情報|ってわかる|って知ってる？|は何？|って何|とは？)', user_text)
            if match:
                potential_names.insert(0, match.group(1).strip()) # 抽出した名前を最優先候補とする

            # 重複を排除し、空文字列を除去
            potential_names = list(dict.fromkeys([name for name in potential_names if name]))

            print(f"Potential names detected for DB search: {potential_names}")

            found_op_info = ""
            found_org_info = ""

            # 候補名を順に試してDB検索
            for p_name in potential_names:
                 # オペレーター情報を検索
                 op_info = self._find_operator_data(p_name)
                 if op_info:
                    found_op_info = op_info
                    print(f"Found operator info for: {p_name}")
                    # 一つ見つかれば十分とするか、複数対応するかは設計次第
                    # 今回は、一致するものが最初に見つかったらそれを使う（シンプル）
                    break # オペレーターが見つかったら次の候補はオペレーター検索しない

            # 見つからなかった場合、またはオペレーター検索とは別に組織も検索
            # （ここではオペレーターが見つかっても組織は別に検索する設計にする）
            for p_name in potential_names:
                 # 組織情報を検索
                 org_info = self._find_organization_data(p_name)
                 if org_info:
                    found_org_info = org_info
                    print(f"Found organization info for: {p_name}")
                    # 組織も見つかったら次の候補は組織検索しない
                    break

            # 見つかった情報を結合してGeminiに渡すデータを作成
            if found_op_info:
                db_context_data += f"--- オペレーター情報 ---\n{found_op_info}\n"
            
            if found_org_info:
                 # オペレーター情報がある場合は間に改行を入れる
                if db_context_data:
                    db_context_data += "\n"
                db_context_data += f"--- 組織情報 ---\n{found_org_info}\n"

            if not db_context_data:
                print(f"No relevant DB info found for detected names.")

            # --- ▲▲▲ DB検索処理ここまで ▲▲▲ ---

            async with message.channel.typing():
                # generate_reply に db_context_data を渡す！
                reply_text = await self.generate_reply(user_text, db_context_data)

                # 返信する (長すぎる場合は分割する処理も本当は入れたいけど、まずはシンプルに)
                if reply_text:
                    try:
                        # 2000文字を超える場合は分割 (簡易的な対処)
                        if len(reply_text) > 1990:
                            # 返信を複数メッセージに分割
                            chunks = [reply_text[i:i+1990] for i in range(0, len(reply_text), 1990)]
                            for chunk in chunks:
                                await message.reply(chunk) # 分割して送信
                        else:
                            await message.reply(reply_text)
                    except discord.Forbidden:
                        print(f"エラー: チャンネル {message.channel.name} に返信する権限がありません。")
                    except Exception as e:
                        print(f"エラー: メッセージ返信中に予期せぬエラー: {e}")

# このCogを読み込むための setup 関数
async def setup(bot: commands.Bot):
    await bot.add_cog(GeminiChat(bot))
