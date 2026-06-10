import asyncio
from datetime import datetime
import html
import json
import os
import re
import xml.etree.ElementTree as ET

import google.generativeai as genai
import requests
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@abduvo")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "10800"))
DB_FILE = "sent_links.json"
LEGACY_DB_FILE = "last_news.txt"
MAX_SAVED_LINKS = 200
GOOGLE_NEWS_BASE_URL = "https://news.google.com/rss/search"
SEARCH_QUERIES = [
    "dasturlash",
    "sun'iy intellekt",
    "python OR javascript OR java OR golang OR rust",
    "backend OR frontend OR api OR database",
    "startup OR open source OR github",
    "texnologiya",
]

INCLUDE_KEYWORDS = [
    "dastur",
    "dasturchi",
    "program",
    "developer",
    "software",
    "python",
    "javascript",
    "typescript",
    "java",
    "golang",
    "go ",
    "rust",
    "php",
    "c++",
    "c#",
    "frontend",
    "backend",
    "fullstack",
    "framework",
    "library",
    "api",
    "sdk",
    "github",
    "gitlab",
    "open source",
    "coding",
    "kod",
    "kodlash",
    "sun'iy intellekt",
    "ai",
    "llm",
    "gemini",
    "chatgpt",
    "gpt",
    "claude",
    "agent",
    "database",
    "postgres",
    "mongodb",
    "sql",
    "cloud",
    "docker",
    "kubernetes",
    "devops",
    "cybersecurity",
    "xavfsizlik",
    "startup",
]

EXCLUDE_KEYWORDS = [
    "telefon",
    "smartfon",
    "iphone",
    "android telefon",
    "noutbuk",
    "notebook",
    "laptop",
    "kompyuter narx",
    "planshet",
    "televizor",
    "tv",
    "kamera",
    "quloqchin",
    "airpods",
    "gadjet",
    "gadget",
    "processor narx",
    "videokarta narx",
    "narx",
    "aksiya",
    "chegirma",
    "review",
    "taqdimot marosimi",
]

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None


def log(message):
    """Konsolga vaqt bilan birga log chiqaradi."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def strip_html(raw_text):
    """Matndan HTML teglarni olib tashlaydi."""
    if not raw_text:
        return ""
    clean_text = re.sub(r"<[^>]+>", "", raw_text)
    return html.unescape(clean_text).strip()


def is_coding_news(title, summary):
    """Faqat dasturlashga oid yangiliklarni qoldiradi."""
    text = f"{title} {summary}".lower()

    if any(keyword in text for keyword in EXCLUDE_KEYWORDS):
        return False

    return any(keyword in text for keyword in INCLUDE_KEYWORDS)


def load_sent_links():
    """Yuborilgan linklar ro'yxatini o'qiydi."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, str) and item.strip()]
        except Exception:
            pass

    if os.path.exists(LEGACY_DB_FILE):
        with open(LEGACY_DB_FILE, "r", encoding="utf-8") as f:
            legacy_link = f.read().strip()
        return [legacy_link] if legacy_link else []

    return []


def save_sent_links(links):
    """Yuborilgan linklar ro'yxatini saqlaydi."""
    trimmed_links = links[:MAX_SAVED_LINKS]
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed_links, f, ensure_ascii=False, indent=2)


def mark_link_as_sent(link):
    """Yangi yuborilgan linkni ro'yxat boshiga qo'shadi."""
    sent_links = load_sent_links()
    updated_links = [link] + [item for item in sent_links if item != link]
    save_sent_links(updated_links)


def extract_google_news_link(link):
    """Google News RSS ichidagi linkni normal ko'rinishga keltiradi."""
    if not link:
        return ""
    if link.startswith("./"):
        return f"https://news.google.com/{link[2:]}"
    return link


def build_google_news_url(query):
    """Google News RSS qidiruv URL manzilini yasaydi."""
    params = {
        "q": query,
        "hl": "uz",
        "gl": "UZ",
        "ceid": "UZ:uz",
    }
    prepared = requests.PreparedRequest()
    prepared.prepare_url(GOOGLE_NEWS_BASE_URL, params)
    return prepared.url


