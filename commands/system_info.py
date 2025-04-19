import discord
from discord import app_commands
from discord.ext import commands
import psutil # システム情報を取得するライブラリ
import os # ファイルパス操作に使うかも (CPU温度取得とか)
import subprocess # vcgencmd を使う場合

# CPU温度を取得する関数 (ラズパイ特有の方法を試す)
def get_cpu_temperature():
    try:
        # 方法1: /sys ファイルシステムから読み取る (多くのLinuxで使える)
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_milli_celsius = int(f.read().strip())
            return temp_milli_celsius / 1000.0 # ミリ℃から℃へ変換
    except FileNotFoundError:
        # 方法2: vcgencmd コマンドを使う (Raspberry Pi OS 標準)
        try:
            result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True, check=True)
            # 出力例: temp=45.6'C
            temp_str = result.stdout.split('=')[1].split("'")[0]
            return float(temp_str)
        except (FileNotFoundError, subprocess.CalledProcessError, IndexError, ValueError) as e:
            print(f"CPU温度の取得に失敗しました: {e}")
            return None # 取得失敗
    except Exception as e:
         print(f"CPU温度の取得中に予期せぬエラー: {e}")
         return None # 取得失敗

class SystemInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="pi_status", description="ラズパイの現在の状態を表示する")
    async def pi_status(self, interaction: discord.Interaction):
        try:
            # 「考え中...」と表示させる (処理に少し時間がかかるかもなので)
            await interaction.response.defer(ephemeral=False) # ephemeral=True にすると本人にだけ見える

            # CPU使用率を取得
            cpu_percent = psutil.cpu_percent(interval=1) # 1秒間の平均

            # CPU温度を取得
            cpu_temp = get_cpu_temperature()
            cpu_temp_str = f"{cpu_temp:.1f}°C" if cpu_temp is not None else "取得失敗"

            # メモリ使用量を取得
            memory_info = psutil.virtual_memory()
            memory_percent = memory_info.percent
            memory_used_gb = memory_info.used / (1024**3) # バイトからGBへ
            memory_total_gb = memory_info.total / (1024**3)

            # ディスク使用量を取得 (ルート / のみ)
            disk_info = psutil.disk_usage('/')
            disk_percent = disk_info.percent
            disk_used_gb = disk_info.used / (1024**3)
            disk_total_gb = disk_info.total / (1024**3)

            # Embedメッセージを作成して見やすく表示！
            embed = discord.Embed(
                title="Raspberry Pi ステータス",
                color=discord.Color.green() # 元気な感じの色！
            )
            embed.add_field(name="🌡️ CPU温度", value=cpu_temp_str, inline=True)
            embed.add_field(name="⚙️ CPU使用率", value=f"{cpu_percent:.1f}%", inline=True)

            embed.add_field(name="🧠 メモリ使用率", value=f"{memory_percent:.1f}%", inline=True)
            embed.add_field(name="💾 使用量", value=f"{memory_used_gb:.1f} GB / {memory_total_gb:.1f} GB", inline=True)

            embed.add_field(name="💽 ディスク使用率 (/)", value=f"{disk_percent:.1f}%", inline=True)
            embed.add_field(name="💾 使用量", value=f"{disk_used_gb:.1f} GB / {disk_total_gb:.1f} GB", inline=True)
            # フッターに現在の時刻とか表示してもいいね！
            embed.set_footer(text=f"取得時刻: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

            # deferの後なので followup.send を使う
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"💥 /pi_status コマンド実行中にエラー: {e}")
            # defer の後なので followup でエラーメッセージを送る
            await interaction.followup.send("ごめんね、ステータス取得中にエラーが起きちゃった…", ephemeral=True)

# Cogを読み込むための setup 関数
async def setup(bot: commands.Bot):
    await bot.add_cog(SystemInfo(bot))
