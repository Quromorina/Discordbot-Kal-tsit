# ベースイメージはPython 3.11（軽量版）
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なファイルをコピー
COPY requirements.txt ./
COPY . .

# Pythonパッケージをインストール
RUN pip install --no-cache-dir -r requirements.txt

# 環境変数を読み込み（安全に保つため）
ENV PYTHONUNBUFFERED=1

# ボット起動
CMD ["python", "main.py"]
