#!/bin/bash
# このスクリプトは cron で実行されることを想定しています。
# cron の実行ユーザーが、必要なコマンド (git, python, systemctl) を実行できる権限が必要です。
# 今回は root の cron (sudo crontab -e) で登録し、ユーザー権限が必要な箇所は sudo -u を使います。

# --- 設定変数 ★★★ ここは自分の環境に合わせて正確に設定！ ★★★ ---
# スクリプトを実行するユーザー (git pull や populate.py を実行するユーザー)
GIT_USER="Quromorina"
USER_HOME="/home/$GIT_USER" # ユーザーのホームディレクトリへのフルパス

# Git clone した ArknightsGameData リポジトリの場所
ARK_DATA_REPO="$USER_HOME/arknights_yostar_data" # ★ cloneした場所のフルパス！
# (例: /home/Quromorina/arknights_yostar_data)

# ボットのプロジェクトフォルダの場所
MYBOT_DIR="$USER_HOME/mybot" # ★ mybotフォルダのフルパス！
# (例: /home/Quromorina/mybot)

# 仮想環境の Python 実行ファイルへのフルパス
VENV_PYTHON="$MYBOT_DIR/my_bot_env/bin/python3.11" # ★ python3.11 か python3 か確認！
# (例: /home/Quromorina/mybot/my_bot_env/bin/python3.11)

# populate_db.py スクリプトのフルパス
POPULATE_SCRIPT="$MYBOT_DIR/populate_db.py"

# スクリプト実行ログの場所
LOGFILE="$MYBOT_DIR/logs/populate_update.log" # logsフォルダは mybot フォルダ内に作成

# --- 事前準備 ---
# ログフォルダが存在しない場合は作成 (cron実行ユーザー (root) が作成するので root 権限で作成)
mkdir -p "$MYBOT_DIR/logs"
# ログファイルの所有者をユーザーに変更しておくと、後でユーザーから確認しやすい
# スクリプト実行前に毎回 ownership を変更すると安全
chown "$GIT_USER":"$GIT_USER" "$MYBOT_DIR/logs" 2>/dev/null # フォルダの所有者変更
chown "$GIT_USER":"$GIT_USER" "$LOGFILE" 2>/dev/null # ファイルの所有者変更


# --- 処理開始 ---
echo "--- $(date) --- Starting Arknights Data Update Script ---" >> $LOGFILE 2>&1 # タイムスタンプをログに追加

# --- 1. ArknightsGameData リポジトリを更新 ---
echo "Updating Arknights data repository at $ARK_DATA_REPO..." >> $LOGFILE 2>&1
# Git pull はユーザー権限 ($GIT_USER) で実行する必要がある
# -C オプションでディレクトリを移動してから git pull を実行
# >> は標準出力と標準エラー出力を両方ログファイルに追記
sudo -u "$GIT_USER" git -C "$ARK_DATA_REPO" pull origin main >> $LOGFILE 2>&1 # または master かも？
GIT_PULL_STATUS=$? # git pull の終了ステータスを取得 (0なら成功)

if [ $GIT_PULL_STATUS -ne 0 ]; then # 終了ステータスが0以外なら失敗
    echo "--- $(date) --- Git pull failed (status $GIT_PULL_STATUS). Aborting populate. ---" >> $LOGFILE 2>&1
    exit 1 # スクリプトを異常終了させる (cron が検知できるように)
fi
echo "Git pull successful." >> $LOGFILE 2>&1


# --- 2. データベースを更新 (populate_db.py を実行) ---
echo "Running populate_db.py..." >> $LOGFILE 2>&1
# populate_db.py を仮想環境の Python で、ユーザー権限 ($GIT_USER) で実行
# HOME 環境変数をユーザーのものに合わせて渡すと、sqlite3 が DB ファイルを見つけやすい
# 仮想環境の Python 実行ファイルへの絶対パスを使う
sudo -u "$GIT_USER" HOME="$USER_HOME" "$VENV_PYTHON" "$POPULATE_SCRIPT" >> $LOGFILE 2>&1
POPULATE_STATUS=$? # populate_db.py の終了ステータスを取得 (0なら成功)

if [ $POPULATE_STATUS -ne 0 ]; then
    echo "--- $(date) --- populate_db.py failed (status $POPULATE_STATUS). ---" >> $LOGFILE 2>&1
    exit 1 # スクリプトを異常終了
fi
echo "Populate script successful." >> $LOGFILE 2>&1


# --- 3. ボットサービスを再起動 ---
echo "Restarting discord-bot.service..." >> $LOGFILE 2>&1
# systemctl restart はシステム権限 (root) で実行する必要がある。
# root の cron なら sudo systemctl は systemctl でOK
systemctl restart discord-bot.service >> $LOGFILE 2>&1
SERVICE_RESTART_STATUS=$? # systemctl restart の終了ステータスを取得 (0なら成功)

if [ $SERVICE_RESTART_STATUS -ne 0 ]; then
    echo "--- $(date) --- Service restart failed (status $SERVICE_RESTART_STATUS). ---" >> $LOGFILE 2>&1
    exit 1 # スクリプトを異常終了
fi
echo "Service restarted successfully." >> $LOGFILE 2>&1


# --- 処理完了 ---
echo "--- $(date) --- Arknights Data Update Completed Successfully. ---" >> $LOGFILE 2>&1
exit 0 # スクリプト正常終了
