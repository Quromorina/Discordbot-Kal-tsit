# config.py の例
import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__),'.env')
load_dotenv(dotenv_path=dotenv_path) # .env ファイルから環境変数を読み込む場合
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