def get_latest_news_candidates(limit=40):
    """Google News orqali bir nechta manbadan o'zbekcha yangiliklarni yig'adi."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
    }
    results = []
    seen_links = set()

    for query in SEARCH_QUERIES:
        response = requests.get(build_google_news_url(query), headers=headers, timeout=20)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        for item in root.findall(".//item"):
            raw_title = item.findtext("title", default="").strip()
            link = extract_google_news_link(item.findtext("link", default="").strip())
            summary = item.findtext("description", default="").strip()
            source = item.findtext("source", default="").strip()
            pub_date = item.findtext("pubDate", default="").strip()

            if not raw_title or not link:
                continue

            title = raw_title.rsplit(" - ", 1)[0].strip()
            title = " ".join(title.split())
            summary = strip_html(summary) or title

            if len(title) < 15:
                continue
            if link in seen_links:
                continue

            seen_links.add(link)
            results.append(
                {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "source": source,
                    "published_at": pub_date,
                    "query": query,
                }
            )

            if len(results) >= limit:
                return results

        log(f"Google qidiruvi tugadi: '{query}' bo'yicha {len(results)} ta umumiy nomzod yig'ildi.")

    return results


async def rewrite_with_ai(title, summary):
    """Gemini orqali postni jozibali va xavfsiz matnga aylantiradi."""
    clean_title = strip_html(title)
    clean_summary = strip_html(summary)
    prompt = (
        "Quyidagi texnologik yangilikni o'zbek tilida, dasturchilar uchun "
        "qiziqarli va professional Telegram posti ko'rinishida qayta yozib ber. "
        "Faqat oddiy matn yoz. HTML teglar, Markdown belgilar va kod blok ishlatma. "
        "2-4 qisqa abzas yoz, oxirida qisqa xulosa qo'sh.\n\n"
        f"Sarlavha: {clean_title}\n"
        f"Ma'lumot: {clean_summary}"
    )
    try:
        if model is None:
            raise RuntimeError("GEMINI_KEY topilmadi")
        response = model.generate_content(prompt)
        generated_text = getattr(response, "text", "") or ""
        safe_text = strip_html(generated_text)
        if safe_text:
            return html.escape(safe_text)
    except Exception as e:
        log(f"Gemini xatosi: {e}")

    return f"<b>{html.escape(clean_title)}</b>\n\n{html.escape(clean_summary)}"


async def check_and_send_news():
    """Yuborilmagan birinchi yangilikni topib Telegram'ga yuboradi."""
    if not TELEGRAM_TOKEN or not GEMINI_KEY:
        log("XATO: TELEGRAM_TOKEN yoki GEMINI_KEY topilmadi.")
        return False

    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    try:
        log("Yangiliklar tekshirilmoqda...")
        candidates = get_latest_news_candidates(limit=50)
        if not candidates:
            log("Google News'dan mos yangilik topilmadi.")
            return False

        candidates = [
            item for item in candidates
            if is_coding_news(item["title"], item["summary"])
        ]
        log(f"Filtrdan keyin {len(candidates)} ta dasturlashga oid nomzod qoldi.")
        if not candidates:
            log("Dasturlashga oid mos yangilik topilmadi.")
            return False

        sent_links = set(load_sent_links())
        selected_news = next((item for item in candidates if item["link"] not in sent_links), None)

        if not selected_news:
            log("Hamma topilgan mos yangiliklar oldin yuborilgan.")
            return False

        source = selected_news.get("source") or "Google News"
        log(f"Yuboriladigan yangilik: {selected_news['title']} | Manba: {source}")
        final_text = await rewrite_with_ai(
            selected_news["title"],
            selected_news["summary"],
        )

        post_content = (
            "<b>Yangi Texno-Xabar</b>\n\n"
            f"{final_text}\n\n"
            f"<b>Manba:</b> {html.escape(source)}\n"
            f"<a href='{html.escape(selected_news['link'], quote=True)}'>Batafsil manbada</a>\n\n"
            "#AI #TechUz #Python"
        )

        await bot.send_message(chat_id=CHANNEL_ID, text=post_content)
        mark_link_as_sent(selected_news["link"])
        log("Post yuborildi!")
        return True
    except Exception as e:
        log(f"Xato: {e}")
        return False
    finally:
        await bot.session.close()


async def main():
    """Botni interval bo'yicha qayta-qayta ishlatadi."""
    cycle = 1
    while True:
        log(f"{cycle}-tekshiruv boshlandi.")
        try:
            sent = await check_and_send_news()
            if sent:
                log("Tekshiruv yakunlandi: yangi post yuborildi.")
            else:
                log("Tekshiruv yakunlandi: yuborishga mos yangi post topilmadi.")
        except Exception as e:
            log(f"Sikl xatosi: {e}")

        log(f"Keyingi tekshiruv {POLL_INTERVAL_SECONDS} soniyadan keyin.")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        cycle += 1


if __name__ == "__main__":
    asyncio.run(main())
