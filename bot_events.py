import discord
import json
from datetime import datetime
import os
import pytz

jst = pytz.timezone('Asia/Tokyo')
# ↓↓↓ datetime.datetime.now じゃなくて datetime.now にする！ ↓↓↓
current_time_jst = datetime.now(jst)
timestamp_str = current_time_jst.strftime('%Y/%m/%d %H:%M:%S JST') # ← フッターに表示する文字列


# 設定ファイルのパス (このファイルと同じディレクトリにあると仮定)
CONFIG_FILE = os.path.join(os.path.dirname(__file__),'commands','config.json')

def load_config():
    """設定ファイル (config.json) を読み込む関数"""
    if not os.path.exists(CONFIG_FILE):
        print(f"情報: 設定ファイルが見つかりません: {CONFIG_FILE}。空の設定として扱います。")
        return {} # ファイルが存在しない場合は空の辞書を返す
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip(): # ファイルが空か、空白文字のみの場合
                 print(f"情報: 設定ファイル {CONFIG_FILE} は空です。")
                 return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"エラー: 設定ファイル {CONFIG_FILE} のJSON形式が正しくありません。")
        return {} # 不正な形式の場合は空の辞書を返す
    except Exception as e:
        print(f"エラー: 設定ファイル {CONFIG_FILE} の読み込み中に予期せぬエラー: {e}")
        return {}

# この関数が main.py の on_voice_state_update から呼び出される
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # ボット自身のアクションは無視
    if member.bot:
        return

    #print(f"Debug: on_voice_state_update in bot_events.py for {member.name}") # デバッグ用

    # VCに入った場合のみ通知 (他のユーザーが既に入っているチャンネルへの参加も含む)
    if before.channel != after.channel and after.channel is not None:
        #print(f"Debug: {member} joined VC {after.channel.name}") # デバッグ用
        # 設定ファイルを読み込む
        all_configs = load_config()
        if not all_configs:
            # print("Debug: No config loaded.") # デバッグ用
            return # 設定が空なら何もしない

        guild_id = str(member.guild.id)
        guild_config = all_configs.get(guild_id)

        if not guild_config:
            # print(f"Debug: No config found for guild {guild_id}") # デバッグ用
            return # このサーバーの設定がない

        vc_id_str = str(after.channel.id)
        setting = guild_config.get(vc_id_str)

        if not setting:
            # print(f"Debug: No specific setting found for VC {vc_id_str} in guild {guild_id}") # デバッグ用
            return # このVCの設定がない

        # --- 設定が見つかった場合の処理 ---
        role_id_str = setting.get("role_id")
        text_channel_id_str = setting.get("text_channel_id")

        if not role_id_str or not text_channel_id_str:
            print(f"警告: VC {after.channel.name} の設定に role_id あるいは text_channel_id が不足している。")
            return

        try:
            role = member.guild.get_role(int(role_id_str))
            text_channel = member.guild.get_channel(int(text_channel_id_str))
        except ValueError:
            print(f"エラー: 設定ファイル内のID (Role: {role_id_str}, Channel: {text_channel_id_str}) が有効な数値ではないようだ。")
            return

        if not role:
            print(f"エラー: 指定されたロールが見つかりません (ID: {role_id_str})。設定を確認してください。")
            # return # ロールが見つからなくても通知を送りたい場合はコメントアウト
        if not text_channel:
            print(f"エラー: 指定されたテキストチャンネルが見つかりません (ID: {text_channel_id_str})。通知は送信されません。")
            return # 通知先チャンネルがないと意味がないのでここで終了

        # 通知メッセージ作成
        embed = discord.Embed(
            title=f"🔊 通話開始", # シンプルに
            description=f"{member.mention} が <#{after.channel.id}> に参加したようだ。",
            color=discord.Color.green() # 色を変更
        )

        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        # member.display_name はニックネームも考慮してくれるよ！
        # member.name だとユーザー名だけになる

        # ★Footerにタイムスタンプを設定！
        embed.set_footer(text=f"参加時刻: {timestamp_str}")

        # 通知メッセージ送信
        try:
            # ロールメンションを含めるかどうかの判断 (常にメンションするならこのまま)
            content_msg = role.mention if role else None
            await text_channel.send(content=content_msg, embed=embed)
            print(f"通知を送信しました: サーバー「{member.guild.name}」のチャンネル「{text_channel.name}」へ")
        except discord.Forbidden:
             print(f"エラー: チャンネル「{text_channel.name}」にメッセージを送信する権限がありません。")
        except discord.HTTPException as e:
             print(f"エラー: Discord APIへのリクエスト中にエラーが発生しました (通知送信): {e}")
        except Exception as e:
            print(f"通知送信中に予期せぬエラーが発生しました: {e}")

    # (任意) VCから退出した場合の処理もここに追加できる
    # elif before.channel is not None and after.channel is None:
    #     print(f"{member} が {before.channel.name} から退出しました。")
    #     # 何か処理が必要ならここに書く
