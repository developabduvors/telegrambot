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
from aiogram.types import URLInputFile
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

# Faqat aniq texnologiya va dasturlash so'rovlari
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

# Faqat aniq dasturlash va AI kalit so'zlar
INCLUDE_KEYWORDS = [
    "python",
    "javascript",
    "typescript",
    "java ",
    "golang",
    "rust ",
    "php",
    "c++",
    "c#",
    "swift",
    "kotlin",
    "react",
    "next.js",
    "nextjs",
    "vue",
    "angular",
    "node.js",
    "nodejs",
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
    "programming",
    "developer",
    "software engineer",
    "code",
    "coding",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "llm",
    "large language model",
    "gemini",
    "chatgpt",
    "gpt-",
    "claude",
    "codex",
    "copilot",
    "openai",
    "anthropic",
    "hugging face",
    "neural network",
    "database",
    "postgresql",
    "mongodb",
    "redis",
    "sql",
    "docker",
    "kubernetes",
    "devops",
    "ci/cd",
    "cybersecurity",
    "cloud computing",
    "aws",
    "azure",
    "vercel",
    "startup tech",
    "ide",
    "vs code",
    "linux kernel",
    "web3",
    "blockchain developer",
]

# Keng exclude ro'yxati — dasturlashga aloqasi yo'q mavzular
EXCLUDE_KEYWORDS = [
    # Shaxslar va siyosat
    "boshqaruv raisi",
    "tayinlandi",
    "prezident",
    "vazir",
    "hokimi",
    "parlament",
    "saylov",
    "siyosat",
    "diplomatiya",
    "elchi",
    "tashkent metro",
    "aviakompaniya",
    "airways",
    "airline",
    # Tovarlar va narx
    "telefon",
    "smartfon",
    "iphone",
    "android telefon",
    "noutbuk",
    "notebook",
    "laptop narx",
    "planshet",
    "televizor",
    "kamera",
    "quloqchin",
    "airpods",
    "gadget review",
    "narx",
    "aksiya",
    "chegirma",
    "sotib olish",
    # Sport va ko'ngilochar
    "futbol",
    "basketbol",
    "tennis",
    "sport",
    "chempionat",
    "o'yin natija",
    "kino",
    "film",
    "serial",
    "muzika",
    "konsert",
    # Boshqa
    "ob-havo",
    "zilzila",
    "voqea",
    "tashrif",
    "uchrashuv",
    "imzolandi",
    "shartnoma",
]

# Mavzuga mos hashtaglar lug'ati
TOPIC_HASHTAGS = {
    "python": "#Python",
    "javascript": "#JavaScript",
    "typescript": "#TypeScript",
    "java": "#Java",
    "golang": "#Golang",
    "rust": "#Rust",
    "php": "#PHP",
    "c++": "#CPlusPlus",
    "c#": "#CSharp",
    "ai": "#AI",
    "llm": "#LLM",
    "gemini": "#Gemini",
    "chatgpt": "#ChatGPT",
    "gpt": "#GPT",
    "claude": "#Claude",
    "docker": "#Docker",
    "kubernetes": "#Kubernetes",
    "devops": "#DevOps",
    "github": "#GitHub",
    "open source": "#OpenSource",
    "cybersecurity": "#CyberSecurity",
    "xavfsizlik": "#Xavfsizlik",
    "startup": "#Startup",
    "database": "#Database",
    "cloud": "#Cloud",
    "frontend": "#Frontend",
    "backend": "#Backend",
    "fullstack": "#Fullstack",
}

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
    """Faqat dasturlash va AI ga oid yangiliklarni qoldiradi."""
    title_lower = title.lower()
    text = f"{title} {summary}".lower()

    # Exclude ro'yxatida bo'lsa — sarlavhada ham, matnda ham tekshiramiz
    if any(keyword in title_lower for keyword in EXCLUDE_KEYWORDS):
        return False
    if any(keyword in text for keyword in EXCLUDE_KEYWORDS):
        return False

    # Sarlavhada kamida 1 ta include kalit so'z bo'lishi shart
    title_match = any(keyword in title_lower for keyword in INCLUDE_KEYWORDS)
    if not title_match:
        return False

    # Umumiy matnda kamida 2 ta include kalit so'z bo'lishi shart
    match_count = sum(1 for keyword in INCLUDE_KEYWORDS if keyword in text)
    return match_count >= 2


def get_topic_hashtags(title, summary):
    """Yangilik matniga mos hashtaglarni topadi (max 4 ta)."""
    text = f"{title} {summary}".lower()
    found = []
    for keyword, hashtag in TOPIC_HASHTAGS.items():
        if keyword in text and hashtag not in found:
            found.append(hashtag)
        if len(found) >= 4:
            break
    # Har doim asosiy hashtaglar bo'lsin
    base_tags = ["#TechUz", "#Dasturlash"]
    all_tags = found + [t for t in base_tags if t not in found]
    return " ".join(all_tags[:5])


def fetch_og_image(url):
    """Yangilik sahifasidan og:image meta-tegini oladi."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # og:image ni regex bilan qidiramiz (BeautifulSoup o'rnatilmagan bo'lishi mumkin)
        og_image_match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            response.text,
            re.IGNORECASE,
        )
        if not og_image_match:
            # Teskari tartibda ham qidiramiz
            og_image_match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                response.text,
                re.IGNORECASE,
            )

        if og_image_match:
            image_url = og_image_match.group(1).strip()
            if image_url.startswith("http"):
                return image_url
    except Exception as e:
        log(f"Rasm olishda xato: {e}")
    return None


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
        "hl": "en",
        "gl": "US",
        "ceid": "US:en",
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
        "Yangilik inglizcha bo'lsa, o'zbekchaga tarjima qil. "
        "Faqat oddiy matn yoz. HTML teglar, Markdown belgilar va kod blok ishlatma. "
        "2-4 qisqa abzas yoz, oxirida qisqa xulosa qo'sh. "
        "Faqat Python, JavaScript, React, Next.js, AI, LLM, Claude, GPT, Gemini, "
        "Docker, GitHub va shunga o'xshash texnologiyalar haqida yoz.\n\n"
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

        # Sana va vaqt
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        # Mavzuga mos hashtaglar
        hashtags = get_topic_hashtags(selected_news["title"], selected_news["summary"])

        post_content = (
            "🖥 <b>Yangi Texno-Xabar</b>\n"
            f"🗓 {now_str}\n\n"
            f"{final_text}\n\n"
            f"📰 <b>Manba:</b> {html.escape(source)}\n"
            f"🔗 <a href='{html.escape(selected_news['link'], quote=True)}'>Batafsil o'qish</a>\n\n"
            f"{hashtags}"
        )

        # Yangilik sahifasidan rasm olishga urinamiz
        log("Rasm qidirilmoqda...")
        image_url = fetch_og_image(selected_news["link"])

        if image_url:
            log(f"Rasm topildi: {image_url}")
            try:
                photo = URLInputFile(image_url)
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=photo,
                    caption=post_content,
                )
                log("Rasm bilan post yuborildi!")
            except Exception as img_err:
                log(f"Rasm yuborishda xato, oddiy matn yuboriladi: {img_err}")
                await bot.send_message(chat_id=CHANNEL_ID, text=post_content)
                log("Oddiy matn post yuborildi!")
        else:
            log("Rasm topilmadi, oddiy matn yuboriladi.")
            await bot.send_message(chat_id=CHANNEL_ID, text=post_content)
            log("Post yuborildi!")

        mark_link_as_sent(selected_news["link"])
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
