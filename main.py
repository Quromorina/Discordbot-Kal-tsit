import os
import discord
import subprocess
import datetime
import random
from discord.ext import commands
# config.py からトークンを読み込む想定 (config.py が環境変数などから安全に読み込むように実装されていること)
from config import DISCORD_TOKEN
# bot_events.py から on_voice_state_update 関数をインポート
# (Cog化する方が望ましいが、既存の構造を維持)
from bot_events import on_voice_state_update as on_voice_impl
import asyncio # asyncioを追加 (Cogロード後に同期するため)
print("--- main.py 実行開始！ ---", flush=True)
# Discordクライアント初期化
intents = discord.Intents.default()
intents.message_content = True # プリフィックスコマンドやメッセージ内容を読む場合に必要
intents.voice_states = True   # ボイスチャンネルの状態変化を検知するために必須
intents.guilds = True         # ギルド関連の情報取得に必要
intents.members = True        # メンバー情報の取得に必要 (on_voice_state_update で member を使うため)

# command_prefix はスラッシュコマンドメインなら不要かもしれないが、互換性のため残す
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Cogを非同期でロードするための関数 ---
async def load_extensions():
    # commands フォルダ内の Cog をロード
    cog_files = [
        'commands.commands',  # Basicコマンド
        'commands.janken',    # じゃんけん
        'commands.dice',      # ダイスロール
        'commands.configure', # 参加通知設定コマンド
        'commands.gemini_chat', # Gemini AI
        'commands.system_info', # ラズパイステータス
        'commands.weather_notify', #天気
        'commands.arknights_commands' # アークナイツオペレーターサーチ
    ]
    for extension in cog_files:
        try:
            await bot.load_extension(extension)
            print(f"✅ Cog '{extension}' をロードしました")
        except commands.ExtensionNotFound:
            print(f"❌ Cog '{extension}' が見つかりません")
        except commands.ExtensionAlreadyLoaded:
            print(f"ℹ️ Cog '{extension}' は既にロードされています")
        except Exception as e:
            print(f"❌ Cog '{extension}' のロード中にエラー: {e}")

# --- イベントハンドラ ---
@bot.event
async def on_ready():
    print("--- on_ready 開始 ---", flush=True)
    print(f'Logged in as {bot.user.name} ({bot.user.id})', flush=True)
    print('------', flush=True)

    # 候補リスト
    activities = [
        "ロドスアイランド(シラクーザに停泊中)",
        "ロドスアイランド(龍門に停泊中)",
        "ロドスアイランド(移動中)",
        "ロドスアイランド(not found...)",
        "ロドスアイランド(イベリアに停泊中)",
        "ロドスアイランド(メンテナンス作業中)",
        "ロドスアイランド(チェルノボーグに停泊中)",
        "ロドスアイランド(クルビアに停泊中)",
        "ロドスアイランド(カジミエーシュに停泊中)",
        "ロドスアイランド(ラテラーノに停泊中)",
        "ロドスアイランド(ヴィクトリアに停泊中)",
        "ロドスアイランド(リターニアに停泊中)",
        "ロドスアイランド(イベリアに停泊中)",
        "ロドスアイランド(イェラグに停泊中)",
        "ロドスアイランド(シエスタに停泊中)",
        "ロドスアイランド(サルゴンに停泊中)",
        "ロドスアイランド(サルゴンに停泊中)",
    ]
    
    today = datetime.date.today()
    # 「3日ごと」のグループ番号を計算
    block = today.toordinal() // 3
    rng = random.Random(block)
    shuffled = activities[:]
    rng.shuffle(shuffled)
    activity_name = shuffled[0]  # 各ブロックごとに1つランダム選出

    # データベース自動作成
    db_path = os.path.join(os.path.dirname(__file__), 'arknights_data.db')
    if not os.path.exists(db_path):
        print("🚨 データベースが見つからないため作成を試みます...")
        try:
            subprocess.run(['python', 'create_db.py'], check=True)
            subprocess.run(['python', 'populate_db.py'], check=True)
            print("✅ データベースの自動作成が完了しました。")
        except Exception as e:
            print(f"❌ データベース自動作成中にエラー: {e}")

    print("--- Cog ロード開始 ---", flush=True)

    # Cogをロード
    try:
        await load_extensions()
    except Exception as e:
        print(f"!!!!! Cog ロード中に致命的なエラー:{e}!!!!!", flush=True)

    print("--- Cog ロード完了 ---", flush=True) # ★追加
    print("--- ステータス変更開始 ---", flush=True) # ★追加

    # ステータスメッセージ設定
    try:
        activity = discord.CustomActivity(name=activity_name)
        await bot.change_presence(status=discord.Status.online, activity=activity)
    except Exception as e:
        print(f"!!!!! ステータス変更中にエラー: {e} !!!!!", flush=True)

    print("--- ステータス変更完了 ---", flush=True)
    print("--- スラッシュコマンド同期開始 ---", flush=True)

    # スラッシュコマンドをグローバルに同期
    # 注意: 同期には時間がかかることがあります。頻繁な変更時はギルド指定を推奨
    try:
        # 特定ギルドのみでテストする場合:
        # GUILD_ID = discord.Object(id=YOUR_TEST_SERVER_ID) # テストサーバーIDに置き換える
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)}個のスラッシュコマンドを同期しました", flush=True)
    except Exception as e:
        print(f"❌ スラッシュコマンドの同期に失敗しました: {e}", flush=True)

    print("--- スラッシュコマンド同期完了 ---", flush=True)
    print("--- on_ready 完了 ---", flush=True)

@bot.event
async def on_voice_state_update(member, before, after):
    # bot_events.py の on_voice_state_update 関数を呼び出す
    print(f"Debug: on_voice_state_update triggered in main.py for {member.name}",flush=True) # デバッグ用
    await on_voice_impl(member, before, after)

# メッセージベースのコマンドも使う場合 (使わないならコメントアウト可)
@bot.event
async def on_message(message):
    if message.author.bot: # ボット自身のメッセージは無視
        return
    try:
        await bot.process_commands(message)
    except commands.CommandNotFound:
        pass # コマンドが見つからなくてもエラーにしない

# --- 起動 ---
if __name__ == '__main__':
    # トークンが正しく設定されているか確認 (任意)
    if not DISCORD_TOKEN:
        print("エラー: Discordボットトークンが config.py で設定されていません。")
    else:
        try:
            bot.run(DISCORD_TOKEN)
        except discord.LoginFailure:
            print("エラー: Discordボットトークンが無効です。")
        except Exception as e:
            print(f"ボットの起動中に予期せぬエラーが発生しました: {e}")
