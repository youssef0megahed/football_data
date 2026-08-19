import os
import json
import time
import requests

from datetime import datetime
from zoneinfo import ZoneInfo


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

ESPN_BASE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer"
)

GEMINI_MODEL = "gemini-flash-latest"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# أقصى عدد أخبار جديدة نترجمها وننشرها في التشغيلة الواحدة
# (حماية من تكلفة/تكرار غير متوقع لو ظهرت دفعة كبيرة فجأة)
MAX_ARTICLES_PER_RUN = 10

COMPETITION_SLUGS = {
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
}

COMPETITION_NAMES_AR = {
    "Premier League": "الدوري الإنجليزي الممتاز",
    "La Liga": "الدوري الإسباني",
    "Serie A": "الدوري الإيطالي",
    "Bundesliga": "الدوري الألماني",
    "Ligue 1": "الدوري الفرنسي",
}


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
# ESPN NEWS FEED
# ============================================================

def get_league_news(league_slug):

    url = f"{ESPN_BASE_URL}/{league_slug}/news"

    def request():

        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            return response.json()

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"ESPN transient HTTP {response.status_code}"
            )

        raise RuntimeError(
            f"ESPN HTTP {response.status_code}: {response.text[:300]}"
        )

    data = retry_call(request, f"ESPN news {league_slug}")

    return data.get("articles") or []


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
# GEMINI TRANSLATION
# ============================================================

def translate_article(headline_en, description_en):

    prompt = (
        "ترجم العنوان والوصف التاليين لخبر رياضي عن كرة القدم "
        "إلى العربية المستخدمة في الإعلام الرياضي العربي "
        "(واضحة ومختصرة). حافظ على أسماء اللاعبين والفرق "
        "بصياغتها العربية الشائعة. أرجع فقط كائن JSON صحيح "
        "بدون أي نص أو markdown إضافي، بالشكل التالي:\n"
        '{"headline_ar": "...", "description_ar": "..."}\n\n'
        f"العنوان: {headline_en}\n"
        f"الوصف: {description_en}"
    )

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 500,
        },
    }

    def request():

        response = requests.post(
            GEMINI_URL,
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
                f"Gemini transient HTTP {response.status_code}"
            )

        raise RuntimeError(
            f"Gemini HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = retry_call(request, "Gemini translate")

    text = (
        data["candidates"][0]["content"]["parts"][0]["text"]
    )

    # الموديل ممكن يرجع الـ JSON ملفوف في ```json أحيانًا رغم التعليمات
    text = text.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]

    parsed = json.loads(text.strip())

    return (
        parsed.get("headline_ar", "").strip(),
        parsed.get("description_ar", "").strip(),
    )


# ============================================================
# ALREADY STORED?
# ============================================================

def get_existing_article_ids(source_article_ids):

    if not source_article_ids:
        return set()

    ids = ",".join(f'"{a}"' for a in source_article_ids)

    rows = supabase_request(
        "GET",
        "news_articles",
        params={
            "select": "source_article_id",
            "source": "eq.espn",
            "source_article_id": f"in.({ids})",
        },
    )

    return {row["source_article_id"] for row in rows}


# ============================================================
# MESSAGE
# ============================================================

def build_news_message(article, competition_name):

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    lines = ["📰 " + article["headline_ar"], ""]

    if article.get("description_ar"):
        lines.append(article["description_ar"])
        lines.append("")

    if competition_ar:
        lines.append(f"🏆 {competition_ar}")
        lines.append("")

    hashtag = (
        "#" + competition_ar.replace(" ", "_")
        if competition_ar
        else ""
    )

    tags = " ".join(t for t in [hashtag, "#أخبار"] if t)

    lines.append(tags)

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    log("==================================================")
    log("NEWS PUBLISHER START")
    log("==================================================")

    processed = 0

    for competition_name, league_slug in COMPETITION_SLUGS.items():

        if processed >= MAX_ARTICLES_PER_RUN:
            log("Reached per-run article limit, stopping.")
            break

        try:
            articles = get_league_news(league_slug)
        except Exception as error:
            log(f"ERROR fetching news for {competition_name}: {error}")
            continue

        source_ids = [
            str(a.get("id"))
            for a in articles
            if a.get("id") is not None
        ]

        existing_ids = get_existing_article_ids(source_ids)

        for article in articles:

            if processed >= MAX_ARTICLES_PER_RUN:
                break

            source_article_id = str(article.get("id") or "")

            if not source_article_id:
                continue

            if source_article_id in existing_ids:
                continue

            headline_en = article.get("headline") or ""
            description_en = article.get("description") or ""

            if not headline_en:
                continue

            link = ""
            links = article.get("links") or {}
            web_link = links.get("web") or {}
            link = web_link.get("href") or ""

            image_url = ""
            images = article.get("images") or []
            if images:
                image_url = images[0].get("url") or ""

            published_at = article.get("published") or None

            try:

                headline_ar, description_ar = translate_article(
                    headline_en, description_en
                )

            except Exception as error:
                log(
                    f"ERROR translating article "
                    f"{source_article_id}: {error}"
                )
                continue

            if not headline_ar:
                log(
                    f"WARNING: empty translation for "
                    f"article {source_article_id}, skipping."
                )
                continue

            record = {
                "source": "espn",
                "source_article_id": source_article_id,
                "competition_name": competition_name,
                "headline_en": headline_en,
                "description_en": description_en,
                "headline_ar": headline_ar,
                "description_ar": description_ar,
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

                message = build_news_message(
                    {
                        "headline_ar": headline_ar,
                        "description_ar": description_ar,
                    },
                    competition_name,
                )

                telegram_payload = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                }

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
                        "sendMessage", telegram_payload
                    )

                supabase_request(
                    "PATCH",
                    "news_articles",
                    params={
                        "source": "eq.espn",
                        "source_article_id": f"eq.{source_article_id}",
                    },
                    json_body={
                        "sent_at": datetime.now(TIMEZONE).isoformat()
                    },
                    extra_headers={"Prefer": "return=minimal"},
                )

                log(f"Sent news article {source_article_id}")

                processed += 1

            except Exception as error:
                log(
                    f"ERROR sending article "
                    f"{source_article_id}: {error}"
                )
                continue

    log("==================================================")
    log(f"Processed: {processed}")
    log("NEWS PUBLISHER END")
    log("==================================================")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
