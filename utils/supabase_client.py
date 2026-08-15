"""
دوال Supabase: حالة البوت (bot_state) ومنع تكرار إرسال نفس حدث المباراة
"""
import requests


def _headers(supabase_key):
    return {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }


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


def is_event_sent(supabase_url, supabase_key, fixture_id, event_key):
    url = f"{supabase_url}/rest/v1/sent_live_events"
    resp = requests.get(
        url, headers=_headers(supabase_key),
        params={
            "select": "id",
            "fixture_id": f"eq.{fixture_id}",
            "event_key": f"eq.{event_key}",
        }, timeout=20,
    )
    if resp.status_code == 200:
        return len(resp.json()) > 0
    return False


def mark_event_sent(supabase_url, supabase_key, fixture_id, event_key):
    url = f"{supabase_url}/rest/v1/sent_live_events"
    resp = requests.post(
        url, headers={**_headers(supabase_key), "Prefer": "resolution=ignore-duplicates"},
        json={"fixture_id": fixture_id, "event_key": event_key}, timeout=20,
    )
    return resp.status_code in (200, 201)
