import asyncio
from datetime import datetime
import html
import json
import os
import random
import re
import time
import xml.etree.ElementTree as ET

import google.generativeai as genai
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

# QAT'IY 3 SOAT (Railway variables buni ezib yubormasligi uchun kod ichida ham mustahkamlandi)
POLL_INTERVAL_SECONDS = 10800 

DB_FILE = "sent_links.json"
MAX_SAVED_LINKS = 200
GOOGLE_NEWS_BASE_URL = "https://news.google.com/rss/search"

# Server o'chib yonganda kesh yo'qolmasligi uchun vaqtinchalik global xotira
RUNNING_SENT_LINKS = set()

SEARCH_QUERIES = [
    "python programming language",
    "javascript framework react nextjs",
    "artificial intelligence Claude GPT Gemini Codex",
    "machine learning deep learning LLM",
    "github open source release",
    "docker kubernetes devops",
    "web development frontend backend",
    "rust golang typescript programming",
    "openai anthropic google deepmind",
    "software developer tools IDE",
]

INCLUDE_KEYWORDS = [
    "python", "javascript", "typescript", "java ", "golang", "rust ", "php", "c++", "c#",
    "react", "next.js", "nextjs", "vue", "angular", "node.js", "nodejs", "frontend",
    "backend", "fullstack", "framework", "library", "api", "sdk", "github", "gitlab",
    "open source", "programming", "developer", "software engineer", "code", "coding",
    "artificial intelligence", "machine learning", "deep learning", "llm", "large language model",
    "gemini", "chatgpt", "gpt-", "claude", "codex", "copilot", "openai", "anthropic",
    "database", "postgresql", "mongodb", "redis", "sql", "docker", "kubernetes", "devops",
    "cloud computing", "aws", "vercel", "ide", "vs code"
]

EXCLUDE_KEYWORDS = [
    "boshqaruv raisi", "tayinlandi", "prezident", "vazir", "hokimi", "parlament", "saylov",
    "siyosat", "diplomatiya", "elchi", "tashkent metro", "aviakompaniya", "airways",
    "telefon", "smartfon", "iphone", "android telefon", "noutbuk", "notebook", "laptop narx",
    "planshet", "televizor", "kamera", "quloqchin", "airpods", "gadget review", "narx",
    "aksiya", "chegirma", "sotib olish", "futbol", "basketbol", "tennis", "sport",
    "chempionat", "o'yin natija", "kino", "film", "serial", "muzika", "konsert",
    "ob-havo", "zilzila", "voqea", "tashrif", "uchrashuv", "imzolandi", "shartnoma"
]

TOPIC_HASHTAGS = {
    "python": "#Python", "javascript": "#JavaScript", "typescript": "#TypeScript",
    "java": "#Java", "golang": "#Golang", "rust": "#Rust", "php": "#PHP",
    "ai": "#AI", "llm": "#LLM", "gemini": "#Gemini", "chatgpt": "#ChatGPT",
    "gpt": "#GPT", "claude": "#Claude", "docker": "#Docker", "kubernetes": "#Kubernetes",
    "devops": "#DevOps", "github": "#GitHub", "open source": "#OpenSource",
    "database": "#Database", "cloud": "#Cloud", "frontend": "#Frontend",
    "backend": "#Backend", "fullstack": "#Fullstack",
}

TOPIC_FALLBACK_IMAGES = {
    "python": ["https://images.unsplash.com/photo-1526379095098-d400fd0bf935", "https://images.unsplash.com/photo-1515879218367-8466d910aaa4"],
    "javascript": ["https://images.unsplash.com/photo-1627398242454-45a1465c2479", "https://images.unsplash.com/photo-1592609931095-54a2168ae893"],
    "react": ["https://images.unsplash.com/photo-1633356122544-f134324a6cee"],
    "typescript": ["https://images.unsplash.com/photo-1629654297299-c8506221ca97"],
    "docker": ["https://images.unsplash.com/photo-1605745341112-85968b19335b", "https://images.unsplash.com/photo-1667372393119-3d4c48d07fc9"],
    "kubernetes": ["https://images.unsplash.com/photo-1667372393119-3d4c48d07fc9"],
    "ai": ["https://images.unsplash.com/photo-1677442135703-1787eea5ce01", "https://images.unsplash.com/photo-1620712943543-bcc4688e7485", "https://images.unsplash.com/photo-1655720828018-edd2daec9349"],
    "llm": ["https://images.unsplash.com/photo-1677442135703-1787eea5ce01"],
    "github": ["https://images.unsplash.com/photo-1618401471353-b98afee0b2eb"],
    "cloud": ["https://images.unsplash.com/photo-1544197150-b99a580bb7a8"],
    "database": ["https://images.unsplash.com/photo-1544383835-bda2bc66a55d"],
    "devops": ["https://images.unsplash.com/photo-1667372393119-3d4c48d07fc9"],
}

