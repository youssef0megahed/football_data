import os
import re
import json
import time
import requests
import feedparser

from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TIMEZONE = ZoneInfo("Africa/Cairo")

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4

# المصادر المفعّلة حاليًا فقط. تمت الموافقة على CaughtOffside
# لأن الـ RSS بتاعه بيوفر المقال كامل (content:encoded) من غير
# أي حاجة لعمل scraping لصفحة الموقع. BBC وFootball365 لسه
# مش مفعّلين (BBC عنده تنويه صريح بمنع إعادة استخدام الـ RSS).
RSS_SOURCES = {
    "caughtoffside": "https://www.caughtoffside.com/feed",
}

GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]

GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

MAX_ARTICLES_PER_RUN = 8

# فقرات متكررة/دعائية بتتكرر في كل مقال CaughtOffside، بنشيلها
# قبل الترجمة عشان ميتترجموش من غير فايدة.
BOILERPLATE_MARKERS = [
    "want more caughtoffside coverage",
    "the post ",
    "appeared first on",
]

HASHTAGS = "#كرة_القدم #أخبار"


# ============================================================
# LOGGING
# ============================================================

def log(message):
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now} Cairo] {message}", flush=True)


# ============================================================
# ENVIRONMENT
# ============================================================

def validate_environment():

    required = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "GEMINI_API_KEY": GEMINI_API_KEY,
    }

    missing = [key for key, value in required.items() if not value]

    if missing:
        raise RuntimeError(
            "Missing environment variables: " + ", ".join(missing)
        )


# ============================================================
# RETRY
# ============================================================

def retry_call(operation, label):

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            return operation()

        except Exception as error:

            last_error = error

            if attempt >= MAX_RETRIES:
                break

            delay = 2 ** (attempt - 1)

            log(f"{label} failed ({attempt}/{MAX_RETRIES}): {error}")
            log(f"Retrying in {delay}s...")

            time.sleep(delay)

    raise RuntimeError(
        f"{label} failed after {MAX_RETRIES} attempts: {last_error}"
    )


# ============================================================
# FETCH RSS FEED
# ============================================================

def get_feed_entries(feed_url):

    def request():

        response = requests.get(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; football_news/1.0)"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            return response.content

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"RSS transient HTTP {response.status_code}"
            )

        raise RuntimeError(
            f"RSS HTTP {response.status_code}: {response.text[:300]}"
        )

    raw = retry_call(request, f"RSS fetch {feed_url}")

    parsed = feedparser.parse(raw)

    return parsed.entries or []


# ============================================================
# CLEAN ARTICLE HTML -> PLAIN TEXT
# ============================================================

def extract_clean_text(html):

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # نشيل العناصر اللي مالهاش لازمة للترجمة
    for tag in soup.find_all(
        ["script", "style", "blockquote", "table", "section", "figure"]
    ):
        tag.decompose()

    for tag in soup.find_all(class_="more-stories"):
        tag.decompose()

    parts = []

    for element in soup.find_all(["p", "h2"]):

        text = element.get_text(" ", strip=True)

        if not text:
            continue

        lowered = text.lower()

        if any(marker in lowered for marker in BOILERPLATE_MARKERS):
            continue

        parts.append(text)

    combined = "\n".join(parts)

    # تقليم أي مسافات زيادة
    combined = re.sub(r"\n{2,}", "\n", combined).strip()

    return combined


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def supabase_request(
    method, table, params=None, json_body=None, extra_headers=None
):

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    headers = dict(SUPABASE_HEADERS)

    if extra_headers:
        headers.update(extra_headers)

    def request():

        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code in {200, 201, 204}:
            if not response.content:
                return []
            return response.json()

        if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"Supabase transient HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        raise RuntimeError(
            f"Supabase HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(request, f"Supabase {method} {table}")


# ============================================================
# TELEGRAM
# ============================================================

def telegram_request(method, payload):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"

    def request():

        response = requests.post(
            url, json=payload, timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            if not data.get("ok", False):
                raise RuntimeError(str(data))
            return data

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"Telegram transient HTTP {response.status_code}"
            )

        raise RuntimeError(
            f"Telegram HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(request, f"Telegram {method}")


# ============================================================
# GEMINI SUMMARIZE + TRANSLATE
# ============================================================

def call_gemini(model, payload):

    url = GEMINI_URL_TEMPLATE.format(model=model)

    def request():

        response = requests.post(
            url,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"Gemini ({model}) transient HTTP "
                f"{response.status_code}"
            )

        raise RuntimeError(
            f"Gemini ({model}) HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(request, f"Gemini ({model})")


def summarize_article(headline_en, full_text_en):

    # نطلب ملخص إخباري شامل بالعربي (مش ترجمة حرفية كاملة للنص)،
    # ده أنضف من ناحية الحقوق وأنسب لطول رسالة تليجرام.
    prompt = (
        "أنت محرر أخبار رياضية. لخّص الخبر التالي (منقول من موقع "
        "إنجليزي متخصص في أخبار كرة القدم) إلى ملخص عربي صحفي "
        "شامل من 4 إلى 7 جمل، يغطي كل التفاصيل والأرقام والأسماء "
        "المهمة المذكورة في النص، بأسلوب مباشر وواضح. حافظ على "
        "أسماء اللاعبين والأندية بصياغتها العربية الشائعة. "
        "أرجع فقط كائن JSON صحيح بدون أي نص أو markdown إضافي، "
        "بالشكل التالي:\n"
        '{"headline_ar": "...", "summary_ar": "..."}\n\n'
        f"العنوان: {headline_en}\n\n"
        f"النص الكامل:\n{full_text_en[:6000]}"
    )

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 800,
        },
    }

    last_error = None

    for model in GEMINI_MODELS:

        try:

            data = call_gemini(model, payload)

            text = (
                data["candidates"][0]["content"]["parts"][0]["text"]
            )

            text = text.strip()

            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]

            parsed = json.loads(text.strip())

            headline_ar = parsed.get("headline_ar", "").strip()
            summary_ar = parsed.get("summary_ar", "").strip()

            if not headline_ar:
                raise RuntimeError("Empty headline_ar from Gemini")

            return headline_ar, summary_ar

        except Exception as error:

            last_error = error

            log(
                f"Gemini model '{model}' failed: {error} "
                f"— trying next model."
            )

            continue

    raise RuntimeError(
        f"All Gemini models failed. Last error: {last_error}"
    )


