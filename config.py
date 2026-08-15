import os

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
HCTI_USER_ID = os.environ.get("HCTI_USER_ID", "")
HCTI_API_KEY = os.environ.get("HCTI_API_KEY", "")
FPL_BASE = "https://fantasy.premierleague.com/api"

API_FOOTBALL_BASE = "https://api-football-v1.p.rapidapi.com/v3"
API_FOOTBALL_HOST = "api-football-v1.p.rapidapi.com"

LEAGUE_IDS = {
    "الدوري الإنجليزي": 39,
    "الليجا الإسبانية": 140,
    "الدوري الإيطالي": 135,
    "البوندسليجا": 78,
    "الليج 1 الفرنسي": 61,
    "دوري أبطال أوروبا": 2,
}

TRACKED_CLUBS = {
    "Manchester City": "مانشستر سيتي",
    "Arsenal": "أرسنال",
    "Chelsea": "تشيلسي",
    "Liverpool": "ليفربول",
    "Aston Villa": "أستون فيلا",
    "Manchester United": "مانشستر يونايتد",
    "Barcelona": "برشلونة",
    "Real Madrid": "ريال مدريد",
    "Atletico Madrid": "أتلتيكو مدريد",
    "Bayern Munich": "بايرن ميونخ",
    "Borussia Dortmund": "بوروسيا دورتموند",
    "Paris Saint Germain": "باريس سان جيرمان",
    "AC Milan": "إيه سي ميلان",
    "Juventus": "يوفنتوس",
    "Napoli": "نابولي",
    "Inter": "إنتر ميلان",
}
