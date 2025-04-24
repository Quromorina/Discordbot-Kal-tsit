import discord
from discord.ext import commands, tasks
import os
import requests # 天気API用
from datetime import time, datetime, timezone, timedelta # 時刻処理用
import pytz # タイムゾーン処理用

# .env から設定を読み込み
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
TARGET_USER_ID_STR = os.getenv("WEATHER_USER_ID")
TARGET_CITY = os.getenv("WEATHER_CITY_NAME", "Tokyo,JP") # デフォルトは東京
NOTIFY_TIME_STR = os.getenv("WEATHER_NOTIFY_TIME", "06:00") # デフォルトは7:00

# 文字列から数値や時刻オブジェクトに変換
TARGET_USER_ID = int(TARGET_USER_ID_STR) if TARGET_USER_ID_STR else None
notify_hour, notify_minute = map(int, NOTIFY_TIME_STR.split(':'))
# ★★★ 日本時間(JST)で指定された時刻に実行するように設定 ★★★
jst = pytz.timezone('Asia/Tokyo')
NOTIFY_TIME_UTC = time(hour=notify_hour, minute=notify_minute, tzinfo=jst).astimezone(pytz.utc)
print(f"Weather Notify Time (UTC): {NOTIFY_TIME_UTC.strftime('%H:%M')}")


class WeatherNotify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = OPENWEATHER_API_KEY
        self.target_user_id = TARGET_USER_ID
        self.city = TARGET_CITY

        # APIキーやユーザーIDがない場合はタスクを開始しない
        if not self.api_key:
            print("🚨 OpenWeatherMap APIキーが設定されていません。天気通知は無効です。")
        elif not self.target_user_id:
            print("🚨 通知先のユーザーID (WEATHER_USER_ID) が設定されていません。天気通知は無効です。")
        else:
            self.daily_weather_check.start() # タスクループを開始！

    def cog_unload(self):
        self.daily_weather_check.cancel() # Cogアンロード時にタスクをキャンセル

    async def _get_weather_info(self) -> str:
        """OpenWeatherMap APIから天気情報を取得して整形する"""
        if not self.api_key: return "APIキーが設定されていません。"

        base_url = "http://api.openweathermap.org/data/2.5/weather?"
        complete_url = base_url + "appid=" + self.api_key + "&q=" + self.city + "&lang=ja&units=metric" # 日本語&摂氏指定

        try:
            response = requests.get(complete_url)
            response.raise_for_status() # エラーがあれば例外を発生させる
            data = response.json()

            if data["cod"] != "404":
                main = data["main"]
                weather = data["weather"][0]
                wind = data["wind"]

                temp = main["temp"]
                temp_min = main["temp_min"]
                temp_max = main["temp_max"]
                humidity = main["humidity"]
                description = weather["description"]
                wind_speed = wind["speed"]

                # 時刻も取得してJSTに変換 (APIの時刻はUTC)
                dt_utc = datetime.fromtimestamp(data['dt'], tz=timezone.utc)
                dt_jst = dt_utc.astimezone(jst)
                time_str = dt_jst.strftime('%H:%M JST')

                # メッセージを作成
                message = (
                    f"おはよう、ドクター {self.city} の現在の天候 ({time_str}) だ。\n"
                    f"天気: {description}\n"
                    f"気温: {temp:.1f}°C (最高: {temp_max:.1f}°C / 最低: {temp_min:.1f}°C)\n"
                    f"湿度: {humidity}%\n"
                    f"風速: {wind_speed:.1f} m/s\n"
                )
                return message
            else:
                return f"都市「{self.city}」が見つかりませんでした。"
        except requests.exceptions.RequestException as e:
            print(f"天気APIへのリクエストエラー: {e}")
            return "天気情報の取得中にネットワークエラーが発生しました。"
        except KeyError as e:
            print(f"天気APIの応答形式エラー: {e}")
            return "天気情報の解析に失敗しました。"
        except Exception as e:
            print(f"天気情報取得中に予期せぬエラー: {e}")
            return "天気情報の取得中に不明なエラーが発生しました。"

    # ★★★ tasks.loop で毎日指定時刻に実行！ ★★★
    @tasks.loop(time=NOTIFY_TIME_UTC) # UTCで指定された時刻に実行
    async def daily_weather_check(self):
        print(f"[{datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')}] Running daily weather check...")
        target_user = self.bot.get_user(self.target_user_id)

        if target_user:
            weather_message = await self._get_weather_info()
            try:
                await target_user.send(weather_message)
                print(f"ユーザーID {self.target_user_id} に天気情報をDMで送信しました。")
            except discord.Forbidden:
                print(f"エラー: ユーザーID {self.target_user_id} にDMを送信する権限がありません。(ブロックされてる？)")
            except Exception as e:
                print(f"DM送信中に予期せぬエラー: {e}")
        else:
            print(f"エラー: 通知先のユーザーID {self.target_user_id} が見つかりませんでした。")

    # ループ開始前にボットの準備が完了するのを待つ
    @daily_weather_check.before_loop
    async def before_daily_check(self):
        print("Waiting for bot to be ready before starting weather loop...")
        await self.bot.wait_until_ready()
        print("Bot is ready, weather loop will start at the specified time.")

# Cogを読み込むための setup 関数
async def setup(bot: commands.Bot):
    # .envファイルから設定を読み込むため、ここでも読み込む必要があるかも？
    await bot.add_cog(WeatherNotify(bot))