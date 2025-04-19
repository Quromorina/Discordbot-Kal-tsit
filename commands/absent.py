import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import pytz

absent_members = set()
CHANNEL_ID = 1157690596270547066  # ← 通知したいチャンネルIDをここに！

class AbsentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="欠席します", style=discord.ButtonStyle.danger, custom_id="absent_button")
    async def absent_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        channel = interaction.client.get_channel(CHANNEL_ID)

        if user.id in absent_members:
            absent_members.remove(user.id)
            await interaction.response.defer()  # ← 処理中表示だけ出して、返信はなし！
            if channel:
                await channel.send(f"✅ {user.mention} の欠席を取り消しました！")
        else:
            absent_members.add(user.id)
            await interaction.response.defer() # ← 処理中表示だけ出して、返信はなし！
            if channel:
                await channel.send(f"🚨 {user.mention} が **欠席** を登録しました！")

class Absent(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_absent_message.start()

    def cog_unload(self):
        self.daily_absent_message.cancel()

    @tasks.loop(minutes=1)
    async def daily_absent_message(self):
        jst = pytz.timezone("Asia/Tokyo")
        now = datetime.datetime.now(jst)  # ← JSTで現在時刻を取得！
        if now.hour == 12 and now.minute == 00:
            absent_members.clear()
            channel = self.bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.send("今日欠席する人はこのボタンを押してね！", view=AbsentView())

    @daily_absent_message.before_loop
    async def before_daily(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="absent", description="欠席入力ボタンを表示するよ")
    async def absent(self, interaction: discord.Interaction):
        await interaction.response.send_message("欠席する人はこのボタンを押してね！", view=AbsentView())

async def setup(bot: commands.Bot):
    await bot.add_cog(Absent(bot))