DEFAULT_FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1461749280684-dccba630e2f6",
    "https://images.unsplash.com/photo-1504639725590-34d0984388bd",
    "https://images.unsplash.com/photo-1517694712202-14dd9538aa97",
    "https://images.unsplash.com/photo-1542831371-29b0f74f9713",
]

# API Versiya muammolarini chetlab o'tish uchun to'g'rilangan blok
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # v1beta xatosini bermasligi uchun qat'iy model va konfiguratsiya sozlamalari
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={"response_mime_type": "text/plain"}
    )
else:
    model = None


def log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def strip_html(raw_text):
    if not raw_text:
        return ""
    clean_text = re.sub(r"<[^>]+>", "", raw_text)
    return html.unescape(clean_text).strip()


def is_coding_news(title, summary):
    title_lower = title.lower()
    text = f"{title} {summary}".lower()

    if any(keyword in title_lower for keyword in EXCLUDE_KEYWORDS) or any(keyword in text for keyword in EXCLUDE_KEYWORDS):
        return False

    title_match = any(keyword in title_lower for keyword in INCLUDE_KEYWORDS)
    if not title_match:
        return False

    match_count = sum(1 for keyword in INCLUDE_KEYWORDS if keyword in text)
    return match_count >= 2


def get_topic_hashtags(title, summary):
    text = f"{title} {summary}".lower()
    found = []
    for keyword, hashtag in TOPIC_HASHTAGS.items():
        if keyword in text and hashtag not in found:
            found.append(hashtag)
        if len(found) >= 4:
            break
    base_tags = ["#TechUz", "#Dasturlash"]
    all_tags = found + [t for t in base_tags if t not in found]
    return " ".join(all_tags[:5])


def fetch_og_image(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        og_image_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', response.text, re.IGNORECASE)
        if not og_image_match:
            og_image_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', response.text, re.IGNORECASE)

        if og_image_match:
            image_url = og_image_match.group(1).strip()
            if image_url.startswith("http"):
                # Telegram keshini majburiy o'ldirish
                return f"{image_url}&tgcache={int(time.time())}" if "?" in image_url else f"{image_url}?tgcache={int(time.time())}"
    except Exception as e:
        log(f"Rasm yuklashda xato: {e}")
    return None


def get_fallback_image(title, summary):
    text = f"{title} {summary}".lower()
    base_url = random.choice(DEFAULT_FALLBACK_IMAGES)
    
    for topic, images in TOPIC_FALLBACK_IMAGES.items():
        if topic in text:
            base_url = random.choice(images)
            break
            
    # Mutlaqo boshqa-boshqa rasm yuklash signaturasi (Keshni sindiradi)
    return f"{base_url}?w=800&h=450&fit=crop&sig={random.randint(1, 100000)}&t={int(time.time())}"


def load_sent_links():
    global RUNNING_SENT_LINKS
    links = list(RUNNING_SENT_LINKS)
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str) and item.strip():
                        RUNNING_SENT_LINKS.add(item)
                return list(RUNNING_SENT_LINKS)
        except Exception:
            pass
    return links


def save_sent_links(links):
    trimmed_links = links[:MAX_SAVED_LINKS]
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed_links, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Faylga yozish jarayonida xato: {e}")


def mark_link_as_sent(link):
    global RUNNING_SENT_LINKS
    RUNNING_SENT_LINKS.add(link)
    sent_links = load_sent_links()
    updated_links = [link] + [item for item in sent_links if item != link]
    save_sent_links(updated_links)


def extract_google_news_link(link):
    if not link:
        return ""
    if link.startswith("./"):
        return f"https://news.google.com/{link[2:]}"
    return link


def build_google_news_url(query):
    params = {"q": query, "hl": "en", "gl": "US", "ceid": "US:en"}
    prepared = requests.PreparedRequest()
    prepared.prepare_url(GOOGLE_NEWS_BASE_URL, params)
    return prepared.url


