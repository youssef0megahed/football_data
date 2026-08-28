import os
import io
import requests
from PIL import Image, ImageDraw, ImageFont

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lib.config import validate_environment
from lib.log import log, retry_call
from lib.supabase_client import supabase_request, select
from lib.render_utils import (
    draw_arabic_text, get_logo, draw_placeholder_circle,
    FONT_REGULAR_PATH, FONT_BOLD_PATH,
    COMPETITION_BANNER_COLOR, COMPETITION_NAMES_AR,
)


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TIMEZONE = ZoneInfo("Africa/Cairo")
REQUEST_TIMEOUT = 30


def validate_telegram_env():

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
        )


# ============================================================
# TELEGRAM
# ============================================================

def telegram_send(text):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def request():

        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
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

    return retry_call(request, "Telegram sendMessage")


# ============================================================
# صورة النص (بديل صور Gemini — بترسم نفس نص الرسالة على كارت)
# ============================================================

COLOR_CARD_BG = (16, 19, 28)
COLOR_CARD_TEXT = (240, 240, 245)
COLOR_CARD_ACCENT = (86, 180, 233)


def draw_match_card(
    competition_name, home_team, away_team, center_text,
    extra_lines=None, home_lines=None, away_lines=None,
):

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    banner_color = COMPETITION_BANNER_COLOR.get(
        competition_name, (40, 46, 66)
    )

    width = 800
    banner_height = 150
    team_row_height = 300
    logo_size = 150

    line_height = 48
    blank_gap = 22
    padding_top = 40
    padding_bottom = 50

    two_column = home_lines is not None or away_lines is not None

    if two_column:

        home_lines = home_lines or []
        away_lines = away_lines or []

        content_height = (
            max(len(home_lines), len(away_lines)) * line_height
        )

    else:

        extra_lines = extra_lines or []

        content_height = 0

        for line in extra_lines:
            content_height += (
                line_height if line.strip() else blank_gap
            )

    natural_height = (
        banner_height + team_row_height
        + padding_top + padding_bottom + content_height
    )

    # نستهدف نسبة 4:5 (طولية، أفضل انتشار على فيسبوك) — لو
    # المحتوى أقصر من كده بيتوزع فراغ إضافي فوق وتحت المحتوى
    # عشان الكارت مايبقاش فاضي من غير ما نمطط المحتوى نفسه.
    target_height = int(width * 1.25)

    height = max(natural_height, target_height)

    extra_padding = max(0, height - natural_height)
    content_padding_top = padding_top + extra_padding // 2

    img = Image.new("RGB", (width, height), COLOR_CARD_BG)
    draw = ImageDraw.Draw(img)

    # --- بانر البطولة ---
    draw.rectangle([(0, 0), (width, banner_height)], fill=banner_color)

    font_banner = ImageFont.truetype(FONT_BOLD_PATH, 34)

    draw_arabic_text(
        draw, (width / 2, banner_height / 2), f"🏆 {competition_ar}",
        font=font_banner, fill=(255, 255, 255), anchor="mm",
    )

    # --- صف الفريقين (شعار + اسم)، المضيف يمين والضيف شمال ---
    y_logo = banner_height + (team_row_height - logo_size) // 2 - 15

    home_cx = width * 0.76
    away_cx = width * 0.24

    home_logo = get_logo(home_team.get("logo"), logo_size)
    away_logo = get_logo(away_team.get("logo"), logo_size)

    if home_logo:
        img.paste(
            home_logo,
            (int(home_cx - logo_size / 2), y_logo), home_logo,
        )
    else:
        draw_placeholder_circle(
            draw, home_cx, y_logo + logo_size / 2, logo_size
        )

    if away_logo:
        img.paste(
            away_logo,
            (int(away_cx - logo_size / 2), y_logo), away_logo,
        )
    else:
        draw_placeholder_circle(
            draw, away_cx, y_logo + logo_size / 2, logo_size
        )

    font_team_name = ImageFont.truetype(FONT_BOLD_PATH, 28)

    home_name = (
        home_team.get("name_ar") or home_team.get("name") or "?"
    )
    away_name = (
        away_team.get("name_ar") or away_team.get("name") or "?"
    )

    draw_arabic_text(
        draw, (home_cx, y_logo + logo_size + 30), home_name,
        font=font_team_name, fill=(240, 240, 245), anchor="mm",
    )

    draw_arabic_text(
        draw, (away_cx, y_logo + logo_size + 30), away_name,
        font=font_team_name, fill=(240, 240, 245), anchor="mm",
    )

    # --- النص المركزي (النتيجة أو موعد الماتش) ---
    # النتيجة (زي "0 - 2") أرقام بس؛ اتجاه RTL بيقلب ترتيب
    # المجموعات الرقمية المنفصلة فيها. لكن وقت الماتش فيه كلمة
    # عربية حقيقية (زي "مساءً") ومحتاج RTL عشان تتشكّل صح.
    # فبنقرر حسب محتوى النص نفسه.
    font_center = ImageFont.truetype(FONT_BOLD_PATH, 52)

    has_arabic = any(
        "\u0600" <= ch <= "\u06FF" for ch in center_text
    )

    center_xy = (width / 2, banner_height + team_row_height / 2 - 10)

    if has_arabic:
        draw_arabic_text(
            draw, center_xy, center_text,
            font=font_center, fill=COLOR_CARD_ACCENT, anchor="mm",
        )
    else:
        draw.text(
            center_xy, center_text,
            font=font_center, fill=COLOR_CARD_ACCENT, anchor="mm",
        )

    # --- خط فاصل ---
    y_divider = banner_height + team_row_height

    draw.line(
        [(60, y_divider), (width - 60, y_divider)],
        fill=(58, 62, 80), width=2,
    )

    # --- تفاصيل إضافية ---
    y_start = y_divider + content_padding_top

    font_normal = ImageFont.truetype(FONT_REGULAR_PATH, 24)
    font_sub_header = ImageFont.truetype(FONT_BOLD_PATH, 23)
    font_small = ImageFont.truetype(FONT_REGULAR_PATH, 20)

    if two_column:

        def draw_column(lines, cx):

            y = y_start

            for line in lines:

                line = line.strip()

                is_header = line.startswith("أهداف")

                font, color = (
                    (font_sub_header, (205, 210, 225))
                    if is_header
                    else (font_normal, COLOR_CARD_TEXT)
                )

                draw_arabic_text(
                    draw, (cx, y + line_height / 2), line,
                    font=font, fill=color, anchor="mm",
                )

                y += line_height

        draw_column(home_lines, home_cx)
        draw_column(away_lines, away_cx)

        # فاصل عمودي خفيف بين العمودين
        draw.line(
            [(width / 2, y_divider + 10), (width / 2, height - 15)],
            fill=(45, 49, 64), width=1,
        )

    else:

        y = y_start

        for line in extra_lines:

            line = line.strip()

            if not line:
                y += blank_gap
                continue

            is_hashtag = line.startswith("#")

            font, color = (
                (font_small, (140, 145, 165))
                if is_hashtag
                else (font_normal, COLOR_CARD_TEXT)
            )

            draw_arabic_text(
                draw, (width / 2, y + line_height / 2), line,
                font=font, fill=color, anchor="mm",
            )

            y += line_height

    return img


