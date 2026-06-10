import asyncio
from datetime import datetime
import html
import json
import os
import random
import re
import time
import xml.etree.ElementTree as ET

# YECHIM: Yangi Google SDK
from google import genai
import requests
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import URLInputFile
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@abduvo")
POLL_INTERVAL_SECONDS = 10800 

DB_FILE = "sent_links.json"
MAX_SAVED_LINKS = 200
GOOGLE_NEWS_BASE_URL = "https://news.google.com/rss/search"

# Global o'zgaruvchilar
RUNNING_SENT_LINKS = set()

# YECHIM: Yangi SDK bo'yicha Client yaratish
client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

SEARCH_QUERIES = ["python programming", "javascript react", "AI LLM Gemini", "github open source", "docker kubernetes"]
INCLUDE_KEYWORDS = ["python", "javascript", "ai", "llm", "docker", "github", "react"]
EXCLUDE_KEYWORDS = ["siyosat", "futbol", "kino", "narx"]

def log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

def strip_html(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()

def load_sent_links():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
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
    # Promptni aniqroq qildik
    prompt = f"Ushbu texnologik yangilikni o'zbek tiliga professional tarjima qiling. FAQAT o'zbekcha javob qaytaring: {title}"
    try:
        if client:
            # YECHIM: Yangi SDK chaqiruvi (xatolikni oldini oladi)
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
                await bot.send_message(chat_id=CHANNEL_ID, text=f"🖥 <b>Texno-Yangilik</b>\n\n{text}\n\n🔗 <a href='{news['link']}'>Batafsil</a>")
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
    log("Bot ishga tushdi.")
    while True:
        await check_and_send_news()
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())