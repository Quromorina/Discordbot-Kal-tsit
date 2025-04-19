import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from typing import Dict, Any # 型ヒントのため

# 設定ファイルのパス (このCogファイルと同じディレクトリにあると仮定)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

# --- 設定ファイルの読み書き関数 ---
def load_config() -> Dict[str, Any]:
    """設定ファイル (config.json) を読み込む"""
    if not os.path.exists(CONFIG_FILE):
        return {} # ファイルが存在しない場合は空の辞書を返す
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            # ファイルが空の場合も考慮
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"エラー: 設定ファイル {CONFIG_FILE} のJSON形式が不正です。空のファイルとして扱います。")
        return {}
    except Exception as e:
        print(f"エラー: 設定ファイル {CONFIG_FILE} の読み込み中にエラーが発生しました: {e}")
        return {}

def save_config(data: Dict[str, Any]):
    """設定データ (辞書) を config.json に書き込む"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False) # indentで整形、日本語もOKに
    except Exception as e:
        print(f"エラー: 設定ファイル {CONFIG_FILE} への書き込み中にエラーが発生しました: {e}")

# --- ここからCogクラス ---
class Configure(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="configure", description="通知するVC・ロール・テキストチャンネルを設定")
    @app_commands.describe(vc="通知対象のVC", role="メンションするロール", text_channel="通知を送るテキストチャンネル")
    async def configure(
        self,
        interaction: discord.Interaction,
        vc: discord.VoiceChannel,
        role: discord.Role,
        text_channel: discord.TextChannel
    ):
        try:
            guild_id = str(interaction.guild.id)
            all_configs = load_config() # 全設定を読み込む

            # このギルドの設定を取得 (なければ新規作成)
            guild_config = all_configs.get(guild_id, {})

            # ボイスチャンネルIDをキーにして設定を保存
            guild_config[str(vc.id)] = {
                "role_id": str(role.id),
                "text_channel_id": str(text_channel.id)
            }

            # 全設定データにこのギルドの設定を反映
            all_configs[guild_id] = guild_config
            save_config(all_configs) # 全設定をファイルに書き込む

            await interaction.response.send_message(
                f"✅ 設定保存済み\nVC: {vc.mention}\nロール: {role.mention}\n通知チャンネル: {text_channel.mention}",
                ephemeral=True # 設定内容は本人だけに見せる
            )
        except Exception as e:
            print(f"Error during configure: {e}")
            await interaction.response.send_message(f"⚠️ 設定保存中にエラーが発生しました: {e}", ephemeral=True)

    @app_commands.command(name="configure_state", description="現在の通知設定を確認できる")
    async def configure_state(self, interaction: discord.Interaction):
        try:
            guild_id = str(interaction.guild.id)
            all_configs = load_config()
            guild_config = all_configs.get(guild_id)

            if not guild_config:
                await interaction.response.send_message("⚠️ このサーバーには設定がまだないようだ", ephemeral=True)
                return

            settings_message = "🔧 現在の設定：\n"
            found_settings = False
            for vc_id, setting in guild_config.items():
                try:
                    # int() に失敗するキーがある可能性を考慮
                    vc = interaction.guild.get_channel(int(vc_id))
                    role = interaction.guild.get_role(int(setting.get("role_id"))) # .get()でキー欠損に対応
                    text_channel = interaction.guild.get_channel(int(setting.get("text_channel_id")))

                    vc_mention = vc.mention if vc else f"(ID: {vc_id} - 不明なVC)"
                    role_mention = role.mention if role else f"(ID: {setting.get('role_id')} - 不明なロール)"
                    tc_mention = text_channel.mention if text_channel else f"(ID: {setting.get('text_channel_id')} - 不明なチャンネル)"

                    settings_message += f"- VC: {vc_mention}, ロール: {role_mention}, チャンネル: {tc_mention}\n"
                    found_settings = True
                except (ValueError, KeyError, AttributeError) as inner_e:
                     print(f"設定表示中に一部エラー: vc_id={vc_id}, error={inner_e}")
                     settings_message += f"- (ID: {vc_id} の設定表示中にエラー)\n"


            if not found_settings:
                 await interaction.response.send_message("⚠️ このサーバーには有効な設定がなないようだ。", ephemeral=True)
                 return

            await interaction.response.send_message(settings_message, ephemeral=True)
        except Exception as e:
            print(f"Error during configure_state: {e}")
            await interaction.response.send_message(f"⚠️ 設定確認中にエラーが発生しました: {e}", ephemeral=True)

    @app_commands.command(name="configure_delete", description="指定したVCの通知設定を削除する")
    @app_commands.describe(vc="設定を削除するVC")
    async def configure_delete(self, interaction: discord.Interaction, vc: discord.VoiceChannel):
        try:
            guild_id = str(interaction.guild.id)
            all_configs = load_config()
            guild_config = all_configs.get(guild_id)

            if not guild_config:
                await interaction.response.send_message("⚠️ このサーバーにはまだ設定がされていない。", ephemeral=True)
                return

            vc_id_str = str(vc.id)

            if vc_id_str in guild_config:
                del guild_config[vc_id_str] # 該当VCの設定を削除

                # もしギルドの設定が空になったら、ギルド自体のキーも削除する（任意）
                if not guild_config:
                    del all_configs[guild_id]
                else:
                    all_configs[guild_id] = guild_config # 更新されたギルド設定を反映

                save_config(all_configs) # ファイルに書き込む
                await interaction.response.send_message(f"🗑️ {vc.mention} の通知設定を削除した", ephemeral=True)
            else:
                await interaction.response.send_message(f"現状、 {vc.mention} の設定はないようだ", ephemeral=True)
        except Exception as e:
            print(f"Error during configure_delete: {e}")
            await interaction.response.send_message(f"⚠️ 設定削除中にエラーが発生しました: {e}", ephemeral=True)

# このCogを読み込むための setup 関数
async def setup(bot: commands.Bot):
    await bot.add_cog(Configure(bot))
