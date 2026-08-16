import os
import requests


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def main():

    if not BOT_TOKEN:
        raise Exception("TELEGRAM_BOT_TOKEN is missing")

    if not CHAT_ID:
        raise Exception("TELEGRAM_CHAT_ID is missing")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    message = """🚀 اختبار نظام الأخبار

تم الاتصال بنجاح مع Telegram.

Football News Pipeline
Status: ONLINE ✅
"""

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=30
    )

    print("HTTP Status:", response.status_code)
    print("Response:", response.text)

    if response.status_code != 200:
        raise Exception(
            f"Telegram API error: {response.text}"
        )

    print("Telegram message sent successfully ✅")


if __name__ == "__main__":
    main()
