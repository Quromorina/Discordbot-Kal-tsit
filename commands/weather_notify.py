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

        # --- 1. 天気予報を取得 ---
        weather_message = await self._get_weather_info()
        if "エラー" in weather_message or "取得できませんでした" in weather_message or "見つかりませんでした" in weather_message:
             print(f"天気予報取得失敗のためスキップ: {weather_message}")
             # (エラーメッセージ送信処理は省略)
             return
        
        # --- 2. GeminiChat Cog を取得 ---
        gemini_cog: GeminiChat = self.bot.get_cog('GeminiChat') # 型ヒントを追加(任意)
        if not gemini_cog or not gemini_cog.model: # GeminiCogがないか、モデルが初期化されてない場合
            print("🚨 GeminiChat Cog またはモデルが見つからないため、天気解説はスキップします。")
            # 天気予報だけ送る
            try:
                 await target_user.send(weather_message)
                 print(f"ユーザーID {self.target_user_id} に天気予報のみDM送信しました。")
            except Exception as e:
                 print(f"天気予報のみDM送信中にエラー: {e}")
            return
        
        # --- 3. Gemini に渡す指示を作成 ---
        instruction = "上記の天気予報データに基づき、今日の活動で注意すべき点、及び推奨される服装について、君の見解を簡潔に述べたまえ。"

        # --- 4. GeminiChat Cog の新メソッドを呼び出す！ ---
        print("GeminiChat Cog に天気予報の解説をリクエスト中...")
        advice_text = "思考モジュールからの応答がなかった。" # デフォルトのエラーメッセージ
        try:
            async with target_user.typing():
                 # ★★★ ここで generate_commentary を呼び出す！ ★★★
                advice_text = await gemini_cog.generate_commentary(context=weather_message, instruction=instruction)
        except Exception as e:
            print(f"❌ Gemini解説生成呼び出し中にエラー: {e}")
            # advice_text はデフォルトのエラーメッセージのまま

        # --- 5. 結果をDMで送信 (変更なし) ---
        final_dm_message = f"\n以下に示すのは天候予測に基づく私の見解だ。\n---\n{advice_text}"
        try:
            # ... (メッセージ送信処理) ...
            await target_user.send(final_dm_message)
            print(f"ユーザーID {self.target_user_id} に天気予報とAI解説をDMで送信しました。")
        except Exception as e:
            print(f"最終DM送信中にエラー: {e}")

    # ループ開始前にボットの準備が完了するのを待つ
    @daily_weather_check.before_loop
    async def before_daily_check(self):
        await self.bot.wait_until_ready()

# Cogを読み込むための setup 関数
async def setup(bot: commands.Bot):
    # .envファイルから設定を読み込むため、ここでも読み込む必要があるかも？
    await bot.add_cog(WeatherNotify(bot))
