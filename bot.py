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

# --- Flask Web Server ---
app = Flask(__name__)


@app.route('/')
def health_check():
    # 當 Bot 成功登入 (is_ready) 時才回傳 200，否則回傳 503
    if bot.is_ready():
        return '✅ PTT Bot is online and healthy!', 200
    else:
        return '❌ Bot is offline or rate limited', 503


def run_flask():
    # Render 預設使用 PORT 環境變數
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()


# --- 機器人與爬蟲邏輯 ---
PTT_URL = 'https://www.ptt.cc/bbs/PC_Shopping/index.html'
seen_links = set()

intents = discord.Intents.default()
intents.message_content = True  # 開啟訊息內容意圖

bot = commands.Bot(command_prefix='!', intents=intents)


def fetch_articles():
    try:
        headers = {
            'cookie': 'over18=1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        res = requests.get(PTT_URL, headers=headers, timeout=10)
        res.raise_for_status()

        soup = BeautifulSoup(res.text, 'lxml')
        entries = soup.select('div.r-ent')
        new_articles = []

        for entry in entries:
            a_tag = entry.select_one('div.title a')
            if not a_tag:
                continue

            nrec_tag = entry.select_one('div.nrec')
            push_count = nrec_tag.text.strip() if nrec_tag else '0'

            author_tag = entry.select_one('div.meta .author')
            author_name = author_tag.text.strip() if author_tag else 'unknown'

            href = f'https://www.ptt.cc{a_tag["href"]}'
            title = a_tag.text.strip()

            if href not in seen_links:
                seen_links.add(href)
                new_articles.append(
                    {
                        'title': title,
                        'href': href,
                        'author': author_name,
                        'push': push_count,
                    }
                )

        return new_articles[::-1]
    except Exception as e:
        print(f'❌ 爬取失敗: {e}')
        return []


@tasks.loop(minutes=5)
async def check_ptt():
    raw_channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
    channel = cast(TextChannel, raw_channel)

    if not channel:
        print(f'⚠️ 找不到頻道: {CHANNEL_ID}')
        return

    articles = fetch_articles()
    for article in articles:
        embed = discord.Embed(
            title=article['title'],
            url=article['href'],
            color=0x1D9BF0,
        )
        embed.add_field(name='作者', value=article['author'], inline=True)
        embed.add_field(name='推文', value=article['push'], inline=True)

        try:
            await channel.send(embed=embed)
            await asyncio.sleep(1)  # 延遲 1 秒避免觸發速率限制
        except Exception as e:
            print(f'❌ 發送失敗: {e}')


@bot.event
async def on_ready():
    print(f'✅ 機器人 {bot.user} 已成功上線 (Python {sys.version.split()[0]})')
    fetch_articles()
    if not check_ptt.is_running():
        check_ptt.start()


if __name__ == '__main__':
    if not TOKEN or CHANNEL_ID == 0:
        print('❌ 錯誤：請確認環境變數 TOKEN 與 CHANNEL_ID 已設定')
    else:
        keep_alive()
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print(
                    '❌ 遭 Discord 限制 (429 Rate Limit)。Web 狀態已同步設為紅燈 (503)。'
                )
            raise e
