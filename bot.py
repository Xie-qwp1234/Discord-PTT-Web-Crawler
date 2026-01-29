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

# --- Flask Keep Alive ---
app = Flask(__name__)


def home():
    if bot.is_ready():
        return '✅ PTT Bot is online and healthy!', 200
    else:
        return '❌ Bot is offline or starting up...', 503


def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()


# --- 爬蟲邏輯 ---
PTT_URL = 'https://www.ptt.cc/bbs/PC_Shopping/index.html'
seen_links = set()

intents = discord.Intents.default()
intents.message_content = True
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

        return new_articles[::-1]
    except Exception as e:
        print(f'❌ 爬取失敗: {e}')
        return []


@tasks.loop(minutes=5)
async def check_ptt():
    raw_channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
    channel = cast(TextChannel, raw_channel)

    if not channel:
        return

    articles = fetch_articles()
    for article in articles:
        embed = discord.Embed(
            title=article['title'], url=article['href'], color=0x00FF00
        )
        embed.add_field(name='作者', value=article['author'], inline=True)
        embed.add_field(name='推文', value=article['push'], inline=True)

        try:
            await channel.send(embed=embed)
            await asyncio.sleep(1)
        except Exception as e:
            print(f'❌ 發送失敗: {e}')


@bot.event
async def on_ready():
    print(f'機器人 {bot.user} 已上線 (Python {sys.version.split()[0]})')
    fetch_articles()
    if not check_ptt.is_running():
        check_ptt.start()


if __name__ == '__main__':
    if not TOKEN or CHANNEL_ID == 0:
        print('❌ 錯誤：環境變數未設定')
    else:
        keep_alive()
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print('❌ 遭到 Rate Limit，請嘗試更換 Render Region 或稍後再試。')
            else:
                print(f'❌ 發生 HTTP 錯誤: {e}')