def build_schedule_card_lines(match):

    kickoff = datetime.fromisoformat(match["kickoff_at"])

    if kickoff.tzinfo is not None:
        kickoff = kickoff.astimezone(TIMEZONE)

    center_text = "VS"

    lines = [
        f"⏰ {format_arabic_time(kickoff)} بتوقيت القاهرة",
        f"📆 {kickoff.date().isoformat()}",
    ]

    return center_text, lines


def build_result_card_lines(match, home_name, away_name, goals, players):

    # المضيف ظاهر يمين الصورة، والقراءة بالعربي بتبدأ من اليمين.
    # عشان رقم المضيف يظهر يمين (يتقرا الأول)، لازم نكتبه في
    # آخر النص (النص بيترسم من الشمال لليمين بدون عكس، فآخر
    # حاجة مكتوبة تطلع أقصى اليمين بصريًا).
    center_text = f"{match['away_score']}  -  {match['home_score']}"

    def format_goal_lines(team_goals):

        output = []

        for goal in team_goals:

            player = players.get(goal.get("player_id"), {})

            player_name = resolve_name(
                player.get("name"), player.get("name_ar")
            )

            minute_text = format_minute(
                goal.get("minute"), goal.get("extra_time")
            )

            if player_name:
                output.append(f"⚽ {player_name} {minute_text}")

        return output

    home_lines = []
    away_lines = []

    if goals:

        home_team_id = match["home_team_id"]
        away_team_id = match["away_team_id"]

        home_goals = [g for g in goals if g.get("team_id") == home_team_id]
        away_goals = [g for g in goals if g.get("team_id") == away_team_id]

        if home_goals:
            home_lines.append(f"أهداف {home_name}:")
            home_lines.extend(format_goal_lines(home_goals))

        if away_goals:
            away_lines.append(f"أهداف {away_name}:")
            away_lines.extend(format_goal_lines(away_goals))

    return center_text, home_lines, away_lines


