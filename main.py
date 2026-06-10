import asyncio
from datetime import datetime
import html
import json
import os
import random
import re
import time
import xml.etree.ElementTree as ET

# Yangi Google SDK importi
from google import genai
import requests
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import URLInputFile
from dotenv import load_dotenv

load_dotenv()

# Railway'dagi o'zgaruvchilarni olish
GEMINI_KEY = os.getenv("GEMINI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@abduvo")
POLL_INTERVAL_SECONDS = 10800 

DB_FILE = "sent_links.json"
MAX_SAVED_LINKS = 200
GOOGLE_NEWS_BASE_URL = "https://news.google.com/rss/search"

# Global xotira
RUNNING_SENT_LINKS = set()

# Yangi SDK uchun Client yaratish
client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

SEARCH_QUERIES = [
    "python programming language", "javascript react nextjs", 
    "artificial intelligence LLM", "github open source", "docker kubernetes"
]

INCLUDE_KEYWORDS = ["python", "javascript", "react", "ai", "llm", "docker", "github", "web"]
EXCLUDE_KEYWORDS = ["siyosat", "futbol", "kino", "narx", "ob-havo"]

def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

def strip_html(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()

def load_sent_links():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except: return set()
    return set()

def save_sent_links(links):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(list(links)[:MAX_SAVED_LINKS], f)

def get_latest_news_candidates():
    results = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for query in SEARCH_QUERIES:
        try:
            url = f"{GOOGLE_NEWS_BASE_URL}?q={query}&hl=en&gl=US"
            resp = requests.get(url, headers=headers, timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item"):
                title = item.findtext("title")
                link = item.findtext("link")
                if title and link and link not in RUNNING_SENT_LINKS:
                    results.append({"title": title, "link": link})
        except Exception as e: log(f"Qidiruv xatosi: {e}")
    return results

async def rewrite_with_ai(title):
    prompt = f"Texnologik yangilikni o'zbek tiliga professional tarjima qiling va 3 ta qisqa xatboshida yozing: {title}"
    try:
        if client:
            # Yangi SDK bo'yicha chaqiruv
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
            )
            return response.text.strip()
    except Exception as e:
        log(f"Gemini API xatosi: {e}")
    return f"<b>{html.escape(title)}</b>"

async def check_and_send_news():
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        candidates = get_latest_news_candidates()
        for news in candidates:
            text = await rewrite_with_ai(news['title'])
            
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=text)
                RUNNING_SENT_LINKS.add(news['link'])
                save_sent_links(RUNNING_SENT_LINKS)
                log(f"Yuborildi: {news['title']}")
                break
            except Exception as e:
                log(f"Telegram yuborishda xato: {e}")
    finally:
        await bot.session.close()

async def main():
    global RUNNING_SENT_LINKS
    RUNNING_SENT_LINKS = load_sent_links()
    log("Bot muvaffaqiyatli ishga tushdi.")
    while True:
        await check_and_send_news()
        log(f"{POLL_INTERVAL_SECONDS} soniya kutish...")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())