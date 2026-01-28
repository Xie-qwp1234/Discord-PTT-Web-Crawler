import os
import time
import threading
import random
import traceback

import requests
from bs4 import BeautifulSoup
from flask import Flask
import discord
from discord.ext import tasks
from dotenv import load_dotenv

# =========================
# Env
# =========================
load_dotenv()  # 本機用；Render 上用 Dashboard 設環境變數即可

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()

PTT_BOARD = os.getenv("PTT_BOARD", "PC_Shopping").strip()
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "60"))  # 建議 60~180
PORT = int(os.getenv("PORT", "8080"))

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN env var")
if not CHANNEL_ID.isdigit():
    raise RuntimeError("CHANNEL_ID must be a number (Discord channel id)")

CHANNEL_ID = int(CHANNEL_ID)

# =========================
# Flask keep-alive web
# =========================
app = Flask(__name__)

@app.get("/")
def home():
    return "OK", 200

@app.get("/healthz")
def healthz():
    return "healthy", 200

def run_web():
    # Render Web Service 需要你 listen 這個 PORT
    app.run(host="0.0.0.0", port=PORT)

# =========================
# PTT fetcher (anti-crash)
# =========================
session = requests.Session()
session.cookies.set("over18", "1")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

def is_cloudflare_block(text: str) -> bool:
    t = (text or "").lower()
    # 你截圖那種 cf-error-details / cloudflare footer
    return ("cf-error-details" in t) or ("cloudflare" in t and "error" in t)

def fetch_ptt_index_html(board: str, max_retry: int = 5) -> str | None:
    url = f"https://www.ptt.cc/bbs/{board}/index.html"
    for i in range(max_retry):
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            # 5xx or cloudflare block
            if r.status_code >= 500 or is_cloudflare_block(r.text):
                wait = 8 * (i + 1) + random.randint(0, 3)
                print(f"[PTT] Blocked/5xx ({r.status_code}). retry {i+1}/{max_retry}, sleep {wait}s")
                time.sleep(wait)
                continue

            if r.status_code != 200:
                wait = 5 * (i + 1)
                print(f"[PTT] HTTP {r.status_code}. retry {i+1}/{max_retry}, sleep {wait}s")
                time.sleep(wait)
                continue

            return r.text

        except Exception as e:
            wait = 6 * (i + 1)
            print(f"[PTT] Exception: {e}. retry {i+1}/{max_retry}, sleep {wait}s")
            time.sleep(wait)

    return None

def parse_latest_articles(html: str, limit: int = 10):
    soup = BeautifulSoup(html, "html.parser")
    entries = soup.select("div.r-ent")
    results = []

    for ent in entries[:limit]:
        title_el = ent.select_one("div.title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = "https://www.ptt.cc" + title_el.get("href", "")
        results.append((title, link))

    return results

# =========================
# Discord bot
# =========================
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# 簡單去重：記住最後一篇 link
last_seen_link = None

@client.event
async def on_ready():
    print(f"[Discord] Logged in as {client.user} (board={PTT_BOARD})")
    if not poll_ptt.is_running():
        poll_ptt.start()

@tasks.loop(seconds=CHECK_INTERVAL_SEC)
async def poll_ptt():
    global last_seen_link

    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        print("[Discord] Channel not found. Check CHANNEL_ID and bot permissions.")
        return

    html = fetch_ptt_index_html(PTT_BOARD, max_retry=4)
    if not html:
        # 連續失敗：不崩潰，下一輪再試
        print("[PTT] Failed to fetch index after retries. Will try later.")
        return

    articles = parse_latest_articles(html, limit=8)
    if not articles:
        print("[PTT] No articles parsed (maybe blocked HTML or layout change).")
        return

    newest_title, newest_link = articles[0]

    # 第一次啟動：只記錄不發，避免一上線就洗版
    if last_seen_link is None:
        last_seen_link = newest_link
        print(f"[PTT] Init last_seen_link = {last_seen_link}")
        return

    # 有新文章才發
    if newest_link != last_seen_link:
        last_seen_link = newest_link
        msg = f"🆕 **{newest_title}**\n{newest_link}"
        try:
            await channel.send(msg)
            print("[Discord] Sent:", newest_title)
        except Exception:
            print("[Discord] Send failed:")
            traceback.print_exc()

@poll_ptt.before_loop
async def before_poll():
    await client.wait_until_ready()

def main():
    # 先開 web server（給 Render/UptimeRobot 用）
    t = threading.Thread(target=run_web, daemon=True)
    t.start()

    # 再跑 Discord bot（主線程）
    client.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
