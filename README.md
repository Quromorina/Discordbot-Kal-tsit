雑にいろんな機能を搭載したDiscordボットです。

・/コマンド各種(ダイスロール、ガチャ、じゃんけん等)

・/configureでVC参加時に特定ロールに向けて通知が飛ぶよう設定できます。(/configure statusで確認、/configure deleteで設定削除)

・@メンションすることで会話可能。アークナイツのケルシーのようなキャラ設定にしているので結構冷たい。

・アークナイツのキャラデータ、勢力データも読み込ませているのでアークナイツ関連はある程度答えてくれます。
	 →/search キャラ名　コマンドでキャラのプロファイル、スキル、素質情報

・.envで指定すれば特定チャンネルに毎朝その日の天気情報を通知してくれます。デフォルトは東京。

 .envは個人で用意する必要があります。
    
	Discord botトークン(DISCORD_TOKEN)
 
	Open weather API(OPENWEATHER_API_KEY)
 
	Google Gemini API(GEMINI_API_KEY)
	↑最低限必要
 
	↓天気通知が必要であれば以下も設定
    
	通知したいチャンネルID（WEATHER_USER_ID）
    
	通知したいチャンネルID2 (WEATHER_FRIEND_ID)
    
	WEATHER_CITY_NAME=Tokyo,JP
    
	WEATHER_NOTIFY_TIME=06:00

   
