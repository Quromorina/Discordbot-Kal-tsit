import discord
from discord.ext import commands, tasks
import os
import requests # 天気API用
from datetime import time, datetime, timezone, timedelta # 時刻処理用
import pytz # タイムゾーン処理用

# .env から設定を読み込み
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
TARGET_USER_ID_STR = os.getenv("WEATHER_USER_ID")
FRIEND_TARGET_ID_STR   = os.getenv("WEATHER_FRIEND_ID") # 追加：もう一人の送信先 (ユーザーID or チャンネルID)
TARGET_CITY = os.getenv("WEATHER_CITY_NAME", "Tokyo,JP") # デフォルトは東京
NOTIFY_TIME_STR = os.getenv("WEATHER_NOTIFY_TIME", "06:00") # デフォルトは7:00

# 文字列から数値に変換
TARGET_USER_ID = int(TARGET_USER_ID_STR) if TARGET_USER_ID_STR else None
FRIEND_TARGET_ID     = int(FRIEND_TARGET_ID_STR) if FRIEND_TARGET_ID_STR else None
notify_hour, notify_minute = map(int, NOTIFY_TIME_STR.split(':'))

jst = pytz.timezone('Asia/Tokyo')
hour, minute = map(int, NOTIFY_TIME_STR.split(":"))
now_jst      = datetime.now(jst)
dt_jst       = now_jst.replace(hour=hour, minute=minute, second=0, microsecond=0)
NOTIFY_TIME_UTC = dt_jst.astimezone(pytz.utc).time()

