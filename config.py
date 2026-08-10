"""
إعدادات المشروع - كل المفاتيح بتتقرأ من GitHub Secrets (متغيرات البيئة)
مفيش أي مفتاح مكتوب هنا مباشرة، عشان الريبو Public.
"""
import os

GUARDIAN_API_KEY = os.environ.get("GUARDIAN_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
HCTI_USER_ID = os.environ.get("HCTI_USER_ID", "")
HCTI_API_KEY = os.environ.get("HCTI_API_KEY", "")


# نماذج Gemini بترتيب المحاولة (الأقوى الأول، ثم البديل عند الفشل)
GEMINI_MODELS = ["gemini-3.1-pro","gemini-3.6-flash",]

# أقصى عدد أخبار جديدة تتعالج في التشغيلة الواحدة
MAX_ARTICLES_PER_RUN = 10

# أقصى عدد أخبار تُجلب من كل مصدر قبل الفلترة
LINKS_PER_SOURCE = 10

# أقصى عدد أمثلة من أرشيف التصحيحات تتحط في الـ prompt (Few-Shot)
MAX_CORRECTION_EXAMPLES = 4

# المصادر: (الاسم, رابط RSS)
RSS_SOURCES = [
    ("BBC", "https://feeds.bbci.co.uk/sport/football/rss.xml"),
    ("90min", "https://www.90min.com/posts.rss"),
    ("Soccernews", "https://soccernews.com/feed"),
    ("101GreatGoals", "https://www.101greatgoals.com/feed"),
    ("FootballFanCast", "https://www.footballfancast.com/feed"),
    ("InsideWorldFootball", "https://www.insideworldfootball.com/feed"),
    ("CaughtOffside", "https://www.caughtoffside.com/feed"),
    ("Football365", "https://www.football365.com/feed"),
    ("Guardian", "https://www.theguardian.com/football/rss"),
]

# api-football
API_FOOTBALL_BASE = "https://api-football-v1.p.rapidapi.com/v3"
API_FOOTBALL_HOST = "api-football-v1.p.rapidapi.com"
LEAGUE_ID = 39      # 39 = الدوري الإنجليزي، عدّله حسب الدوري اللي عايزه
SEASON = 2026

# FPL Official API (مجاني، بدون مفتاح، مقصور على الدوري الإنجليزي)
FPL_BASE = "https://fantasy.premierleague.com/api"
