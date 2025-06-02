#!/bin/bash
# このスクリプトは cron で実行されることを想定しています。
# cron の実行ユーザーが、必要なコマンド (git, python, systemctl) を実行できる権限が必要です。
# 今回は root の cron (sudo crontab -e) で登録し、ユーザー権限が必要な箇所は sudo -u を使います。

# --- 設定変数 ★★★ 環境に合わせて正確に設定！ ★★★ ---
GIT_USER="Quromorina"
USER_HOME="/home/$GIT_USER"

MYBOT_DIR="$USER_HOME/mybot/Discordbot-Kal-tsit"
VENV_PYTHON="$USER_HOME/mybot/venv/bin/python3"
POPULATE_SCRIPT="$MYBOT_DIR/populate_db.py"
LOGFILE="$MYBOT_DIR/logs/populate_update.log"

# --- 事前準備 ---
mkdir -p "$MYBOT_DIR/logs"
chown "$GIT_USER":"$GIT_USER" "$MYBOT_DIR/logs" 2>/dev/null
touch "$LOGFILE"
chown "$GIT_USER":"$GIT_USER" "$LOGFILE" 2>/dev/null

echo "--- $(date) --- Starting Arknights Data Update Script ---" >> "$LOGFILE" 2>&1

# --- 1. ArknightsGameData リポジトリを更新 ---
echo "Updating Arknights data submodule (ark_data)..." >> "$LOGFILE"

# ① サブモジュールをリモートから最新取得
sudo -u "$GIT_USER" git -C "$MYBOT_DIR" submodule update --remote --merge ark_data >> "$LOGFILE" 2>&1

GIT_PULL_STATUS=$?
if [ $GIT_PULL_STATUS -ne 0 ]; then
    echo "--- $(date) --- Git pull failed (status $GIT_PULL_STATUS). Aborting populate. ---" >> "$LOGFILE" 2>&1
    exit 1
fi
echo "Git pull successful." >> "$LOGFILE" 2>&1

# --- 2. データベースを更新 ---
echo "Running populate_db.py..." >> "$LOGFILE" 2>&1
sudo -u "$GIT_USER" HOME="$USER_HOME" "$VENV_PYTHON" "$POPULATE_SCRIPT" >> "$LOGFILE" 2>&1
POPULATE_STATUS=$?
if [ $POPULATE_STATUS -ne 0 ]; then
    echo "--- $(date) --- populate_db.py failed (status $POPULATE_STATUS). ---" >> "$LOGFILE" 2>&1
    exit 1
fi
echo "Populate script successful." >> "$LOGFILE" 2>&1

# --- 3. ボットサービスを再起動 ---
echo "Restarting discord-bot (docker-compose)..." >> "$LOGFILE" 2>&1
docker-compose -f /home/Quromorina/mybot/Discordbot-Kal-tsit/docker-compose.yml restart >> "$LOGFILE" 2>&1
RESTART_STATUS=$?
if [ $RESTART_STATUS -ne 0 ]; then
    echo "--- $(date) --- docker-compose restart failed (status $RESTART_STATUS). ---" >> "$LOGFILE" 2>&1
    exit 1
fi
echo "docker-compose restarted successfully." >> "$LOGFILE" 2>&1

echo "--- $(date) --- Arknights Data Update Completed Successfully. ---" >> "$LOGFILE" 2>&1
exit 0
