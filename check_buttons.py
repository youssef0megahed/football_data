"""
بيفحص أي ضغطات جديدة على أزرار "نشر" أو "تعديل" في تليجرام، وينشر على فيسبوك حسب الاختيار.
لو حصل تعديل، بيسجل (المسودة الأصلية + التعديل) في أرشيف التصحيحات عشان النظام يتعلم منه.
"""
import requests
import config
from utils import telegram, supabase_client


def publish_to_facebook(image_url, caption):
    url = f"https://graph.facebook.com/v19.0/{config.FB_PAGE_ID}/photos"
    resp = requests.post(url, data={
        "url": image_url,
        "caption": caption,
        "access_token": config.FB_PAGE_ACCESS_TOKEN,
    }, timeout=30)
    data = resp.json()
    if "id" in data:
        return True
    print(f"  خطأ في النشر على فيسبوك: {data}")
    return False


def handle_publish(article_id, chat_id):
    article = supabase_client.get_article_by_id(config.SUPABASE_URL, config.SUPABASE_KEY, article_id)
    if not article:
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, chat_id, "❌ الخبر غير موجود.")
        return

    caption = f"{article['title']}\n\n{article['body']}"
    success = publish_to_facebook(article["image_url"], caption)

    if success:
        supabase_client.update_article(config.SUPABASE_URL, config.SUPABASE_KEY, article_id, {"published_to_fb": True})
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, chat_id, "✅ تم النشر على فيسبوك بنجاح")
    else:
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, chat_id, "❌ فشل النشر على فيسبوك، جرب تاني")


def handle_edit_request(article_id, chat_id):
    telegram.send_message(
        config.TELEGRAM_BOT_TOKEN, chat_id,
        f"✏️ ردّ (Reply) على رسالة الخبر دي بالنص الجديد اللي عايزه ينشر.\n(رقم الخبر: {article_id})"
    )


def handle_edit_reply(message):
    reply_to = message.get("reply_to_message")
    if not reply_to:
        return

    original_msg_id = reply_to.get("message_id")
    article = supabase_client.get_article_by_telegram_message_id(
        config.SUPABASE_URL, config.SUPABASE_KEY, original_msg_id
    )
    if not article:
        return

    new_text = message.get("text", "")
    chat_id = message["chat"]["id"]

    success = publish_to_facebook(article["image_url"], new_text)
    if success:
        supabase_client.update_article(
            config.SUPABASE_URL, config.SUPABASE_KEY, article["id"], {"published_to_fb": True}
        )
        # تسجيل التصحيح في الأرشيف عشان النظام يتعلم منه في المرات الجاية
        original_draft = article.get("ai_draft_text") or f"{article['title']}\n\n{article['body']}"
        supabase_client.add_correction(config.SUPABASE_URL, config.SUPABASE_KEY, original_draft, new_text)

        telegram.send_message(config.TELEGRAM_BOT_TOKEN, chat_id, "✅ تم نشر النص المعدّل، وحفظنا التصحيح عشان نتعلم منه")
    else:
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, chat_id, "❌ فشل النشر، جرب تاني")


def main():
    last_update_id = supabase_client.get_bot_state(config.SUPABASE_URL, config.SUPABASE_KEY, "last_update_id")
    offset = int(last_update_id) + 1 if last_update_id else None

    updates = telegram.get_updates(config.TELEGRAM_BOT_TOKEN, offset=offset)
    if not updates:
        print("مفيش تحديثات جديدة.")
        return

    max_update_id = offset - 1 if offset else 0

    for update in updates:
        max_update_id = max(max_update_id, update["update_id"])

        if "callback_query" in update:
            cq = update["callback_query"]
            data = cq.get("data", "")
            chat_id = cq["message"]["chat"]["id"]
            telegram.answer_callback_query(config.TELEGRAM_BOT_TOKEN, cq["id"])

            if data.startswith("publish:"):
                article_id = data.split(":", 1)[1]
                print(f"معالجة نشر مباشر للخبر: {article_id}")
                handle_publish(article_id, chat_id)
            elif data.startswith("edit:"):
                article_id = data.split(":", 1)[1]
                print(f"طلب تعديل للخبر: {article_id}")
                handle_edit_request(article_id, chat_id)

        elif "message" in update and "reply_to_message" in update["message"]:
            print("معالجة رد تعديل...")
            handle_edit_reply(update["message"])

    supabase_client.set_bot_state(config.SUPABASE_URL, config.SUPABASE_KEY, "last_update_id", str(max_update_id))
    print(f"تم تحديث آخر update_id إلى: {max_update_id}")


if __name__ == "__main__":
    main()
