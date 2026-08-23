import os
import sys
import io
import requests
from PIL import Image, ImageDraw, ImageFont

from lib.config import validate_environment
from lib.log import log, retry_call
from lib.supabase_client import select
from lib.render_utils import (
    draw_arabic_text, get_logo,
    FONT_REGULAR_PATH, FONT_BOLD_PATH,
    COMPETITION_NAMES_AR, COMPETITION_BANNER_COLOR,
)


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

REQUEST_TIMEOUT = 30

COLOR_BG = (18, 20, 28)
COLOR_TEXT = (240, 240, 245)
COLOR_JERSEY_BG = (45, 50, 68)


def validate_telegram_env():

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
        )


# ============================================================
# POSITION GROUPING (نص المركز -> صف في الملعب)
# ============================================================

def position_group(position_text):

    text = (position_text or "").lower()

    if "goalkeeper" in text or "keeper" in text:
        return "GK"

    if "back" in text or "defender" in text or "defence" in text:
        return "DEF"

    if "wing" in text and (
        "forward" in text or "attack" in text
    ):
        return "FWD"

    if "midfield" in text:
        return "MID"

    if (
        "forward" in text
        or "striker" in text
        or "winger" in text
    ):
        return "FWD"

    return "MID"


ROW_ORDER = ["FWD", "MID", "DEF", "GK"]


# ============================================================
# DATA
# ============================================================

def get_lineup_data(match_id):

    match_rows = select(
        "matches",
        {
            "select": (
                "id,competition_id,home_team_id,away_team_id"
            ),
            "id": f"eq.{match_id}",
        },
    )

    if not match_rows:
        raise RuntimeError(f"Match not found: {match_id}")

    match = match_rows[0]

    competition_rows = select(
        "competitions",
        {"select": "id,name", "id": f"eq.{match['competition_id']}"},
    )

    competition_name = (
        competition_rows[0]["name"] if competition_rows else ""
    )

    lineup_rows = select(
        "match_lineups",
        {
            "select": (
                "team_id,home_away,formation,player_id,"
                "jersey_number,position,starter"
            ),
            "match_id": f"eq.{match_id}",
            "starter": "eq.true",
        },
    )

    player_ids = [r["player_id"] for r in lineup_rows]

    players = {}

    if player_ids:

        ids = ",".join(str(p) for p in player_ids)

        player_rows = select(
            "players",
            {"select": "id,name,name_ar,photo", "id": f"in.({ids})"},
        )

        players = {p["id"]: p for p in player_rows}

    team_ids = [match["home_team_id"], match["away_team_id"]]

    ids = ",".join(str(t) for t in team_ids if t)

    team_rows = select(
        "teams",
        {"select": "id,name,name_ar,logo", "id": f"in.({ids})"},
    )

    teams = {t["id"]: t for t in team_rows}

    return match, competition_name, lineup_rows, players, teams


# ============================================================
# PHOTO DOWNLOAD (best-effort, ESPN headshot pattern often 404s)
# ============================================================

_photo_cache = {}


def get_circular_photo(url, size):

    if not url:
        return None

    cache_key = (url, size)

    if cache_key in _photo_cache:
        return _photo_cache[cache_key]

    try:

        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            _photo_cache[cache_key] = None
            return None

        img = Image.open(io.BytesIO(response.content)).convert("RGBA")

        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((size, size), Image.LANCZOS)

        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)

        circular = Image.new("RGBA", (size, size))
        circular.paste(img, (0, 0), mask)

        _photo_cache[cache_key] = circular

        return circular

    except Exception as error:
        log(f"WARNING: photo fetch failed {url}: {error}")
        _photo_cache[cache_key] = None
        return None


def draw_fallback_circle(draw, cx, cy, size, jersey_number, font):

    r = size / 2

    draw.ellipse(
        [(cx - r, cy - r), (cx + r, cy + r)],
        fill=COLOR_JERSEY_BG, outline=(70, 76, 96), width=2,
    )

    if jersey_number:
        draw.text(
            (cx, cy), str(jersey_number), font=font,
            fill=COLOR_TEXT, anchor="mm",
        )


# ============================================================
# IMAGE
# ============================================================

