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


# 嘗試在最開頭解決 3.13 audioop 缺失問題
try:
    import audioop
except ImportError:
    try:
        # 嘗試從音訊補丁套件載入
        import audioop_lpm as audioop

        sys.modules['audioop'] = audioop
        print('✅ 已成功載入 Python 3.13 audioop 補丁')
    except ImportError:
        # 如果不使用語音功能，這樣可以防止 discord.py 在匯入時直接崩潰
        print('⚠️ 警告：找不到 audioop。若 discord.py 報錯，請安裝 audioop-lpm')

# --- 載入環境變數 ---
load_dotenv()
# 注意：你的環境變數 Key 必須與 Render 設定一致 (TOKEN 或 DISCORD_TOKEN)
TOKEN = os.getenv('TOKEN')
RAW_ID = os.getenv('CHANNEL_ID')
CHANNEL_ID = int(RAW_ID) if RAW_ID else 0

# --- Flask Keep Alive ---
app = Flask(__name__)


@app.route('/')
def home():
    return 'Bot is alive and monitoring PTT!'


def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()


# --- 爬蟲邏輯 ---
PTT_URL = 'https://www.ptt.cc/bbs/PC_Shopping/index.html'
seen_links = set()

# 針對 3.13 優化 intents
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
    try:
        # 3.13 建議使用 get_partial_messageable 或確保 fetch
        raw_channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        channel = cast(TextChannel, raw_channel)

        if not channel:
            return

        articles = fetch_articles()
        for article in articles:
            embed = discord.Embed(
                title=article['title'], url=article['href'], color=0x1D9BF0
            )
            embed.add_field(name='👤 作者', value=article['author'], inline=True)
            embed.add_field(name='🔥 推文', value=article['push'], inline=True)

            await channel.send(embed=embed)
            await asyncio.sleep(1)
    except Exception as e:
        print(f'⚠️ 迴圈執行異常: {e}')


@bot.event
async def on_ready():
    print(f'✅ 機器人 {bot.user} 已上線 (Python {sys.version.split()[0]})')
    # 初始執行一次填充 seen_links
    fetch_articles()
    if not check_ptt.is_running():
        check_ptt.start()


if __name__ == '__main__':
    if not TOKEN or CHANNEL_ID == 0:
        print('❌ 錯誤：請確認環境變數已設定')
    else:
        keep_alive()
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f'❌ 啟動失敗: {e}')
