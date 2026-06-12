import asyncio
import os
import html
import re
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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

# O'zbekiston vaqti (Railway UTC da turadi, shuning uchun majburan belgilaymiz)
TZ = ZoneInfo("Asia/Tashkent")
# Kuniga 3 marta: ertalab, obed payti, kechqurun (soat:minut)
POST_TIMES = [(8, 0), (13, 0), (20, 0)]

# Gemini Client
client = genai.Client(api_key=GEMINI_KEY)

# 2. Yordamchi funksiyalar
def log(msg): print(f"[{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return []

def save_db(links):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(links[-200:], f)

def clean_html(raw):
    # RSS description ichidagi HTML teglarni tozalaydi
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def get_image(link):
    try:
        resp = requests.get(link, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        m = re.search(r'<meta[^>]+property="og:image"[^>]+content="(.*?)"', resp.text)
        if not m:
            m = re.search(r'<meta[^>]+content="(.*?)"[^>]+property="og:image"', resp.text)
        return html.unescape(m.group(1)) if m else "https://picsum.photos/800/400"
    except Exception:
        return "https://picsum.photos/800/400"

# 3. AI Tarjima — endi sarlavha + tavsifni to'liq maqolaga aylantiradi
async def ai_rewrite(title, description):
    prompt = (
        "Sen professional texnologiya jurnalistisan. Quyidagi yangilikni o'zbek tilida "
        "jonli, jozibali va MUFASSAL qilib yoz. 4-5 ta xatboshi bo'lsin, har biri 2-3 jumladan. "
        "Yangilikning mohiyatini ochib ber, nima uchun muhimligini tushuntir. "
        "Oxirida qisqa xulosa qil. FAQAT o'zbek tilida yoz, ortiqcha izohsiz.\n\n"
        f"SARLAVHA: {title}\n\n"
        f"TAVSIF: {description}"
    )
    # Bir nechta modelni navbat bilan sinaydi (biri ishlamasa ikkinchisi)
    for model in ("gemini-2.0-flash", "gemini-2.5-flash", "gemini-flash-latest"):
        try:
            res = await asyncio.to_thread(
                client.models.generate_content, model=model, contents=prompt
            )
            if res and res.text:
                return res.text.strip()
        except Exception as e:
            log(f"AI Xatosi ({model}): {e}")
    return None  # Tarjima bo'lmasa post qilmaymiz

# 4. Bitta post yuborish
async def post_one(bot, links):
    resp = requests.get(
        "https://news.google.com/rss/search?q=technology&hl=uz&gl=UZ&ceid=UZ:uz",
        timeout=15,
    )
    root = ET.fromstring(resp.content)
    items = root.findall(".//item")

    for item in items[:15]:
        title = item.findtext("title")
        link = item.findtext("link")
        description = clean_html(item.findtext("description"))

        if link and link not in links:
            text = await ai_rewrite(title, description)
            if not text:
                log("Tarjima bo'lmadi, keyingi yangilikka o'tildi")
                continue

            img = get_image(link)
            caption = (
                f"🖥 <b>Texno-Yangilik</b>\n\n{text}\n\n"
                f"#Texnologiya #AI #Dasturlash #Yangiliklar\n\n"
                f"🔗 <a href='{link}'>Batafsil o'qish</a>"
            )
            # Telegram caption limiti 1024 belgi — oshsa qisqartiramiz
            if len(caption) > 1024:
                caption = caption[:1000].rsplit(" ", 1)[0] + "..."

            await bot.send_photo(chat_id=CHANNEL_ID, photo=img, caption=caption)
            links.append(link)
            save_db(links)
            log("✅ Post yuborildi!")
            return True

    log("Yangi yangilik topilmadi")
    return False

async def run_bot():
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await post_one(bot, load_db())
    except Exception as e:
        log(f"Asosiy xato: {e}")
    finally:
        await bot.session.close()

# 5. Keyingi belgilangan vaqtgacha kutish
def seconds_until_next_post():
    now = datetime.now(TZ)
    candidates = []
    for h, m in POST_TIMES:
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if t <= now:
            t += timedelta(days=1)  # bugun o'tib ketgan bo'lsa ertaga
        candidates.append(t)
    nxt = min(candidates)
    return (nxt - now).total_seconds(), nxt

async def main():
    log("Bot ishga tushdi. Post vaqtlari: " + ", ".join(f"{h:02d}:{m:02d}" for h, m in POST_TIMES))
    while True:
        wait, nxt = seconds_until_next_post()
        log(f"Keyingi post: {nxt.strftime('%Y-%m-%d %H:%M')} ({int(wait/60)} daqiqadan keyin)")
        await asyncio.sleep(wait)
        await run_bot()
        await asyncio.sleep(60)  # bir daqiqalik vaqt oynasini o'tkazib yuboramiz

if __name__ == "__main__":
    asyncio.run(main())
