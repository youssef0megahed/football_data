import requests

from lib.config import SUPABASE_URL, SUPABASE_KEY, REQUEST_TIMEOUT
from lib.log import retry_call


def _headers(extra_headers=None):

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    if extra_headers:
        headers.update(extra_headers)

    return headers


def supabase_request(
    method, table, params=None, json_body=None, extra_headers=None
):

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    headers = _headers(extra_headers)

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
            f"{response.text[:800]}"
        )

    return retry_call(request, f"Supabase {method} {table}")


def upsert(table, records, on_conflict, return_rows=False):
    """Upsert واحد أو أكتر من الصفوف. بيرجع الصفوف لو return_rows=True
    (مفيد لما محتاجين نعرف id الصف بعد الإدخال)."""

    if not records:
        return [] if return_rows else 0

    prefer = "resolution=merge-duplicates"
    prefer += ",return=representation" if return_rows else ",return=minimal"

    result = supabase_request(
        "POST",
        table,
        params={"on_conflict": on_conflict},
        json_body=records,
        extra_headers={"Prefer": prefer},
    )

    return result if return_rows else len(records)


def select(table, params):
    return supabase_request("GET", table, params=params)
