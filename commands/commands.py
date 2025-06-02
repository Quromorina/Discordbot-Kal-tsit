# commands/commands.py

import discord
from discord import app_commands
from discord.ext import commands

class Basic(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # /osu
    @app_commands.command(name="kal'tsit", description="自己診断")
    async def ossu(self, interaction: discord.Interaction):
        await interaction.response.send_message("私の診断結果は私が自ら判断しよう。諸君は他の助けを必要としている感染者に力を注いでくれ。")

async def setup(bot: commands.Bot):
    await bot.add_cog(Basic(bot))

