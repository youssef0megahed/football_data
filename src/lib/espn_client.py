import requests

from lib.config import ESPN_BASE_URL, REQUEST_TIMEOUT
from lib.log import retry_call


def espn_get(url, params=None):

    def request():

        response = requests.get(
            url, params=params, timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"ESPN transient HTTP {response.status_code}"
            )

        raise RuntimeError(
            f"ESPN HTTP {response.status_code}: {response.text[:300]}"
        )

    return retry_call(request, f"ESPN GET {url}")


def get_scoreboard(league_slug, date_str):
    """date_str بصيغة YYYYMMDD (شكل ESPN)."""

    url = f"{ESPN_BASE_URL}/{league_slug}/scoreboard"

    return espn_get(url, {"dates": date_str})


def get_summary(league_slug, event_id):

    url = f"{ESPN_BASE_URL}/{league_slug}/summary"

    return espn_get(url, {"event": str(event_id)})
