import io
import requests
from PIL import Image

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


def draw_arabic_text(draw, xy, text, font, fill, anchor="mm"):

    text = str(text)

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

        response = requests.get(url, timeout=REQUEST_TIMEOUT)
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
    
