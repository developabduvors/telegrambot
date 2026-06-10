import asyncio
import os
import html
import re
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from google import genai
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# 1. Sozlamalar
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@abduvo")
DB_FILE = "sent_links.json"

# Gemini Client
client = genai.Client(api_key=GEMINI_KEY)

# 2. Yordamchi funksiyalar
def log(msg): print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return []

def save_db(links):
    with open(DB_FILE, "w") as f: json.dump(links[-200:], f)

def get_image(link):
    try:
        resp = requests.get(link, timeout=5)
        m = re.search(r'<meta property="og:image" content="(.*?)"', resp.text)
        return m.group(1) if m else "https://picsum.photos/800/400"
    except: return "https://picsum.photos/800/400"

# 3. AI Tarjima
async def ai_rewrite(title):
    prompt = (f"Ushbu texnologik yangilikni o'zbek tiliga professional, jozibali qilib tarjima qiling. "
              f"3 ta qisqa xatboshida yozing. Oxirida xulosa qiling. FAQAT o'zbek tilida: {title}")
    try:
        res = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return res.text
    except Exception as e:
        log(f"AI Xatosi: {e}")
        return title

# 4. Asosiy logika
async def run_bot():
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    links = load_db()
    
    try:
        resp = requests.get("https://news.google.com/rss/search?q=technology&hl=uz", timeout=10)
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        
        for item in items[:5]:
            title = item.findtext("title")
            link = item.findtext("link")
            
            if link not in links:
                text = await ai_rewrite(title)
                img = get_image(link)
                
                caption = (f"🖥 <b>Texno-Yangilik</b>\n\n{text}\n\n"
                           f"#Texnologiya #AI #Dasturlash #Yangiliklar\n\n"
                           f"🔗 <a href='{link}'>Batafsil o'qish</a>")
                
                await bot.send_photo(chat_id=CHANNEL_ID, photo=img, caption=caption)
                links.append(link)
                save_db(links)
                log("Post yuborildi!")
                break
    except Exception as e:
        log(f"Asosiy xato: {e}")
    finally:
        await bot.session.close()

async def main():
    while True:
        await run_bot()
        await asyncio.sleep(10800) # 3 soat

if __name__ == "__main__":
    asyncio.run(main())