# ============================================================
# ALREADY STORED?
# ============================================================

def get_existing_article_ids(source, source_article_ids):

    if not source_article_ids:
        return set()

    ids = ",".join(f'"{a}"' for a in source_article_ids)

    rows = supabase_request(
        "GET",
        "news_articles",
        params={
            "select": "source_article_id",
            "source": f"eq.{source}",
            "source_article_id": f"in.({ids})",
        },
    )

    return {row["source_article_id"] for row in rows}


# ============================================================
# MESSAGE
# ============================================================

def build_news_message(headline_ar, summary_ar):

    lines = ["📰 " + headline_ar, ""]

    if summary_ar:
        lines.append(summary_ar)
        lines.append("")

    lines.append(HASHTAGS)

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    log("==================================================")
    log("RSS NEWS PUBLISHER START")
    log("==================================================")

    processed = 0

    for source_name, feed_url in RSS_SOURCES.items():

        if processed >= MAX_ARTICLES_PER_RUN:
            log("Reached per-run article limit, stopping.")
            break

        try:
            entries = get_feed_entries(feed_url)
        except Exception as error:
            log(f"ERROR fetching feed {source_name}: {error}")
            continue

        source_ids = [
            entry.get("id") or entry.get("link")
            for entry in entries
            if entry.get("id") or entry.get("link")
        ]

        existing_ids = get_existing_article_ids(source_name, source_ids)

        for entry in entries:

            if processed >= MAX_ARTICLES_PER_RUN:
                break

            source_article_id = entry.get("id") or entry.get("link")

            if not source_article_id:
                continue

            if source_article_id in existing_ids:
                continue

            headline_en = entry.get("title") or ""

            if not headline_en:
                continue

            content_html = ""

            if entry.get("content"):
                content_html = entry["content"][0].get("value", "")
            elif entry.get("summary"):
                content_html = entry.get("summary", "")

            full_text_en = extract_clean_text(content_html)

            if len(full_text_en) < 80:
                log(
                    f"SKIP (too short) article "
                    f"{source_article_id}"
                )
                continue

            link = entry.get("link") or ""

            image_url = ""

            if entry.get("media_thumbnail"):
                image_url = entry["media_thumbnail"][0].get("url", "")
            elif entry.get("media_content"):
                image_url = entry["media_content"][0].get("url", "")

            published_at = None

            if entry.get("published_parsed"):
                published_at = datetime(
                    *entry["published_parsed"][:6],
                    tzinfo=ZoneInfo("UTC"),
                ).isoformat()

            try:

                headline_ar, summary_ar = summarize_article(
                    headline_en, full_text_en
                )

            except Exception as error:
                log(
                    f"ERROR summarizing article "
                    f"{source_article_id}: {error}"
                )
                continue

            record = {
                "source": source_name,
                "source_article_id": source_article_id,
                "competition_name": None,
                "headline_en": headline_en,
                "description_en": full_text_en[:3000],
                "headline_ar": headline_ar,
                "description_ar": summary_ar,
                "link": link,
                "image_url": image_url,
                "published_at": published_at,
            }

            try:

                supabase_request(
                    "POST",
                    "news_articles",
                    params={
                        "on_conflict": "source,source_article_id"
                    },
                    json_body=[record],
                    extra_headers={
                        "Prefer": (
                            "resolution=merge-duplicates,"
                            "return=minimal"
                        )
                    },
                )

            except Exception as error:
                log(
                    f"ERROR saving article "
                    f"{source_article_id}: {error}"
                )
                continue

            try:

                message = build_news_message(headline_ar, summary_ar)

                if image_url:
                    telegram_request(
                        "sendPhoto",
                        {
                            "chat_id": TELEGRAM_CHAT_ID,
                            "photo": image_url,
                            "caption": message,
                        },
                    )
                else:
                    telegram_request(
                        "sendMessage",
                        {
                            "chat_id": TELEGRAM_CHAT_ID,
                            "text": message,
                        },
                    )

                supabase_request(
                    "PATCH",
                    "news_articles",
                    params={
                        "source": f"eq.{source_name}",
                        "source_article_id": f"eq.{source_article_id}",
                    },
                    json_body={
                        "sent_at": datetime.now(TIMEZONE).isoformat()
                    },
                    extra_headers={"Prefer": "return=minimal"},
                )

                log(f"Sent article {source_article_id}")

                processed += 1

            except Exception as error:
                log(
                    f"ERROR sending article "
                    f"{source_article_id}: {error}"
                )
                continue

    log("==================================================")
    log(f"Processed: {processed}")
    log("RSS NEWS PUBLISHER END")
    log("==================================================")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
