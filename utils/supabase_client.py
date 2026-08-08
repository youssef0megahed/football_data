"""
دوال التعامل مع Supabase عبر REST API مباشرة
"""
import requests


def _headers(supabase_key):
    return {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }


def is_duplicate(supabase_url, supabase_key, source_url):
    url = f"{supabase_url}/rest/v1/articles"
    resp = requests.get(
        url, headers=_headers(supabase_key),
        params={"select": "id", "source_url": f"eq.{source_url}"}, timeout=20,
    )
    if resp.status_code == 200:
        return len(resp.json()) > 0
    print(f"  تحذير: فشل فحص التكرار - {resp.status_code} {resp.text[:200]}")
    return False


def insert_article(supabase_url, supabase_key, source_url, title, body, image_url="", telegram_message_id=None):
    url = f"{supabase_url}/rest/v1/articles"
    payload = {
        "source_url": source_url, "title": title, "body": body,
        "image_url": image_url, "published_to_fb": False,
    }
    if telegram_message_id is not None:
        payload["telegram_message_id"] = telegram_message_id

    resp = requests.post(
        url, headers={**_headers(supabase_key), "Prefer": "return=representation"},
        json=payload, timeout=20,
    )
    if resp.status_code in (200, 201):
        rows = resp.json()
        return rows[0] if rows else None
    print(f"  خطأ في حفظ الخبر: {resp.status_code} {resp.text[:300]}")
    return None


def update_article(supabase_url, supabase_key, article_id, fields: dict):
    url = f"{supabase_url}/rest/v1/articles"
    resp = requests.patch(
        url, headers=_headers(supabase_key),
        params={"id": f"eq.{article_id}"}, json=fields, timeout=20,
    )
    return resp.status_code in (200, 204)


def get_article_by_id(supabase_url, supabase_key, article_id):
    url = f"{supabase_url}/rest/v1/articles"
    resp = requests.get(
        url, headers=_headers(supabase_key),
        params={"select": "*", "id": f"eq.{article_id}"}, timeout=20,
    )
    rows = resp.json() if resp.status_code == 200 else []
    return rows[0] if rows else None


def get_article_by_telegram_message_id(supabase_url, supabase_key, message_id):
    url = f"{supabase_url}/rest/v1/articles"
    resp = requests.get(
        url, headers=_headers(supabase_key),
        params={"select": "*", "telegram_message_id": f"eq.{message_id}"}, timeout=20,
    )
    rows = resp.json() if resp.status_code == 200 else []
    return rows[0] if rows else None


def get_bot_state(supabase_url, supabase_key, key):
    url = f"{supabase_url}/rest/v1/bot_state"
    resp = requests.get(
        url, headers=_headers(supabase_key),
        params={"select": "value", "key": f"eq.{key}"}, timeout=20,
    )
    rows = resp.json() if resp.status_code == 200 else []
    return rows[0]["value"] if rows else None


def set_bot_state(supabase_url, supabase_key, key, value):
    url = f"{supabase_url}/rest/v1/bot_state"
    resp = requests.post(
        url, headers={**_headers(supabase_key), "Prefer": "resolution=merge-duplicates"},
        json={"key": key, "value": value}, timeout=20,
    )
    return resp.status_code in (200, 201)


# ---------- أرشيف التصحيحات (Few-Shot Learning) ----------

def add_correction(supabase_url, supabase_key, original_ai_text, corrected_text):
    """بيتسجل كل مرة تستخدم زرار التعديل"""
    url = f"{supabase_url}/rest/v1/correction_log"
    resp = requests.post(
        url, headers=_headers(supabase_key),
        json={"original_ai_text": original_ai_text, "corrected_text": corrected_text},
        timeout=20,
    )
    return resp.status_code in (200, 201)


def get_recent_corrections(supabase_url, supabase_key, limit=4):
    """بيجيب آخر أمثلة تصحيح عشان تتحط في الـ prompt كـ Few-Shot"""
    url = f"{supabase_url}/rest/v1/correction_log"
    resp = requests.get(
        url, headers=_headers(supabase_key),
        params={"select": "original_ai_text,corrected_text", "order": "created_at.desc", "limit": limit},
        timeout=20,
    )
    return resp.json() if resp.status_code == 200 else []
