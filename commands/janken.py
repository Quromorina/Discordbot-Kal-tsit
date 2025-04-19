import random
import discord
from discord.ext import commands
from discord import app_commands

class JankenView(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=30)
        self.user = user
        self.result_sent = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("これはあなた専用のじゃんけんだよ！", ephemeral=True)
            return False
        return True

    async def end_game(self, interaction: discord.Interaction, player_hand: int, label: str, emoji: str):
        bot_hand = random.randint(0, 2)
        hand_emojis = ["✊", "✌", "🖐️"]
        result = (player_hand - bot_hand + 3) % 3

        result_msg = ["あいこで…もう一回！", "なんで負けたのか明日までに考えといてください。", "あなたの勝ち～🎉"][result]

        # すべてのボタンを無効化
        for item in self.children:
            item.disabled = True

        # 新しいボタンだけ表示
        final_view = discord.ui.View()
        final_view.add_item(discord.ui.Button(
            label=f"{label}を出したよ！",
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            disabled=True
        ))

        await interaction.response.edit_message(
            content=f"ぽんっ！ {hand_emojis[bot_hand]}（Bot）\n{result_msg}",
            view=final_view
        )
        self.result_sent = True
        self.stop()

    @discord.ui.button(label="グー", emoji="✊", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.end_game(interaction, 0, button.label, button.emoji)

    @discord.ui.button(label="チョキ", emoji="✌", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.end_game(interaction, 1, button.label, button.emoji)

    @discord.ui.button(label="パー", emoji="🖐️", style=discord.ButtonStyle.primary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.end_game(interaction, 2, button.label, button.emoji)

    async def on_timeout(self):
        if not self.result_sent:
            for item in self.children:
                item.disabled = True
            await self.message.edit(content="時間切れ～！またやってね💦", view=self)


class Janken(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="janken", description="じゃんけんで対決！")
    async def janken(self, interaction: discord.Interaction):
        view = JankenView(user=interaction.user)
        view.message = await interaction.response.send_message("じゃんけん...", view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(Janken(bot))
