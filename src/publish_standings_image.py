import os
import io
import sys
import requests
import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

from lib.config import validate_environment
from lib.log import log, retry_call
from lib.supabase_client import select


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

REQUEST_TIMEOUT = 30

FONT_REGULAR_PATH = "assets/Cairo-Regular.ttf"
FONT_BOLD_PATH = "assets/Cairo-SemiBold.ttf"

COMPETITION_NAMES_AR = {
    "Premier League": "الدوري الإنجليزي الممتاز",
    "La Liga": "الدوري الإسباني",
    "Serie A": "الدوري الإيطالي",
    "Bundesliga": "الدوري الألماني",
    "Ligue 1": "الدوري الفرنسي",
}

COMPETITION_BANNER_COLOR = {
    "Premier League": (55, 0, 60),
    "La Liga": (238, 49, 36),
    "Serie A": (0, 60, 130),
    "Bundesliga": (214, 0, 24),
    "Ligue 1": (16, 40, 90),
}

ZONE_COLORS = {
    "cl": (52, 120, 220),
    "el": (255, 140, 0),
    "conf": (46, 160, 90),
    "relegation": (210, 40, 40),
}

ZONE_RULES = {
    "Premier League": {1: "cl", 2: "cl", 3: "cl", 4: "cl", 5: "el", 6: "conf"},
    "La Liga": {1: "cl", 2: "cl", 3: "cl", 4: "cl", 5: "el", 6: "conf"},
    "Serie A": {1: "cl", 2: "cl", 3: "cl", 4: "cl", 5: "el", 6: "conf"},
    "Bundesliga": {1: "cl", 2: "cl", 3: "cl", 4: "cl", 5: "el", 6: "conf"},
    "Ligue 1": {1: "cl", 2: "cl", 3: "cl", 4: "el", 5: "conf"},
}

RELEGATION_COUNT = 3

COLOR_BG = (255, 255, 255)
COLOR_HEADER_ROW_BG = (243, 244, 248)
COLOR_ROW_EVEN = (255, 255, 255)
COLOR_ROW_ODD = (250, 250, 252)
COLOR_BORDER = (228, 229, 235)
COLOR_TEXT = (20, 22, 30)
COLOR_HEADER_TEXT = (255, 255, 255)


def validate_telegram_env():

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
        )


# ============================================================
# ARABIC TEXT SHAPING
# ============================================================

def shape_arabic(text):

    reshaped = arabic_reshaper.reshape(str(text))

    return get_display(reshaped)


# ============================================================
# DATA
# ============================================================

def get_standings_data(competition_name):

    competitions = select(
        "competitions",
        {"select": "id,name", "name": f"eq.{competition_name}"},
    )

    if not competitions:
        raise RuntimeError(f"Competition not found: {competition_name}")

    competition_id = competitions[0]["id"]

    seasons = select(
        "seasons",
        {
            "select": "id",
            "competition_id": f"eq.{competition_id}",
            "order": "id.desc",
            "limit": "1",
        },
    )

    if not seasons:
        raise RuntimeError(
            f"No season found for competition_id={competition_id}"
        )

    season_id = seasons[0]["id"]

    rows = select(
        "standings",
        {
            "select": (
                "rank,team_id,played,wins,draws,losses,"
                "goals_for,goals_against,goal_difference,points"
            ),
            "season_id": f"eq.{season_id}",
            "order": "rank.asc",
        },
    )

    team_ids = [r["team_id"] for r in rows]

    teams = {}

    if team_ids:

        ids = ",".join(str(t) for t in team_ids)

        team_rows = select(
            "teams",
            {
                "select": "id,name,name_ar,logo",
                "id": f"in.({ids})",
            },
        )

        teams = {t["id"]: t for t in team_rows}

    return rows, teams


# ============================================================
# LOGO DOWNLOAD (best-effort, falls back to a plain circle)
# ============================================================

_logo_cache = {}


def get_team_logo(url, size):

    if not url:
        return None

    cache_key = (url, size)

    if cache_key in _logo_cache:
        return _logo_cache[cache_key]

    try:

        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        logo = Image.open(io.BytesIO(response.content)).convert("RGBA")
        logo = logo.resize((size, size), Image.LANCZOS)

        _logo_cache[cache_key] = logo

        return logo

    except Exception as error:
        log(f"WARNING: failed to fetch logo {url}: {error}")
        return None


def draw_placeholder_logo(draw, cx, cy, size):

    r = size / 2

    draw.ellipse(
        [(cx - r, cy - r), (cx + r, cy + r)],
        fill=(225, 227, 233),
        outline=COLOR_BORDER,
    )


# ============================================================
# ZONE COLOR
# ============================================================

def get_zone_color(competition_name, rank, total_teams):

    rules = ZONE_RULES.get(competition_name, {})

    zone = rules.get(rank)

    if zone:
        return ZONE_COLORS[zone]

    if rank > total_teams - RELEGATION_COUNT:
        return ZONE_COLORS["relegation"]

    return None


# ============================================================
# IMAGE RENDERING
# ============================================================

