import os
import sys
import requests
from PIL import Image, ImageDraw, ImageFont

from lib.config import validate_environment
from lib.log import log, retry_call
from lib.supabase_client import select
from lib.render_utils import (
    draw_arabic_text, get_logo, draw_placeholder_circle,
    FONT_REGULAR_PATH, FONT_BOLD_PATH,
    COMPETITION_NAMES_AR, COMPETITION_BANNER_COLOR,
    COLOR_BG, COLOR_HEADER_ROW_BG, COLOR_ROW_EVEN, COLOR_ROW_ODD,
    COLOR_BORDER, COLOR_TEXT, COLOR_HEADER_TEXT,
)


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

REQUEST_TIMEOUT = 30

TOP_N = 20


def validate_telegram_env():

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
        )


# ============================================================
# DATA
# ============================================================

def get_competition_and_season(competition_name):

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

    return competition_id, seasons[0]["id"]


def get_top_scorers(competition_name, limit=TOP_N):

    _, season_id = get_competition_and_season(competition_name)

    matches = select(
        "matches", {"select": "id", "season_id": f"eq.{season_id}"}
    )

    match_ids = [m["id"] for m in matches]

    if not match_ids:
        return []

    ids = ",".join(str(i) for i in match_ids)

    events = select(
        "match_events",
        {
            "select": "player_id,team_id",
            "match_id": f"in.({ids})",
            "event_type": "eq.goal",
        },
    )

    counts = {}

    for event in events:

        player_id = event.get("player_id")

        if not player_id:
            continue

        if player_id not in counts:
            counts[player_id] = {
                "player_id": player_id,
                "team_id": event.get("team_id"),
                "goals": 0,
            }

        counts[player_id]["goals"] += 1

    rows = sorted(
        counts.values(), key=lambda r: -r["goals"]
    )[:limit]

    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    return rows


def attach_names(rows):

    player_ids = [r["player_id"] for r in rows]
    team_ids = [r["team_id"] for r in rows if r.get("team_id")]

    players = {}
    teams = {}

    if player_ids:

        ids = ",".join(str(p) for p in player_ids)

        player_rows = select(
            "players",
            {"select": "id,name,name_ar", "id": f"in.({ids})"},
        )

        players = {p["id"]: p for p in player_rows}

    if team_ids:

        ids = ",".join(str(t) for t in team_ids)

        team_rows = select(
            "teams",
            {"select": "id,name,name_ar,logo", "id": f"in.({ids})"},
        )

        teams = {t["id"]: t for t in team_rows}

    return players, teams


# ============================================================
# IMAGE RENDERING
# ============================================================

def draw_top_scorers_table(competition_name, rows, players, teams):

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    banner_height = 110
    header_row_height = 50
    row_height = 78
    logo_size = 40

    col_widths = {"goals": 110, "team": 220, "player": 300, "rank": 70}

    width = sum(col_widths.values())
    height = banner_height + header_row_height + row_height * len(rows)

    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype(FONT_BOLD_PATH, 36)
    font_subtitle = ImageFont.truetype(FONT_REGULAR_PATH, 20)
    font_header = ImageFont.truetype(FONT_BOLD_PATH, 18)
    font_cell = ImageFont.truetype(FONT_BOLD_PATH, 20)
    font_player = ImageFont.truetype(FONT_BOLD_PATH, 21)

    banner_color = COMPETITION_BANNER_COLOR.get(
        competition_name, (30, 41, 59)
    )

    draw.rectangle([(0, 0), (width, banner_height)], fill=banner_color)

    draw_arabic_text(
        draw, (width / 2, banner_height * 0.42), f"⚽ {competition_ar}",
        font=font_title, fill=COLOR_HEADER_TEXT, anchor="mm",
    )

    draw_arabic_text(
        draw, (width / 2, banner_height * 0.75), "قائمة الهدافين",
        font=font_subtitle, fill=(230, 230, 235), anchor="mm",
    )

    y = banner_height

    draw.rectangle(
        [(0, y), (width, y + header_row_height)],
        fill=COLOR_HEADER_ROW_BG,
    )

    header_order = [
        ("rank", "ت"), ("player", "اللاعب"),
        ("team", "الفريق"), ("goals", "الأهداف"),
    ]

    x = width

    for key, label in header_order:

        col_w = col_widths[key]
        x -= col_w

        draw_arabic_text(
            draw, (x + col_w / 2, y + header_row_height / 2), label,
            font=font_header, fill=COLOR_TEXT, anchor="mm",
        )

    y = banner_height + header_row_height

    for row_index, row in enumerate(rows):

        player = players.get(row["player_id"], {})
        player_name = (
            player.get("name_ar") or player.get("name") or "?"
        )

        team = teams.get(row.get("team_id"), {})
        team_name = team.get("name_ar") or team.get("name") or ""

        bg = COLOR_ROW_EVEN if row_index % 2 == 0 else COLOR_ROW_ODD

        draw.rectangle([(0, y), (width, y + row_height)], fill=bg)

        draw.line(
            [(0, y + row_height), (width, y + row_height)],
            fill=COLOR_BORDER, width=1,
        )

        x = width

        # الترتيب
        col_w = col_widths["rank"]
        x -= col_w
        draw_arabic_text(
            draw, (x + col_w / 2, y + row_height / 2), str(row["rank"]),
            font=font_cell, fill=COLOR_TEXT, anchor="mm",
        )

        # اللاعب
        col_w = col_widths["player"]
        x -= col_w
        draw_arabic_text(
            draw, (x + col_w - 12, y + row_height / 2), player_name,
            font=font_player, fill=COLOR_TEXT, anchor="rm",
        )

        # الفريق (شعار + اسم)
        col_w = col_widths["team"]
        x -= col_w

        logo_img = get_logo(team.get("logo"), logo_size)
        logo_x = x + col_w - logo_size - 10
        logo_y = int(y + (row_height - logo_size) / 2)

        if logo_img:
            img.paste(logo_img, (logo_x, logo_y), logo_img)
        else:
            draw_placeholder_circle(
                draw, logo_x + logo_size / 2,
                y + row_height / 2, logo_size,
            )

        draw_arabic_text(
            draw, (logo_x - 10, y + row_height / 2), team_name,
            font=font_cell, fill=COLOR_TEXT, anchor="rm",
        )

        # عدد الأهداف
        col_w = col_widths["goals"]
        x -= col_w
        draw_arabic_text(
            draw, (x + col_w / 2, y + row_height / 2),
            str(row["goals"]),
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

    log(f"Generating top scorers image for: {competition_name}")

    rows = get_top_scorers(competition_name)

    if not rows:
        log("No goal data yet for this competition. Skipping.")
        return

    players, teams = attach_names(rows)

    img = draw_top_scorers_table(competition_name, rows, players, teams)

    safe_name = competition_name.replace(" ", "_")
    output_path = f"top_scorers_{safe_name}.png"
    img.save(output_path)

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    leader = rows[0]
    leader_player = players.get(leader["player_id"], {})
    leader_name = (
        leader_player.get("name_ar") or leader_player.get("name") or "?"
    )

    caption_lines = [
        f"⚽ هدافو {competition_ar}",
        "",
        f"🥇 الصدارة: {leader_name} ({leader['goals']} هدف)",
        "",
        "#كرة_القدم #الهدافين",
    ]

    telegram_send_photo(output_path, caption="\n".join(caption_lines))

    log(f"Sent top scorers image for {competition_name}")


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
