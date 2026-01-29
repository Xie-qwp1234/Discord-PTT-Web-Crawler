from __future__ import annotations

import asyncio
import os
import sys
from threading import Thread
from typing import Any, cast

import discord
import requests
from bs4 import BeautifulSoup
from discord import TextChannel, Thread as DiscordThread
from discord.abc import GuildChannel, PrivateChannel
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask


load_dotenv()
TOKEN: str | None = os.getenv('TOKEN')
RAW_ID: str | None = os.getenv('CHANNEL_ID')
CHANNEL_ID: int = int(RAW_ID) if RAW_ID else 0

app: Flask = Flask(__name__)


@app.route('/')
def health_check() -> tuple[str, int]:
    if bot.is_ready():
        return 'PTT Bot is online and healthy!', 200
    else:
        return 'Bot is offline or rate limited', 503


def run_flask() -> None:
    port: int = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)


def keep_alive() -> None:
    t: Thread = Thread(target=run_flask, daemon=True)
    t.start()


PTT_URL: str = 'https://www.ptt.cc/bbs/PC_Shopping/index.html'
seen_links: set[str] = set()

intents: discord.Intents = discord.Intents.default()
intents.message_content = True

bot: commands.Bot = commands.Bot(command_prefix='!', intents=intents)


def fetch_articles() -> list[dict[str, str]]:
    try:
        headers: dict[str, str] = {
            'cookie': 'over18=1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        res: requests.Response = requests.get(PTT_URL, headers=headers, timeout=10)
        res.raise_for_status()

        soup: BeautifulSoup = BeautifulSoup(res.text, 'lxml')
        entries: Any = soup.select('div.r-ent')
        new_articles: list[dict[str, str]] = []

        for entry in entries:
            a_tag: Any = entry.select_one('div.title a')
            if not a_tag:
                continue

            nrec_tag: Any = entry.select_one('div.nrec')
            push_count: str = nrec_tag.text.strip() if nrec_tag else '0'

            author_tag: Any = entry.select_one('div.meta .author')
            author_name: str = author_tag.text.strip() if author_tag else 'unknown'

            href: str = f'https://www.ptt.cc{a_tag["href"]}'
            title: str = a_tag.text.strip()

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
        print(f'爬取失敗: {e}')
        return []


@tasks.loop(minutes=5)
async def check_ptt() -> None:
    raw_channel: GuildChannel | PrivateChannel | DiscordThread | None = bot.get_channel(
        CHANNEL_ID
    ) or await bot.fetch_channel(CHANNEL_ID)
    channel: TextChannel = cast(TextChannel, raw_channel)

    if not channel:
        print(f'找不到頻道: {CHANNEL_ID}')
        return

    articles: list[dict[str, str]] = fetch_articles()
    for article in articles:
        embed: discord.Embed = discord.Embed(
            title=article['title'], url=article['href'], color=0x00FF00
        )
        embed.add_field(name='作者', value=article['author'], inline=True)
        embed.add_field(name='推文', value=article['push'], inline=True)

        try:
            await channel.send(embed=embed)
            await asyncio.sleep(1)
        except Exception as e:
            print(f'發送失敗: {e}')


@bot.event
async def on_ready() -> None:
    print(f'機器人 {bot.user} 已成功上線 (Python {sys.version.split()[0]})')
    fetch_articles()
    if not check_ptt.is_running():
        check_ptt.start()


if __name__ == '__main__':
    if not TOKEN or CHANNEL_ID == 0:
        print('錯誤：請確認環境變數 TOKEN 與 CHANNEL_ID 已設定')
    else:
        keep_alive()
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print('遭 Discord 限制 (429 Rate Limit)')
            raise e

