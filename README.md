# Discord-PTT-Web-Crawler
一個能自動爬取 PTT 看板文章，並推送到 Discord 頻道的機器人。 使用者可自行設定看板名稱、Discord Token 與頻道 ID。
## ⚠️ 請新增 .env
```env
TOKEN=你的機器人TOKEN
CHANNEL_ID=你的頻道ID
```
## 使用指南
需求

1. Python 3.10+（<3.13）
2. 一個擁有管理權限的伺服器
3. 能連外網的主機（Linux）

## 1. 在 Discord Developer Portal 建立 Bot

前往 https://discord.com/developers/applications &rarr; New Application &rarr; 取名（例如：PTT Crawler）。

左側 Bot &rarr; Add Bot。

Reset Token / Copy Token：複製「Bot Token」（等等要放到 .env 的 TOKEN）。

Privileged Gateway Intents：這個專案只需要發訊息，不必讀訊息，可以不勾（若未來要讀訊息再開）。

邀請 Bot 進伺服器

到 OAuth2 &rarr; URL Generator

Scopes 勾：bot（可另外勾 applications.commands）

Bot Permissions 只勾最小權限即可：

View Channels（1024）

Send Messages（2048）

Embed Links（16384）

複製產生的 URL，用瀏覽器打開並選你的伺服器 &rarr; Authorize。

⚠️小提醒：若你要的權限更簡單，至少要有 View Channels + Send Messages + Embed Links。

## 2. 取得 Discord 頻道 ID
Discord 用戶端 &rarr; 設定 &rarr; 進階 &rarr; 開啟 開發者模式。

右鍵你的目標頻道 &rarr; Copy ID，貼到 .env 的 CHANNEL_ID。

## 3. 下載與安裝專案
```bash
git clone https://github.com/<你的帳號>/Discord-PTT-Web-Crawler.git
cd Discord-PTT-Web-Crawler

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4. 修改 .env
```env
TOKEN=你的機器人TOKEN
CHANNEL_ID=你的頻道ID
```

## 5. 本機測試執行
```bash
python bot.py
```

## 6.（選用）Linux 伺服器常駐執行（systemd）
1. 編輯服務檔
  ```ini
  # /etc/systemd/system/dcpttbot.service
  [Unit]
  Description=Discord Bot - dcpttbot
  After=network.target

  [Service]
  Type=simple
  WorkingDirectory=/home/dcptt
  ExecStart=/home/dcptt/venv/bin/python /home/dcptt/bot.py
  Restart=always
  RestartSec=5
  User=dcptt
  EnvironmentFile=/home/dcptt/.env

  [Install]
  WantedBy=multi-user.target
  ```
2. 啟用與檢查
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable dcpttbot
  sudo systemctl start dcpttbot
  sudo systemctl status dcpttbot
  ```

## 7. 常見問題 (FAQ)
機器人不說話

確認 .env 的 TOKEN 正確且未過期。

檢查 DISCORD_CHANNEL_ID 是否真的是數字、且 Bot 已被加入該伺服器與頻道可見。

檢查頻道權限：Bot 是否具備View Channels／Send Messages／Embed Links

## 8. 想監控別的看板
改 .env 的 PTT_BOARD &rarr; 重新啟動
