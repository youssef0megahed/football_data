"""
دوال إرسال الرسائل والصور عبر Telegram Bot API
"""
import requests

BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def send_message(bot_token, chat_id, text):
    url = BASE_URL.format(token=bot_token, method="sendMessage")
    resp = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
    data = resp.json()
    if data.get("ok"):
        return data["result"]["message_id"]
    print(f"  خطأ في إرسال الرسالة: {data}")
    return None


def send_photo(bot_token, chat_id, photo_url, caption=""):
    url = BASE_URL.format(token=bot_token, method="sendPhoto")
    resp = requests.post(url, data={
        "chat_id": chat_id, "photo": photo_url, "caption": caption,
    }, timeout=30)
    data = resp.json()
    if data.get("ok"):
        return data["result"]["message_id"]
    print(f"  خطأ في إرسال الصورة: {data}")
    return None
