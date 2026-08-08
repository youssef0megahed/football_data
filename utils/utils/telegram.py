"""
دوال إرسال واستقبال الرسائل عبر Telegram Bot API
"""
import requests

BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def send_photo(bot_token, chat_id, photo_url, caption):
    url = BASE_URL.format(token=bot_token, method="sendPhoto")
    resp = requests.post(url, data={
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
    }, timeout=30)
    data = resp.json()
    if data.get("ok"):
        return data["result"]["message_id"]
    print(f"  خطأ في إرسال الصورة: {data}")
    return None


def send_message(bot_token, chat_id, text, reply_markup=None):
    url = BASE_URL.format(token=bot_token, method="sendMessage")
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        import json
        payload["reply_markup"] = json.dumps(reply_markup)
    resp = requests.post(url, data=payload, timeout=30)
    data = resp.json()
    if data.get("ok"):
        return data["result"]["message_id"]
    print(f"  خطأ في إرسال الرسالة: {data}")
    return None


def send_publish_buttons(bot_token, chat_id, article_id):
    """يبعت رسالة فيها زرارين: نشر فيسبوك / تعديل ثم نشر"""
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ نشر فيسبوك", "callback_data": f"publish:{article_id}"},
            {"text": "✏️ تعديل ثم نشر", "callback_data": f"edit:{article_id}"},
        ]]
    }
    return send_message(bot_token, chat_id, "اختار إجراء للخبر ده:", reply_markup)


def get_updates(bot_token, offset=None, timeout=10):
    url = BASE_URL.format(token=bot_token, method="getUpdates")
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(url, params=params, timeout=timeout + 10)
    data = resp.json()
    if data.get("ok"):
        return data["result"]
    print(f"  خطأ في جلب التحديثات: {data}")
    return []


def answer_callback_query(bot_token, callback_query_id, text=""):
    url = BASE_URL.format(token=bot_token, method="answerCallbackQuery")
    requests.post(url, data={"callback_query_id": callback_query_id, "text": text}, timeout=15)
