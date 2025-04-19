#ダイスロールコマンドファイル
# commands/dice.py
import discord
from discord import app_commands
from discord.ext import commands
import random

class Dice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="dice", description="指定した回数ダイスを振るよ")
    @app_commands.describe(times="振る回数", sides="ダイスの面数")
    async def dice(self, interaction: discord.Interaction, times: int, sides: int):
        if times <= 0 or sides <= 0:
            await interaction.response.send_message("正の数を入力してね！")
            return

        rolls = [random.randint(1, sides) for _ in range(times)]
        total = sum(rolls)
        result = ", ".join(map(str, rolls))
        await interaction.response.send_message(f"{times}d{sides}の結果: 🎲 {result}（合計: {total}）")

async def setup(bot: commands.Bot):
    await bot.add_cog(Dice(bot))