class WeatherNotify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot            = bot
        self.api_key        = OPENWEATHER_API_KEY
        self.city           = TARGET_CITY
        self.target_user_id = TARGET_USER_ID
        self.friend_id      = FRIEND_TARGET_ID

        if not self.api_key or not self.target_user_id:
            print("🚨 必須設定が不足しています。天気通知は無効です。")
        else:
            self.daily_weather_check.start()

    @tasks.loop(time=NOTIFY_TIME_UTC)
    async def daily_weather_check(self):
        # 1) 天気メッセージ生成
        weather_message = await self._get_weather_info()

        # 2) 所感を取得
        #gemini_cog: GeminiChat = self.bot.get_cog('GeminiChat')
        #if gemini_cog and gemini_cog.model:
        #    instruction = (
        #        "上記の天気予報データに基づき、今日の活動で注意すべき点、"
        #        "及び推奨される服装について、君の見解を述べたまえ。"
        #    )
        #    try:
        #        commentary = await gemini_cog.generate_commentary(
        #            context=weather_message,
        #            instruction=instruction
        #        )
        #   except Exception as e:
        #        print(f"❌ Commentary生成中にエラー: {e}")
        #        commentary = "所感の生成に失敗しました。"
        #else:
        #    commentary = ""

        # 3) full_message を組み立て
        #if commentary:
        #    full_message = (
        #        f"{weather_message}\n"
        #        "以下に示すのは天候予測に基づく私の見解だ。\n"
        #        f"---\n{commentary}"
        #    )
        #else:
        #    full_message = weather_message
        full_message = weather_message

        # 4) 送信先リストを作成
        send_funcs = []
        user = self.bot.get_user(self.target_user_id)
        if user:
            send_funcs.append(user.send)
        obj = self.bot.get_user(self.friend_id) or self.bot.get_channel(self.friend_id)
        if obj and hasattr(obj, "send"):
            send_funcs.append(obj.send)

        # 5) 一斉送信（full_messageを送る！）
        for send in send_funcs:
            try:
                await send(full_message)
            except discord.Forbidden:
                print(f"⛔️ 送信権限がありません: {send}")
            except Exception as e:
                print(f"❌ 送信中エラー ({send}): {e}")

    @daily_weather_check.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    async def _get_weather_info(self) -> str:
        """OpenWeatherMap API(/forecast)から天気と3時間予報を取得して整形する"""
        if not self.api_key: return "APIキーが設定されていません。"

        # ★★★ APIエンドポイントを /forecast に変更！ ★★★
        base_url = "http://api.openweathermap.org/data/2.5/forecast?"
        complete_url = base_url + "appid=" + self.api_key + "&q=" + self.city + "&lang=ja&units=metric&cnt=12"

        # ★★★ 絵文字マップは関数の最初の方で1回だけ定義！ ★★★
        emoji_map = {
            "01d": "☀️", "01n": "🌙", "02d": "🌤️", "02n": "☁️", "03d": "☁️", "03n": "☁️",
            "04d": "☁️", "04n": "☁️", "09d": "🌧️", "09n": "🌧️", "10d": "🌦️", "10n": "🌧️",
            "11d": "⛈️", "11n": "⛈️", "13d": "❄️", "13n": "❄️", "50d": "🌫️", "50n": "🌫️",
        }
        
        try:
            response = requests.get(complete_url)
            response.raise_for_status()
            data = response.json()

            if data["cod"] == "200": # ステータスコードが "200" なら成功
                forecast_list = data.get("list", [])

                # ★★★ リストが空か最初にチェック！ ★★★
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

                current_temp = current_main.get('temp')
                current_desc = current_weather.get('description', 'N/A')
                current_humidity = current_main.get('humidity') # ★ 湿度を取得！
                current_wind_speed = current_wind.get('speed') # ★ 風速を取得！
                current_icon = current_weather.get('icon') # アイコンも取れる

                # ★★★ 現在の天気情報を先に整形 ★★★
                current_temp_str = f"{current_temp:.1f}°C" if isinstance(current_temp, (int, float)) else "N/A"
                current_humidity_str = f"{current_humidity}%" if isinstance(current_humidity, (int, float)) else "N/A"
                current_wind_str = f"{current_wind_speed:.1f} m/s" if isinstance(current_wind_speed, (int, float)) else "N/A"
                current_emoji = emoji_map.get(current_icon, "❔") # 絵文字マップを使う

                # --- 3時間ごとの予報 (指定範囲だけ抽出！)  ---
                forecast_parts = []
                # 今日の日付と明日の日付をJSTで取得
                today_jst_date = datetime.now(jst).date()
                tomorrow_jst_date = today_jst_date + timedelta(days=1)
                
                # APIから取得した全予報データをチェック
                for forecast_entry in forecast_list:
                    dt_utc = datetime.fromtimestamp(forecast_entry.get('dt', 0), tz=timezone.utc)
                    dt_jst = dt_utc.astimezone(jst) # JSTに変換

                    # ★★★ フィルタリング条件 ★★★
                    # 今日の6時以降 OR 明日の3時以前 かどうか
                    is_today_target = (dt_jst.date() == today_jst_date and dt_jst.hour >= 6)
                    is_tomorrow_target = (dt_jst.date() == tomorrow_jst_date and dt_jst.hour <= 3)

                    # 条件に合致したらリストに追加
                    if is_today_target or is_tomorrow_target:
                        time_str = dt_jst.strftime('%H時')
                        temp = forecast_entry.get("main", {}).get('temp')
                        desc = forecast_entry.get("weather", [{}])[0].get('description')
                        icon = forecast_entry.get("weather", [{}])[0].get('icon', '')
                        icon = forecast_entry.get("weather", [{}])[0].get('icon', '')
                        temp_str = f"{temp:.0f}°C" if isinstance(temp, (int, float)) else "N/A"
                        emoji = emoji_map.get(icon, "❔")
                        forecast_parts.append(f"{time_str}: {emoji}{desc} {temp_str}") # 絵文字と説明を表示

                # メッセージを作成
                forecast_text = "\n".join(forecast_parts)
                if not forecast_text: # もし表示範囲の予報が取れなかった場合
                    forecast_text = "(指定範囲の予報データなし)"
                    
                message = (
                    f"おはよう、ドクター。\n"
                    f"東京の今日の天候を表示する。\n"
                    f"現在の天気: {current_emoji}{current_desc} {current_temp_str}\n"
                    f"湿度: {current_humidity_str} / 風速: {current_wind_str}\n"
                    f"--- 3時間ごと予報 ---\n"
                    f"{forecast_text}\n"
                )
                return message
            else:
                error_message = data.get("message", "不明なエラー")
                print(f"天気APIエラー: Code={data.get('cod')} Message={error_message}")
                return f"都市「{self.city}」の天気情報取得に失敗しました (Code: {data.get('cod')})。"
                
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

# Cogを読み込むための setup 関数
async def setup(bot: commands.Bot):
    await bot.add_cog(WeatherNotify(bot))
