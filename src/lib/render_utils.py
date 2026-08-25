import io
import requests
from PIL import Image, ImageDraw

from lib.log import log

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

COLOR_BG = (255, 255, 255)
COLOR_HEADER_ROW_BG = (243, 244, 248)
COLOR_ROW_EVEN = (255, 255, 255)
COLOR_ROW_ODD = (250, 250, 252)
COLOR_BORDER = (228, 229, 235)
COLOR_TEXT = (20, 22, 30)
COLOR_HEADER_TEXT = (255, 255, 255)


# ============================================================
# ARABIC TEXT DRAWING (raqm أول، fallback يدوي لو مش متاح)
# ============================================================

_manual_fallback_libs = None


def _get_manual_fallback():

    global _manual_fallback_libs

    if _manual_fallback_libs is None:

        import arabic_reshaper
        from bidi.algorithm import get_display

        _manual_fallback_libs = (arabic_reshaper, get_display)

    return _manual_fallback_libs


import re

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002300-\U000023FF"
    "\U00002600-\U000027BF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)


def strip_emoji(text):
    """خط Cairo مالوش رموز إيموجي خالص — أي إيموجي في نص هيترسم
    على الصورة هيطلع مربع فاضي. بنشيله هنا مركزيًا عشان كل
    الصور تستفيد من الإصلاح من غير ما نكرره في كل سكريبت."""

    return EMOJI_PATTERN.sub("", text).strip()


def draw_arabic_text(draw, xy, text, font, fill, anchor="mm"):

    text = strip_emoji(str(text))

    try:

        draw.text(
            xy, text, font=font, fill=fill,
            anchor=anchor, direction="rtl",
        )

    except Exception:

        arabic_reshaper, get_display = _get_manual_fallback()

        shaped = get_display(arabic_reshaper.reshape(text))

        draw.text(xy, shaped, font=font, fill=fill, anchor=anchor)


# ============================================================
# LOGO DOWNLOAD (best-effort, cached)
# ============================================================

_logo_cache = {}


def get_logo(url, size):

    if not url:
        return None

    cache_key = (url, size)

    if cache_key in _logo_cache:
        return _logo_cache[cache_key]

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        logo = Image.open(io.BytesIO(response.content)).convert("RGBA")
        logo = logo.resize((size, size), Image.LANCZOS)

        _logo_cache[cache_key] = logo

        return logo

    except Exception as error:
        log(f"WARNING: failed to fetch logo {url}: {error}")
        return None


def draw_placeholder_circle(draw, cx, cy, size):

    r = size / 2

    draw.ellipse(
        [(cx - r, cy - r), (cx + r, cy + r)],
        fill=(225, 227, 233),
        outline=COLOR_BORDER,
    )


# ============================================================
# PLAYER HEADSHOTS (ESPN CDN — نمط ثابت اتأكدنا منه)
# ============================================================

def get_player_headshot_url(source_player_id):

    if not source_player_id:
        return None

    return (
        "https://a.espncdn.com/i/headshots/soccer/players/full/"
        f"{source_player_id}.png"
    )


def get_diamond_photo(url, size):
    """يرجع صورة اللاعب مقصوصة بشكل معين (diamond) بحواف بيضاء،
    أو None لو مفيش صورة/فشل التحميل."""

    photo = get_logo(url, size)

    if not photo:
        return None

    # قناع المعين (rotate square = diamond)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.polygon(
        [(size / 2, 0), (size, size / 2), (size / 2, size), (0, size / 2)],
        fill=255,
    )

    diamond = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    diamond.paste(photo, (0, 0), mask)

    return diamond


def draw_diamond_frame(draw, cx, cy, size, border_color, width=4):
    """بيرسم إطار المعين الأبيض حوالين الصورة."""

    half = size / 2

    draw.polygon(
        [
            (cx, cy - half), (cx + half, cy),
            (cx, cy + half), (cx - half, cy),
        ],
        outline=border_color, width=width,
        )
            
