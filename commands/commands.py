# commands/commands.py

import discord
from discord import app_commands
from discord.ext import commands

class Basic(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # /osu
    @app_commands.command(name="osu", description="太陽からのエネルギー☀")
    async def ossu(self, interaction: discord.Interaction):
        await interaction.response.send_message("がおっす✋🦁⛩エネルギー感じてますか？どうもボドカです。今日はライオンズゲートの力で勝つことができました。優勝できたのもACEを取れたのも、全部太陽の門から降り注いだエネルギーのおかげです。あーもう最高や。幸福が体を包むんや。俺はボドカ。次のイーグルゲートは11月8日です。")

    # /ehho
    @app_commands.command(name="ehho", description="伝えなきゃ")
    async def ehho(self, interaction: discord.Interaction):
        try:
            # ↓↓↓ ここをフルパスに書き換える！ ↓↓↓
            image_full_path = "/home/Quromorina/mybot/commands/えっほえっほ.jpeg"

            # 指定したフルパスでファイルを開く！
            with open(image_full_path, "rb") as f:
                picture = discord.File(f)
                await interaction.response.send_message(file=picture)
        except FileNotFoundError: # ファイルが見つからないエラーをキャッチ
            print(f"💥 画像ファイルが見つかりません: {image_full_path}")
            await interaction.response.send_message("画像が見つからなかったみたい… (パスを確認してね！)", ephemeral=True)
        except Exception as e: # その他のエラーをキャッチ
            print(f"💥 画像送信エラー: {e}")
            await interaction.response.send_message("画像の送信中にエラーが起きちゃった…", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Basic(bot))