def draw_lineup(match, competition_name, lineup_rows, players, teams):

    home = teams.get(match["home_team_id"], {})
    away = teams.get(match["away_team_id"], {})

    home_name = home.get("name_ar") or home.get("name") or "?"
    away_name = away.get("name_ar") or away.get("name") or "?"

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    def build_rows(team_id):

        rows = {r: [] for r in ROW_ORDER}

        for entry in lineup_rows:

            if entry["team_id"] != team_id:
                continue

            group = position_group(entry.get("position"))
            rows[group].append(entry)

        return [rows[r] for r in ROW_ORDER if rows[r]]

    home_rows = build_rows(match["home_team_id"])
    away_rows = build_rows(match["away_team_id"])

    photo_size = 84
    row_height = 150
    section_gap = 40
    banner_height = 130

    max_rows_per_team = max(len(home_rows), len(away_rows))

    width = 1000

    height = (
        banner_height
        + max_rows_per_team * row_height * 2
        + section_gap
    )

    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype(FONT_BOLD_PATH, 30)
    font_subtitle = ImageFont.truetype(FONT_REGULAR_PATH, 18)
    font_name = ImageFont.truetype(FONT_BOLD_PATH, 17)
    font_jersey = ImageFont.truetype(FONT_BOLD_PATH, 22)

    banner_color = COMPETITION_BANNER_COLOR.get(
        competition_name, (30, 41, 59)
    )

    draw.rectangle([(0, 0), (width, banner_height)], fill=banner_color)

    logo_size = 60

    home_logo = get_logo(home.get("logo"), logo_size)
    away_logo = get_logo(away.get("logo"), logo_size)

    if home_logo:
        img.paste(
            home_logo, (60, (banner_height - logo_size) // 2), home_logo
        )

    if away_logo:
        img.paste(
            away_logo,
            (width - 60 - logo_size, (banner_height - logo_size) // 2),
            away_logo,
        )

    draw_arabic_text(
        draw, (width / 2, banner_height * 0.4),
        f"{home_name}  🆚  {away_name}",
        font=font_title, fill=(255, 255, 255), anchor="mm",
    )

    draw_arabic_text(
        draw, (width / 2, banner_height * 0.75),
        f"التشكيلة الرسمية | {competition_ar}",
        font=font_subtitle, fill=(220, 220, 230), anchor="mm",
    )

    def draw_team_rows(rows, y_start, reverse=False):

        y = y_start

        ordered = list(reversed(rows)) if reverse else rows

        for row_players in ordered:

            count = len(row_players)
            spacing = width / (count + 1)

            for i, entry in enumerate(row_players, start=1):

                cx = spacing * i
                cy = y + row_height / 2

                player = players.get(entry["player_id"], {})

                photo_url = player.get("photo")
                photo_img = get_circular_photo(photo_url, photo_size)

                if photo_img:
                    img.paste(
                        photo_img,
                        (
                            int(cx - photo_size / 2),
                            int(cy - photo_size / 2 - 15),
                        ),
                        photo_img,
                    )
                else:
                    draw_fallback_circle(
                        draw, cx, cy - 15, photo_size,
                        entry.get("jersey_number"), font_jersey,
                    )

                name = (
                    player.get("name_ar")
                    or player.get("name")
                    or "?"
                )

                draw_arabic_text(
                    draw, (cx, cy + photo_size / 2 + 8), name,
                    font=font_name, fill=COLOR_TEXT, anchor="mm",
                )

            y += row_height

        return y

    y = banner_height

    y = draw_team_rows(home_rows, y, reverse=False)

    y += section_gap

    draw_team_rows(away_rows, y, reverse=True)

    return img


# ============================================================
# TELEGRAM
# ============================================================

def telegram_send_photo(image_path, caption=""):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    def request():

        with open(image_path, "rb") as photo_file:

            response = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": photo_file},
                timeout=REQUEST_TIMEOUT,
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

    return retry_call(request, "Telegram sendPhoto")


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()
    validate_telegram_env()

    if len(sys.argv) < 2:
        raise RuntimeError("Usage: publish_lineup_image.py <match_id>")

    match_id = int(sys.argv[1])

    log(f"Generating lineup image for match={match_id}")

    match, competition_name, lineup_rows, players, teams = (
        get_lineup_data(match_id)
    )

    if not lineup_rows:
        log("No starting lineup data for this match yet. Aborting.")
        return

    img = draw_lineup(
        match, competition_name, lineup_rows, players, teams
    )

    output_path = f"lineup_{match_id}.png"
    img.save(output_path)

    log(f"Image saved: {output_path}")

    telegram_send_photo(output_path, caption="📋 التشكيلة الرسمية")

    log("Sent lineup image.")


if __name__ == "__main__":
    main()
          
