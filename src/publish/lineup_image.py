import os
import sys
import io
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

from lib.config import validate_environment
from lib.log import log, retry_call
from lib.supabase_client import select, supabase_request
from lib.render_utils import (
    draw_arabic_text, get_logo,
    FONT_REGULAR_PATH, FONT_BOLD_PATH,
    COMPETITION_NAMES_AR, COMPETITION_BANNER_COLOR,
)


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TIMEZONE = ZoneInfo("Africa/Cairo")
REQUEST_TIMEOUT = 30

# نفحص المباريات اللي هتبدأ خلال الفترة دي، لأن ESPN بينشر
# التشكيلة الرسمية عادة قبل الماتش بساعة تقريبًا.
LOOKAHEAD_MINUTES = 120

COLOR_BG = (18, 20, 28)
COLOR_TEXT = (240, 240, 245)
COLOR_JERSEY_BG = (45, 50, 68)


def validate_telegram_env():

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
        )


# ============================================================
# المباريات المرشحة للإعلان عن التشكيلة تلقائيًا
# ============================================================

def get_matches_needing_lineup():

    now = datetime.now(TIMEZONE)
    end = now + timedelta(minutes=LOOKAHEAD_MINUTES)

    return select(
        "matches",
        {
            "select": "id,kickoff_at",
            "status": "eq.SCHEDULED",
            "kickoff_at": [
                f"gte.{now.isoformat()}",
                f"lte.{end.isoformat()}",
            ],
            "lineup_posted_at": "is.null",
        },
    )


