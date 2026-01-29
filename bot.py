import asyncio
import os
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
# 確保 CHANNEL_ID 存在且為整數
RAW_CHANNEL_ID = os.getenv('CHANNEL_ID')
CHANNEL_ID = int(RAW_CHANNEL_ID) if RAW_CHANNEL_ID else 0

# --- Flask Keep Alive 部分 ---
app = Flask(__name__)


@app.route('/')
def home():
    return "I'm alive!"


def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()


# --- 機器人邏輯 ---
PTT_URL = 'https://www.ptt.cc/bbs/PC_Shopping/index.html'
seen_links = set()

intents = discord.Intents.default()
# 如果你的 Bot 需要處理指令，建議開啟 message_content
# intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)


def fetch_articles():
    try:
        headers = {
            'cookie': 'over18=1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        res = requests.get(PTT_URL, headers=headers, timeout=10)
        res.raise_for_status()

        # 使用 lxml 解析 (對應你的 requirements.txt)
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
    # 解決 Pylance 警告：強制轉型為 TextChannel
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
            await asyncio.sleep(1)
        except Exception as e:
            print(f'❌ 發送失敗: {e}')


@bot.event
async def on_ready():
    print(f'✅ 機器人 {bot.user} 已上線')

    # 初始掃描避開舊文
    print('📥 執行初始掃描...')
    fetch_articles()

    if not check_ptt.is_running():
        check_ptt.start()


# --- 主程式進入點 ---
if __name__ == '__main__':
    # 檢查環境變數是否正確載入
    if not TOKEN or CHANNEL_ID == 0:
        print('❌ 錯誤：請確保 .env 檔案中包含 TOKEN 與 CHANNEL_ID')
    else:
        keep_alive()
        bot.run(TOKEN)
