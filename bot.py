import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import json
import asyncio
from flask import Flask
from threading import Thread
import os
# 啟動迷你網頁，讓 Render 持續上線
app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
# 讀取設定檔
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = config["token"]
CHANNEL_ID = int(config["channel_id"])
PTT_URL = "https://www.ptt.cc/bbs/PC_Shopping/index.html"
seen_links = set()

# 設定 Intents
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 抓取 PTT 電蝦文章
def fetch_articles():
    headers = {"cookie": "over18=1"}
    res = requests.get(PTT_URL, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    entries = soup.select("div.r-ent")
    new_articles = []

    for entry in entries:
        a_tag = entry.select_one("div.title a")
        if not a_tag:
            continue

        title = a_tag.text.strip()
        href = "https://www.ptt.cc" + a_tag["href"]
        push = entry.select_one("div.nrec").text.strip()
        author = entry.select_one("div.meta .author").text.strip()

        if href not in seen_links:
            seen_links.add(href)
            new_articles.append({
                "title": title,
                "href": href,
                "author": author,
                "push": push or "0"
            })

    return new_articles[::-1]

@bot.event
async def on_ready():
    print(f"✅ 成功登入 Discord Bot：{bot.user}")
    try:
        channel = await bot.fetch_channel(CHANNEL_ID)
        await channel.send("🤖 機器人已啟動，開始監控 PTT 電蝦版。")
    except Exception as e:
        print(f"[錯誤] 發送啟動訊息失敗：{e}")
        return

    while True:
        try:
            print("🔍 正在抓取 PTT 電蝦文章...")
            articles = fetch_articles()
            print(f"📥 抓到 {len(articles)} 篇新文章")
            for article in articles:
                embed = discord.Embed(title=article["title"], url=article["href"], color=0x00ff00)
                embed.add_field(name="作者", value=article["author"], inline=True)
                embed.add_field(name="推文數", value=article["push"], inline=True)
                await channel.send(embed=embed)
        except Exception as e:
            print(f"[錯誤] 推文失敗：{e}")

        await asyncio.sleep(300)  # 每 5 分鐘掃一次

keep_alive()
bot.run(TOKEN)
