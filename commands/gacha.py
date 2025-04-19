import discord
from discord import app_commands
from discord.ext import commands
import random

class Gacha(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="gacha", description="ガチャを引いてみよう！")
    async def gacha(self, interaction: discord.Interaction):
        rarities = {
            "UR:RTX4090": 2,     # 1%
            "SSR:ZEMAIM": 8,    # 4%
            "SR:": 12,    # 10%
            "R:": 20,     # 25%
            "N:レッドブル": 58      # 60%
        }

        # 抽選
        result = random.choices(
            population=list(rarities.keys()),
            weights=list(rarities.values()),
            k=1
        )[0]

        await interaction.response.send_message(f" {result} が当選しました！")

async def setup(bot: commands.Bot):
    await bot.add_cog(Gacha(bot))