def telegram_send_photo_bytes_from_image(img, caption=""):

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return telegram_send_photo_bytes(buffer.getvalue(), caption)


def telegram_send_photo_bytes(image_bytes, caption):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    def request():

        response = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"photo": ("cover.png", image_bytes, "image/png")},
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
# HELPERS
# ============================================================

def resolve_name(name, name_ar):
    return name_ar if name_ar else (name or "")


def format_arabic_time(dt_cairo):

    hour = dt_cairo.hour
    minute = dt_cairo.minute

    period = "صباحًا" if hour < 12 else "مساءً"

    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12

    return f"{hour_12:02d}:{minute:02d} {period}"


def get_teams_by_ids(team_ids):

    if not team_ids:
        return {}

    ids = ",".join(str(t) for t in team_ids)

    rows = select(
        "teams",
        {"select": "id,name,name_ar,logo", "id": f"in.({ids})"},
    )

    return {row["id"]: row for row in rows}

# ============================================================
# SCHEDULE MESSAGES (upcoming matches today, not yet posted)
# ============================================================

def get_matches_to_announce():

    today = datetime.now(TIMEZONE).date()

    start = today.isoformat() + "T00:00:00+03:00"
    end = (today + timedelta(days=1)).isoformat() + "T00:00:00+03:00"

    return select(
        "matches",
        {
            "select": (
                "id,competition_id,home_team_id,away_team_id,"
                "kickoff_at,status"
            ),
            "kickoff_at": [f"gte.{start}", f"lt.{end}"],
            "schedule_posted_at": "is.null",
        },
    )


def build_schedule_message(match, teams, competition_name):

    home = teams.get(match["home_team_id"], {})
    away = teams.get(match["away_team_id"], {})

    home_name = resolve_name(home.get("name"), home.get("name_ar"))
    away_name = resolve_name(away.get("name"), away.get("name_ar"))

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    kickoff = datetime.fromisoformat(match["kickoff_at"])

    if kickoff.tzinfo is not None:
        kickoff = kickoff.astimezone(TIMEZONE)

    lines = ["📅 مباراة اليوم", ""]

    if competition_ar:
        lines.append(f"🏆 {competition_ar}")
        lines.append("")

    lines.append(f"⚽ {home_name} 🆚 {away_name}")
    lines.append("")
    lines.append(f"📆 {kickoff.date().isoformat()}")
    lines.append(f"⏰ {format_arabic_time(kickoff)} بتوقيت القاهرة")

    return "\n".join(lines)


# ============================================================
# RESULT MESSAGES (finished matches, not yet posted)
# ============================================================

def get_matches_to_report():

    return select(
        "matches",
        {
            "select": (
                "id,competition_id,home_team_id,away_team_id,"
                "home_score,away_score,status"
            ),
            "status": "eq.FINISHED",
            "result_posted_at": "is.null",
        },
    )


def get_players_by_ids(player_ids):

    if not player_ids:
        return {}

    ids = ",".join(str(p) for p in player_ids if p)

    if not ids:
        return {}

    rows = select(
        "players",
        {"select": "id,name,name_ar", "id": f"in.({ids})"},
    )

    return {row["id"]: row for row in rows}


def get_goals_for_match(match_id):

    return select(
        "match_events",
        {
            "select": "player_id,team_id,minute,extra_time",
            "match_id": f"eq.{match_id}",
            "event_type": "eq.goal",
            "order": "minute.asc",
        },
    )


def format_minute(minute, extra_time):

    if minute is None:
        return ""

    if extra_time:
        return f"{minute}+{extra_time}'"

    return f"{minute}'"