def draw_table(competition_name, rows, teams):

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    banner_height = 110
    header_row_height = 50
    row_height = 78
    logo_size = 46
    zone_bar_width = 10

    col_widths = {
        "points": 90, "diff": 90, "goals": 100, "l": 60, "d": 60,
        "w": 60, "played": 70, "team": 320, "rank": 70,
    }

    width = sum(col_widths.values()) + zone_bar_width
    height = banner_height + header_row_height + row_height * len(rows)

    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype(FONT_BOLD_PATH, 36)
    font_subtitle = ImageFont.truetype(FONT_REGULAR_PATH, 20)
    font_header = ImageFont.truetype(FONT_BOLD_PATH, 18)
    font_cell = ImageFont.truetype(FONT_BOLD_PATH, 20)
    font_team = ImageFont.truetype(FONT_BOLD_PATH, 21)

    banner_color = COMPETITION_BANNER_COLOR.get(
        competition_name, (30, 41, 59)
    )

    draw.rectangle([(0, 0), (width, banner_height)], fill=banner_color)

    draw.text(
        (width / 2, banner_height * 0.42),
        shape_arabic(competition_ar),
        font=font_title, fill=COLOR_HEADER_TEXT, anchor="mm",
    )

    draw.text(
        (width / 2, banner_height * 0.75),
        shape_arabic("جدول الترتيب"),
        font=font_subtitle, fill=(230, 230, 235), anchor="mm",
    )

    y = banner_height

    draw.rectangle(
        [(0, y), (width, y + header_row_height)],
        fill=COLOR_HEADER_ROW_BG,
    )

    x = width - zone_bar_width

    header_order = [
        ("rank", "ت"), ("team", "الفريق"), ("played", "لعب"),
        ("w", "ف"), ("d", "ت"), ("l", "خ"), ("goals", "أهداف"),
        ("diff", "الفرق"), ("points", "نقاط"),
    ]

    for key, label in header_order:

        col_w = col_widths[key]
        x -= col_w

        draw.text(
            (x + col_w / 2, y + header_row_height / 2),
            shape_arabic(label),
            font=font_header, fill=COLOR_TEXT, anchor="mm",
        )

    y = banner_height + header_row_height

    total_teams = len(rows)

    for row_index, row in enumerate(rows):

        team = teams.get(row["team_id"], {})
        team_name = team.get("name_ar") or team.get("name") or "?"

        bg = COLOR_ROW_EVEN if row_index % 2 == 0 else COLOR_ROW_ODD

        draw.rectangle([(0, y), (width, y + row_height)], fill=bg)

        draw.line(
            [(0, y + row_height), (width, y + row_height)],
            fill=COLOR_BORDER, width=1,
        )

        zone_color = get_zone_color(
            competition_name, row["rank"], total_teams
        )

        if zone_color:
            draw.rectangle(
                [(width - zone_bar_width, y),
                 (width, y + row_height)],
                fill=zone_color,
            )

        x = width - zone_bar_width

        col_w = col_widths["rank"]
        x -= col_w
        draw.text(
            (x + col_w / 2, y + row_height / 2), str(row["rank"]),
            font=font_cell, fill=COLOR_TEXT, anchor="mm",
        )

        col_w = col_widths["team"]
        x -= col_w

        logo_url = team.get("logo")
        logo_img = get_team_logo(logo_url, logo_size)

        logo_x = x + col_w - logo_size - 14
        logo_y = int(y + (row_height - logo_size) / 2)

        if logo_img:
            img.paste(logo_img, (logo_x, logo_y), logo_img)
        else:
            draw_placeholder_logo(
                draw, logo_x + logo_size / 2,
                y + row_height / 2, logo_size,
            )

        draw.text(
            (logo_x - 14, y + row_height / 2),
            shape_arabic(team_name),
            font=font_team, fill=COLOR_TEXT, anchor="rm",
        )

        numeric_values = [
            ("played", str(row["played"])),
            ("w", str(row["wins"])),
            ("d", str(row["draws"])),
            ("l", str(row["losses"])),
            ("goals", f"{row['goals_against']}:{row['goals_for']}"),
            (
                "diff",
                (
                    f"+{row['goal_difference']}"
                    if row["goal_difference"] > 0
                    else str(row["goal_difference"])
                ),
            ),
            ("points", str(row["points"])),
        ]

        for key, value in numeric_values:

            col_w = col_widths[key]
            x -= col_w

            draw.text(
                (x + col_w / 2, y + row_height / 2), value,
                font=font_cell, fill=COLOR_TEXT, anchor="mm",
            )

        y += row_height

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
# ONE COMPETITION
# ============================================================

def publish_one(competition_name):

    log(f"Generating standings image for: {competition_name}")

    rows, teams = get_standings_data(competition_name)

    if not rows:
        log("No standings data yet for this competition. Skipping.")
        return

    img = draw_table(competition_name, rows, teams)

    safe_name = competition_name.replace(" ", "_")
    output_path = f"standings_{safe_name}.png"
    img.save(output_path)

    log(f"Image saved: {output_path}")

    telegram_send_photo(output_path)

    log(f"Sent standings image for {competition_name}")


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()
    validate_telegram_env()

    if len(sys.argv) > 1 and sys.argv[1] != "all":

        publish_one(sys.argv[1])

    else:

        for competition_name in COMPETITION_NAMES_AR:

            try:
                publish_one(competition_name)
            except Exception as error:
                log(f"ERROR {competition_name}: {error}")
                continue


if __name__ == "__main__":
    main()