def get_latest_news_candidates(limit=40):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    results = []
    seen_links = set()

    for query in SEARCH_QUERIES:
        try:
            response = requests.get(build_google_news_url(query), headers=headers, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            for item in root.findall(".//item"):
                raw_title = item.findtext("title", default="").strip()
                link = extract_google_news_link(item.findtext("link", default="").strip())
                summary = item.findtext("description", default="").strip()
                source = item.findtext("source", default="").strip()

                if not raw_title or not link:
                    continue

                title = raw_title.rsplit(" - ", 1)[0].strip()
                title = " ".join(title.split())
                summary = strip_html(summary) or title

                if len(title) < 15 or link in seen_links:
                    continue

                seen_links.add(link)
                results.append({
                    "title": title, "link": link, "summary": summary, "source": source
                })

                if len(results) >= limit:
                    return results
        except Exception as e:
            log(f"Qidiruvda uzilish yuz berdi ({query}): {e}")

    return results


async def rewrite_with_ai(title, summary):
    """Gemini orqali postni jozibali O'zbekcha matnga aylantiradi."""
    clean_title = strip_html(title)
    clean_summary = strip_html(summary)
    
    prompt = (
        "Siz dasturchilar uchun mo'ljallangan o'zbek tilidagi Telegram kanali adminisiz.\n\n"
        "VAZIFA: Quyidagi texnologik yangilikni O'ZBEK TILIGA professional, qiziqarli "
        "va tushunarli uslubda tarjima qiling va qayta yozing.\n\n"
        "QAT'IY QOIDALAR:\n"
        "- FAQAT o'zbek tilida yozing. Ruscha yoki inglizcha jumlalar umuman ishlatilmasin.\n"
        "- Matn 3-4 ta qisqa va mazmunli xatboshidan iborat bo'lsin.\n"
        "- Gaplar sodda, ammo o'quvchini o'ziga jalb qiladigan bo'lsin.\n"
        "- Eng oxirida '<b>Xulosa:</b>' so'zi bilan boshlanadigan 1 ta qisqa yakuniy gap qo'shing.\n"
        "- Texnik terminlarni (Python, React, API, Docker va h.g.) o'z holicha qoldiring, o'zbekchaga tarjima qilmang.\n"
        "- Telegram HTML formatiga mos ravishda muhim so'zlarni qalin (<b>) yoki og'ma (<i>) qiling.\n\n"
        f"Sarlavha: {clean_title}\n"
        f"Kontent: {clean_summary}"
    )
    try:
        if model is None:
            raise RuntimeError("GEMINI_KEY topilmadi yoki xato sozlangan.")
        
        # Yangi API spetsifikatsiyasiga mos chaqiruv
        response = model.generate_content(prompt)
        generated_text = response.text
        if generated_text:
            return generated_text.strip()
    except Exception as e:
        log(f"Gemini API xatoligi (Zaxira rejimiga o'tilmoqda): {e}")

    # Agar sun'iy intellekt ishlamay qolsa, bot o'chib qolmasligi uchun zaxira matn
    return f"<b>{html.escape(clean_title)}</b>\n\n{html.escape(clean_summary)}"


async def check_and_send_news():
    if not TELEGRAM_TOKEN or not GEMINI_KEY:
        log("XATO: API Tokenlar topilmadi.")
        return False

    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    try:
        log("Yangiliklar bazasi tekshirilmoqda...")
        candidates = get_latest_news_candidates(limit=50)
        if not candidates:
            return False

        candidates = [item for item in candidates if is_coding_news(item["title"], item["summary"])]
        if not candidates:
            log("Mos IT-yangilik topilmadi.")
            return False

        sent_links = set(load_sent_links())
        selected_news = next((item for item in candidates if item["link"] not in sent_links and item["link"] not in RUNNING_SENT_LINKS), None)

        if not selected_news:
            log("Yangi xabar yo'q, barchasi oldin yuborilgan.")
            return False

        source = selected_news.get("source") or "Google News"
        log(f"Yuborish uchun tanlandi: {selected_news['title']}")

        final_text = await rewrite_with_ai(selected_news["title"], selected_news["summary"])
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        hashtags = get_topic_hashtags(selected_news["title"], selected_news["summary"])

        post_content = (
            "🖥 <b>Yangi Texno-Xabar</b>\n"
            f"🗓 {now_str}\n\n"
            f"{final_text}\n\n"
            f"📰 <b>Manba:</b> {html.escape(source)}\n"
            f"🔗 <a href='{html.escape(selected_news['link'], quote=True)}'>Batafsil o'qish</a>\n\n"
            f"{hashtags}"
        )

        image_url = fetch_og_image(selected_news["link"])
        if not image_url:
            image_url = get_fallback_image(selected_news["title"], selected_news["summary"])

        try:
            photo = URLInputFile(image_url)
            await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=post_content)
            log("Post muvaffaqiyatli yuborildi.")
            mark_link_as_sent(selected_news["link"])
            return True
        except Exception as img_err:
            log(f"Rasm yuborishda xato, faqat matnning o'zi ketmoqda: {img_err}")
            await bot.send_message(chat_id=CHANNEL_ID, text=post_content)
            mark_link_as_sent(selected_news["link"])
            return True

    except Exception as e:
        log(f"Xato yuz berdi: {e}")
        return False
    finally:
        await bot.session.close()


async def main():
    cycle = 1
    load_sent_links()
    
    while True:
        log(f"{cycle}-tsikl boshlandi.")
        try:
            await check_and_send_news()
        except Exception as e:
            log(f"Sikl ichida kutilmagan xato: {e}")

        log(f"Kutish rejimi: {POLL_INTERVAL_SECONDS} soniya (Roppa-rosa 3 soat)...")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        cycle += 1


if __name__ == "__main__":
    asyncio.run(main())