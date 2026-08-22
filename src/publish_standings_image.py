import os
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

# ألوان الهوية البصرية
COLOR_BG = (18, 24, 38)
COLOR_HEADER_BG = (30, 41, 59)
COLOR_ROW_A = (24, 32, 48)
COLOR_ROW_B = (30, 40, 58)
COLOR_TEXT = (240, 240, 245)
COLOR_TEXT_DIM = (170, 178, 195)
COLOR_ACCENT = (56, 189, 148)
COLOR_HEADER_TEXT = (255, 255, 255)

COLUMN_HEADERS_AR = [
    "#", "الفريق", "لعب", "فوز", "تعادل", "خسارة", "له", "عليه", "فارق", "نقاط",
]


def validate_telegram_env():

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
        )


# ============================================================
# ARABIC TEXT SHAPING
# ============================================================

def shape_arabic(text):
    """يحوّل نص عربي لشكل صحيح للرسم (الحروف متصلة، اتجاه صح)."""

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
            {"select": "id,name,name_ar", "id": f"in.({ids})"},
        )

        teams = {t["id"]: t for t in team_rows}

    return rows, teams


# ============================================================
# IMAGE RENDERING
# ============================================================

def draw_table(competition_name, rows, teams):

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    row_height = 56
    header_height = 130
    col_widths = [50, 300, 60, 60, 70, 70, 60, 60, 70, 70]
    width = sum(col_widths) + 60
    height = header_height + row_height * len(rows) + 40

    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype(FONT_BOLD_PATH, 34)
    font_subtitle = ImageFont.truetype(FONT_REGULAR_PATH, 20)
    font_header = ImageFont.truetype(FONT_BOLD_PATH, 18)
    font_cell = ImageFont.truetype(FONT_REGULAR_PATH, 18)
    font_cell_bold = ImageFont.truetype(FONT_BOLD_PATH, 18)

    # --- العنوان ---
    title_text = shape_arabic(f"🏆 {competition_ar}")
    draw.text(
        (width / 2, 30), title_text, font=font_title,
        fill=COLOR_HEADER_TEXT, anchor="mm",
    )

    subtitle_text = shape_arabic("جدول الترتيب")
    draw.text(
        (width / 2, 70), subtitle_text, font=font_subtitle,
        fill=COLOR_ACCENT, anchor="mm",
    )

    # --- رأس الجدول ---
    y = header_height - 40

    draw.rectangle(
        [(30, y), (width - 30, y + 40)], fill=COLOR_HEADER_BG
    )

    x = width - 30

    for i, header in enumerate(COLUMN_HEADERS_AR):

        col_w = col_widths[i]
        x -= col_w

        text = shape_arabic(header)

        draw.text(
            (x + col_w / 2, y + 20), text, font=font_header,
            fill=COLOR_HEADER_TEXT, anchor="mm",
        )

    # --- الصفوف ---
    y = header_height

    for row_index, row in enumerate(rows):

        team = teams.get(row["team_id"], {})
        team_name = team.get("name_ar") or team.get("name") or "?"

        bg = COLOR_ROW_A if row_index % 2 == 0 else COLOR_ROW_B

        draw.rectangle(
            [(30, y), (width - 30, y + row_height)], fill=bg
        )

        values = [
            str(row["rank"]),
            team_name,
            str(row["played"]),
            str(row["wins"]),
            str(row["draws"]),
            str(row["losses"]),
            str(row["goals_for"]),
            str(row["goals_against"]),
            (
                f"+{row['goal_difference']}"
                if row["goal_difference"] > 0
                else str(row["goal_difference"])
            ),
            str(row["points"]),
        ]

        x = width - 30

        for i, value in enumerate(values):

            col_w = col_widths[i]
            x -= col_w

            is_team_col = (i == 1)
            is_points_col = (i == len(values) - 1)

            font = font_cell_bold if is_points_col else font_cell
            color = COLOR_ACCENT if is_points_col else COLOR_TEXT

            if is_team_col:
                text = shape_arabic(value)
                draw.text(
                    (x + col_w - 12, y + row_height / 2), text,
                    font=font, fill=color, anchor="rm",
                )
            else:
                draw.text(
                    (x + col_w / 2, y + row_height / 2), value,
                    font=font, fill=color, anchor="mm",
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
# MAIN
# ============================================================

def main():

    import sys

    validate_environment()
    validate_telegram_env()

    competition_name = (
        sys.argv[1] if len(sys.argv) > 1 else "Premier League"
    )

    log(f"Generating standings image for: {competition_name}")

    rows, teams = get_standings_data(competition_name)

    if not rows:
        log("No standings data yet for this competition. Aborting.")
        return

    img = draw_table(competition_name, rows, teams)

    output_path = "standings_output.png"
    img.save(output_path)

    log(f"Image saved: {output_path}")

    telegram_send_photo(output_path)

    log("Sent standings image to Telegram.")


if __name__ == "__main__":
    main()
