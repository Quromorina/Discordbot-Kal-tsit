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

# 文字列から数値に変換
TARGET_USER_ID = int(TARGET_USER_ID_STR) if TARGET_USER_ID_STR else None
notify_hour, notify_minute = map(int, NOTIFY_TIME_STR.split(':'))
jst = pytz.timezone('Asia/Tokyo')

# ↓↓↓ JST時刻をUTC時刻に正しく変換する処理 ↓↓↓
try:
    now_jst = datetime.now(jst)
    target_dt_jst = now_jst.replace(hour=notify_hour, minute=notify_minute, second=0, microsecond=0)
    target_dt_utc = target_dt_jst.astimezone(pytz.utc)
    NOTIFY_TIME_UTC = target_dt_utc.time()
    print(f"Weather Notify Time (UTC): {NOTIFY_TIME_UTC.strftime('%H:%M')}")
except Exception as e:
    # もし時刻変換でエラーが起きたら、とりあえずUTCの0時を使う (フォールバック)
    print(f"🚨 通知時刻の計算中にエラー: {e}. UTC 00:00 を使用します。")
    NOTIFY_TIME_UTC = time(hour=0, minute=0, tzinfo=pytz.utc)


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
        """OpenWeatherMap API(/forecast)から天気と3時間予報を取得して整形する"""
        if not self.api_key: return "APIキーが設定されていません。"

        # ★★★ APIエンドポイントを /forecast に変更！ ★★★
        base_url = "http://api.openweathermap.org/data/2.5/forecast?"
        # cnt=9 で約24時間分 (現在+未来8回分 = 9データ点) を取得 (API仕様による)
        complete_url = base_url + "appid=" + self.api_key + "&q=" + self.city + "&lang=ja&units=metric&cnt=9"

        try:
            # ★★★ 非同期でリクエストを送るなら aiohttp が望ましいけど、まずは requests で試す ★★★
            # (もしボットが他の処理中に固まるのが気になるなら、後で aiohttp に変える)
            response = requests.get(complete_url)
            response.raise_for_status() # エラーがあれば例外を発生させる
            data = response.json()

            if data["cod"] == "200": # ステータスコードが "200" なら成功
                forecast_list = data.get("list", [])
                if not forecast_list:
                    return f"{self.city} の予報データが取得できませんでした。"

                # --- 現在の天気 (リストの最初のデータを使う) ---
                current_data = forecast_list[0]
                current_main = current_data.get("main", {})
                current_weather = current_data.get("weather", [{}])[0]
                current_wind = current_data.get("wind", {})
                current_dt_utc = datetime.fromtimestamp(current_data.get('dt', 0), tz=timezone.utc)
                current_dt_jst = current_dt_utc.astimezone(jst)
                current_time_str = current_dt_jst.strftime('%H:%M JST')

                current_temp = current_main.get('temp', 'N/A')
                current_desc = current_weather.get('description', 'N/A')
                current_icon = current_weather.get('icon') # アイコンも取れる

                # --- 3時間ごとの予報 (リストの2番目から8個 = 約24時間分) ---
                forecast_parts = []
                # forecast_list[1:9] で、2番目から最大9番目までを取得 (最大8件)
                for forecast_entry in forecast_list[1:9]:
                    dt_utc = datetime.fromtimestamp(forecast_entry.get('dt', 0), tz=timezone.utc)
                    dt_jst = dt_utc.astimezone(jst)
                    time_str = dt_jst.strftime('%H時') # 例: "09時"
                    temp = forecast_entry.get("main", {}).get('temp')
                    desc = forecast_entry.get("weather", [{}])[0].get('description')
                    # アイコンも取れる icon = forecast_entry.get("weather", [{}])[0].get('icon')

                    temp_str = f"{temp:.0f}°C" if isinstance(temp, (int, float)) else "N/A"
                    # 簡単な絵文字マッピング (適宜追加・修正してね！)
                    emoji = "❔"
                    if "晴" in desc: emoji = "☀️"
                    elif "曇" in desc: emoji = "☁️"
                    elif "雨" in desc: emoji = "🌧️"
                    elif "雪" in desc: emoji = "❄️"
                    elif "雷" in desc: emoji = "⚡"

                    forecast_parts.append(f"{time_str}: {emoji}{desc} {temp_str}")
                    
                forecast_text = "\n".join(forecast_parts)
                # メッセージを作成
                message = (
                    f"おはよう、ドクター。\n"
                    f"{self.city} の今日の天候を通知する。\n"
                    f"現在の天気: {current_desc} {current_temp}°C\n"
                    f"気温: {temp:.1f}°C (最高: {temp_max:.1f}°C / 最低: {temp_min:.1f}°C)\n"
                    f"湿度: {humidity}%\n"
                    f"風速: {wind_speed:.1f} m/s\n"
                    f"--- 3時間ごと予報 ---\n"
                    f"{forecast_text}\n"
                )
                return message
            else:
                return f"都市「{self.city}」が見つかりませんでした。"
                
        # (エラー処理は前のままでも良いけど、requests 用に調整)
        except requests.exceptions.RequestException as e:
            print(f"天気API(/forecast)へのリクエストエラー: {e}")
            return "天気情報の取得中にネットワークエラーが発生しました。"
        except KeyError as e:
            print(f"天気API(/forecast)の応答形式エラー: キーが見つかりません {e}")
            return "天気情報の解析に失敗しました。"
        except Exception as e:
            print(f"天気情報(/forecast)取得中に予期せぬエラー: {e}")
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
