import asyncio
import os
import sys
from threading import Thread
from typing import cast

import discord
import requests
from bs4 import BeautifulSoup
from discord import TextChannel
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask


# --- 載入環境變數 ---
load_dotenv()
TOKEN = os.getenv('TOKEN')
RAW_ID = os.getenv('CHANNEL_ID')
CHANNEL_ID = int(RAW_ID) if RAW_ID else 0

# --- Flask Keep Alive (確保 Render 存活) ---
app = Flask(__name__)


@app.route('/')
def home():
    return 'Bot is alive and monitoring PTT!'


def run():
    # Render 會自動分配 Port 到環境變數，預設 8080
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()


# --- 爬蟲邏輯 ---
PTT_URL = 'https://www.ptt.cc/bbs/PC_Shopping/index.html'
seen_links = set()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)


def fetch_articles():
    try:
        headers = {
            'cookie': 'over18=1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        res = requests.get(PTT_URL, headers=headers, timeout=10)
        res.raise_for_status()

        # 使用 lxml 解析
        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.select('div.r-ent')
        new_articles = []

        for entry in entries:
            a_tag = entry.select_one('div.title a')
            if not a_tag:
                continue

            href = f'https://www.ptt.cc{a_tag["href"]}'
            title = a_tag.text.strip()

            nrec_tag = entry.select_one('div.nrec')
            push = nrec_tag.text.strip() if nrec_tag else '0'

            author_tag = entry.select_one('div.meta .author')
            author = author_tag.text.strip() if author_tag else 'unknown'

            if href not in seen_links:
                seen_links.add(href)
                new_articles.append(
                    {'title': title, 'href': href, 'author': author, 'push': push}
                )

        return new_articles[::-1]  # 確保新文章按時間順序發送
    except Exception as e:
        print(f'❌ 爬取失敗: {e}')
        return []


# --- 定時監控任務 ---
@tasks.loop(minutes=5)
async def check_ptt():
    raw_channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
    channel = cast(TextChannel, raw_channel)

    if not channel:
        print(f'⚠️ 找不到頻道 ID: {CHANNEL_ID}')
        return

    articles = fetch_articles()
    for article in articles:
        embed = discord.Embed(
            title=article['title'], url=article['href'], color=0x1D9BF0
        )
        embed.add_field(name='👤 作者', value=article['author'], inline=True)
        embed.add_field(name='🔥 推文', value=article['push'], inline=True)

        try:
            await channel.send(embed=embed)
            await asyncio.sleep(1)  # 延遲 1 秒避免觸發速率限制
        except Exception as e:
            print(f'❌ 訊息發送失敗: {e}')


@bot.event
async def on_ready():
    # 修正 sys 屬性存取
    print(f'✅ 機器人 {bot.user} 已上線 (Python {sys.version.split()[0]})')

    # 執行初始掃描，避免啟動時將舊文章全部噴出
    print('📥 正在進行初始掃描...')
    fetch_articles()

    if not check_ptt.is_running():
        check_ptt.start()


# --- 主程式進入點 ---
if __name__ == '__main__':
    if not TOKEN or CHANNEL_ID == 0:
        print('❌ 錯誤：請確認 .env 檔案或 Render 環境變數已設定 TOKEN 與 ID')
    else:
        keep_alive()
        bot.run(TOKEN)