def mark_lineup_posted(match_id):

    supabase_request(
        "PATCH",
        "matches",
        params={"id": f"eq.{match_id}"},
        json_body={
            "lineup_posted_at": datetime.now(TIMEZONE).isoformat()
        },
        extra_headers={"Prefer": "return=minimal"},
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

# ============================================================
# ألوان الفريق (تحويل hex لـ RGB + لون نص متباين)
# ============================================================

def hex_to_rgb(hex_color, fallback=(60, 130, 90)):

    if not hex_color:
        return fallback

    hex_color = hex_color.lstrip("#")

    if len(hex_color) != 6:
        return fallback

    try:
        return tuple(
            int(hex_color[i:i + 2], 16) for i in (0, 2, 4)
        )
    except ValueError:
        return fallback


def contrasting_text_color(rgb):

    r, g, b = rgb

    luminance = (0.299 * r + 0.587 * g + 0.114 * b)

    return (20, 20, 25) if luminance > 150 else (255, 255, 255)


def blend(color_a, color_b, ratio):

    return tuple(
        int(a * (1 - ratio) + b * ratio)
        for a, b in zip(color_a, color_b)
    )


PITCH_BASE = (18, 40, 28)


# ============================================================
# رسم أيقونة قميص بدل صورة اللاعب
# ============================================================

def draw_jersey_icon(draw, cx, cy, size, team_color, jersey_number):

    text_color = contrasting_text_color(team_color)

    half = size / 2

    # جسم القميص (مستطيل بحواف دائرية)
    draw.rounded_rectangle(
        [(cx - half, cy - half), (cx + half, cy + half)],
        radius=size * 0.18,
        fill=team_color,
        outline=(255, 255, 255),
        width=2,
    )

    # فتحة الرقبة (نصف دائرة صغيرة فوق)
    neck_r = size * 0.16

    draw.ellipse(
        [
            (cx - neck_r, cy - half - neck_r * 0.4),
            (cx + neck_r, cy - half + neck_r * 0.9),
        ],
        fill=PITCH_BASE,
    )

    if jersey_number:

        font_num = ImageFont.truetype(
            FONT_BOLD_PATH, int(size * 0.42)
        )

        draw.text(
            (cx, cy + size * 0.05), str(jersey_number),
            font=font_num, fill=text_color, anchor="mm",
        )


# ============================================================
# رسم خطوط الملعب (نص ملعب واحد، من حرف لحرف)
# ============================================================

def draw_pitch_half(draw, x0, y0, x1, y1, goal_at_top):

    line_color = (255, 255, 255, 60)
    width_line = 2

    # حدود النص
    draw.rectangle(
        [(x0, y0), (x1, y1)], outline=(255, 255, 255), width=width_line
    )

    pitch_width = x1 - x0

    goal_box_w = pitch_width * 0.36
    goal_box_h = (y1 - y0) * 0.14

    goal_x0 = x0 + (pitch_width - goal_box_w) / 2
    goal_x1 = goal_x0 + goal_box_w

    if goal_at_top:
        draw.rectangle(
            [(goal_x0, y0), (goal_x1, y0 + goal_box_h)],
            outline=(255, 255, 255), width=width_line,
        )
    else:
        draw.rectangle(
            [(goal_x0, y1 - goal_box_h), (goal_x1, y1)],
            outline=(255, 255, 255), width=width_line,
        )


# ============================================================
# الرسم الرئيسي
# ============================================================

def draw_lineup(match, competition_name, lineup_rows, players, teams):

    home = teams.get(match["home_team_id"], {})
    away = teams.get(match["away_team_id"], {})

    home_name = home.get("name_ar") or home.get("name") or "?"
    away_name = away.get("name_ar") or away.get("name") or "?"

    home_color = hex_to_rgb(home.get("color"), fallback=(30, 90, 190))
    away_color = hex_to_rgb(
        away.get("color"), fallback=(190, 40, 40)
    )

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

        # من الحارس للهجوم (بره لجوه) عشان الرسم من طرف الملعب للنص
        return [rows[r] for r in ["GK", "DEF", "MID", "FWD"] if rows[r]]

    home_rows = build_rows(match["home_team_id"])
    away_rows = build_rows(match["away_team_id"])

    width = 900
    banner_height = 130
    jersey_size = 74
    row_height = 155
    margin = 30

    max_rows = max(len(home_rows), len(away_rows), 1)

    half_height = max_rows * row_height + 40

    height = banner_height + half_height * 2

    img = Image.new("RGB", (width, height), PITCH_BASE)
    draw = ImageDraw.Draw(img)

    # --- خلفية كل نص بلون الفريق (تعتيم خفيف فوق أرضية الملعب) ---
    away_bg = blend(PITCH_BASE, away_color, 0.28)
    home_bg = blend(PITCH_BASE, home_color, 0.28)

    draw.rectangle(
        [(0, banner_height), (width, banner_height + half_height)],
        fill=away_bg,
    )

    draw.rectangle(
        [(0, banner_height + half_height), (width, height)],
        fill=home_bg,
    )

    # --- خطوط الملعب لكل نص ---
    draw_pitch_half(
        draw, margin, banner_height + margin,
        width - margin, banner_height + half_height,
        goal_at_top=True,
    )

    draw_pitch_half(
        draw, margin, banner_height + half_height,
        width - margin, height - margin,
        goal_at_top=False,
    )

    # --- دائرة المنتصف (حيث يلتقي الفريقان) ---
    mid_y = banner_height + half_height

    draw.ellipse(
        [(width / 2 - 55, mid_y - 55), (width / 2 + 55, mid_y + 55)],
        outline=(255, 255, 255), width=2,
    )

    draw.line(
        [(margin, mid_y), (width - margin, mid_y)],
        fill=(255, 255, 255), width=2,
    )

    # --- بانر العنوان ---
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

    font_title = ImageFont.truetype(FONT_BOLD_PATH, 28)
    font_subtitle = ImageFont.truetype(FONT_REGULAR_PATH, 17)

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

    # --- رسم اللاعبين ---
    font_name = ImageFont.truetype(FONT_BOLD_PATH, 17)

    def draw_team(rows, team_color, top_y, direction):
        """direction=1 يعني بنرسم من top_y نازلين (الفريق البعيد/away)،
        direction=-1 يعني بنرسم من top_y طالعين لفوق (الفريق home)."""

        for row_index, row_players in enumerate(rows):

            row_y = top_y + direction * (
                40 + row_index * row_height
            )

            count = len(row_players)
            spacing = width / (count + 1)

            for i, entry in enumerate(row_players, start=1):

                cx = spacing * i

                draw_jersey_icon(
                    draw, cx, row_y, jersey_size,
                    team_color, entry.get("jersey_number"),
                )

                player = players.get(entry["player_id"], {})

                name = (
                    player.get("name_ar")
                    or player.get("name")
                    or "?"
                )

                badge_y = row_y + jersey_size / 2 + 22

                text_w = font_name.getlength(name) + 24

                draw.rounded_rectangle(
                    [
                        (cx - text_w / 2, badge_y - 16),
                        (cx + text_w / 2, badge_y + 16),
                    ],
                    radius=14,
                    fill=(15, 15, 20),
                    outline=(255, 255, 255),
                    width=1,
                )

                draw_arabic_text(
                    draw, (cx, badge_y), name,
                    font=font_name, fill=(255, 255, 255), anchor="mm",
                )

    # away: من فوق (جوار جولها) نازلين لحد نص الملعب
    draw_team(away_rows, away_color, banner_height, direction=1)

    # home: من تحت (جوار جولهم) طالعين لحد نص الملعب
    draw_team(home_rows, home_color, height, direction=-1)

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

def process_one_match(match_id):
    """يرجع True لو اتبعتت تشكيلة فعليًا، False لو لسه مش جاهزة."""

    log(f"Checking lineup for match={match_id}")

    match, competition_name, lineup_rows, players, teams = (
        get_lineup_data(match_id)
    )

    if not lineup_rows:
        log(f"match={match_id}: no lineup data yet.")
        return False

    # نتأكد إن التشكيلة مكتملة (11 أساسي لكل فريق) قبل النشر،
    # عشان منبعتش تشكيلة ناقصة لسه بتتحدّث من ESPN.
    home_count = sum(
        1 for r in lineup_rows
        if r["team_id"] == match["home_team_id"]
    )
    away_count = sum(
        1 for r in lineup_rows
        if r["team_id"] == match["away_team_id"]
    )

    if home_count < 11 or away_count < 11:
        log(
            f"match={match_id}: lineup incomplete "
            f"(home={home_count}, away={away_count}). "
            f"Will retry next run."
        )
        return False

    img = draw_lineup(
        match, competition_name, lineup_rows, players, teams
    )

    output_path = f"lineup_{match_id}.png"
    img.save(output_path)

    telegram_send_photo(output_path, caption="📋 التشكيلة الرسمية")

    log(f"match={match_id}: lineup image sent.")

    return True


def main():

    validate_environment()
    validate_telegram_env()

    # وضع يدوي/تشخيصي: تحديد ماتش بعينه بالـ id
    if len(sys.argv) >= 2:

        match_id = int(sys.argv[1])

        sent = process_one_match(match_id)

        if sent:
            mark_lineup_posted(match_id)

        return

    # الوضع التلقائي: أي ماتش هيبدأ قريب ولسه ما اتبعتش له تشكيلة
    log("==================================================")
    log("AUTO LINEUP PUBLISHER START")
    log("==================================================")

    matches = get_matches_needing_lineup()

    log(f"Candidate matches: {len(matches)}")

    for match in matches:

        try:

            sent = process_one_match(match["id"])

            if sent:
                mark_lineup_posted(match["id"])

        except Exception as error:
            log(f"ERROR match={match['id']}: {error}")
            continue

    log("==================================================")
    log("AUTO LINEUP PUBLISHER END")
    log("==================================================")


if __name__ == "__main__":
    main()

    