def build_result_message(match, teams, competition_name, goals, players):

    home = teams.get(match["home_team_id"], {})
    away = teams.get(match["away_team_id"], {})

    home_name = resolve_name(home.get("name"), home.get("name_ar"))
    away_name = resolve_name(away.get("name"), away.get("name_ar"))

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    lines = ["🏁 نهاية المباراة", ""]

    if competition_ar:
        lines.append(f"🏆 {competition_ar}")
        lines.append("")

    lines.append(
        f"{home_name} {match['home_score']} - "
        f"{match['away_score']} {away_name}"
    )

    if goals:

        home_team_id = match["home_team_id"]
        away_team_id = match["away_team_id"]

        home_goals = [g for g in goals if g.get("team_id") == home_team_id]
        away_goals = [g for g in goals if g.get("team_id") == away_team_id]

        def format_goal_lines(team_goals):

            output = []

            for goal in team_goals:

                player = players.get(goal.get("player_id"), {})

                player_name = resolve_name(
                    player.get("name"), player.get("name_ar")
                )

                minute_text = format_minute(
                    goal.get("minute"), goal.get("extra_time")
                )

                if player_name:
                    output.append(f"  ⚽ {player_name} {minute_text}")

            return output

        if home_goals:
            lines.append("")
            lines.append(f"أهداف {home_name}:")
            lines.extend(format_goal_lines(home_goals))

        if away_goals:
            lines.append("")
            lines.append(f"أهداف {away_name}:")
            lines.extend(format_goal_lines(away_goals))

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def publish_schedules():

    log("==================================================")
    log("PUBLISH SCHEDULES START")
    log("==================================================")

    competitions = select("competitions", {"select": "id,name"})
    competition_names = {c["id"]: c["name"] for c in competitions}

    to_announce = get_matches_to_announce()

    log(f"Matches to announce (schedule): {len(to_announce)}")

    team_ids = set()

    for m in to_announce:
        team_ids.add(m["home_team_id"])
        team_ids.add(m["away_team_id"])

    teams = get_teams_by_ids(team_ids)

    for match in to_announce:

        try:

            message = build_schedule_message(
                match, teams, competition_names.get(match["competition_id"])
            )

            competition_name = competition_names.get(
                match["competition_id"], ""
            )

            home = teams.get(match["home_team_id"], {})
            away = teams.get(match["away_team_id"], {})

            center_text, extra_lines = build_schedule_card_lines(match)

            card = draw_match_card(
                competition_name, home, away, center_text, extra_lines
            )

            telegram_send_photo_bytes_from_image(card, caption=message)

            supabase_request(
                "PATCH",
                "matches",
                params={"id": f"eq.{match['id']}"},
                json_body={
                    "schedule_posted_at": datetime.now(TIMEZONE).isoformat()
                },
                extra_headers={"Prefer": "return=minimal"},
            )

            log(f"Sent schedule for match={match['id']}")

        except Exception as error:
            log(f"ERROR schedule match={match['id']}: {error}")
            continue

    log("==================================================")
    log("PUBLISH SCHEDULES END")
    log("==================================================")


def publish_results():

    log("==================================================")
    log("PUBLISH RESULTS START")
    log("==================================================")

    competitions = select("competitions", {"select": "id,name"})
    competition_names = {c["id"]: c["name"] for c in competitions}

    to_report = get_matches_to_report()

    log(f"Matches to report (result): {len(to_report)}")

    team_ids = set()

    for m in to_report:
        team_ids.add(m["home_team_id"])
        team_ids.add(m["away_team_id"])

    teams = get_teams_by_ids(team_ids)

    for match in to_report:

        try:

            goals = get_goals_for_match(match["id"])

            player_ids = {g.get("player_id") for g in goals}

            players = get_players_by_ids(player_ids)

            message = build_result_message(
                match,
                teams,
                competition_names.get(match["competition_id"]),
                goals,
                players,
            )

            competition_name = competition_names.get(
                match["competition_id"], ""
            )

            home = teams.get(match["home_team_id"], {})
            away = teams.get(match["away_team_id"], {})

            home_name = resolve_name(home.get("name"), home.get("name_ar"))
            away_name = resolve_name(away.get("name"), away.get("name_ar"))

            center_text, home_lines, away_lines = build_result_card_lines(
                match, home_name, away_name, goals, players
            )

            card = draw_match_card(
                competition_name, home, away, center_text,
                home_lines=home_lines, away_lines=away_lines,
            )

            telegram_send_photo_bytes_from_image(card, caption=message)

            supabase_request(
                "PATCH",
                "matches",
                params={"id": f"eq.{match['id']}"},
                json_body={
                    "result_posted_at": datetime.now(TIMEZONE).isoformat()
                },
                extra_headers={"Prefer": "return=minimal"},
            )

            log(f"Sent result for match={match['id']}")

        except Exception as error:
            log(f"ERROR result match={match['id']}: {error}")
            continue

    log("==================================================")
    log("PUBLISH RESULTS END")
    log("==================================================")


def main():

    import sys

    validate_environment()
    validate_telegram_env()

    mode = sys.argv[1] if len(sys.argv) > 1 else "both"

    if mode in ("schedule", "both"):
        publish_schedules()

    if mode in ("results", "both"):
        publish_results()


if __name__ == "__main__":
    main()
