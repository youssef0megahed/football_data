"""
السكريبت الرئيسي لبوت الأخبار.
نسخة مبسّطة: طلبين Gemini بس لكل خبر (بدل 6) لتقليل استهلاك الحصة.
"""
import config
from utils import rss_sources, extractor, gemini, supabase_client, telegram, image_gen


def build_main_prompt(title, body, correction_examples):
    examples_block = ""
    if correction_examples:
        examples_block = "\n\nأمثلة على تصحيحات سابقة، خد بالك من نفس الأسلوب:\n"
        for i, ex in enumerate(correction_examples, 1):
            examples_block += f"\nمثال {i}:\nالمسودة الأصلية: {ex['original_ai_text']}\nالنسخة الأفضل: {ex['corrected_text']}\n"

    return f"""انت محرر أخبار رياضية محترف. نفّذ الخطوات دي بالترتيب على الخبر اللي هبعتهولك:

1. ترجم الخبر من الإنجليزية للعربية الفصحى الصحفية بدقة، محافظاً على كل الحقائق والأرقام والأسماء.
2. أعد صياغته كمنشور سوشيال ميديا مختصر: عنوان جذاب (سطر واحد يبدأ بإيموجي ⚽)، وفقرتين قصار (2-3 جمل لكل فقرة) تلخصان الخبر. الحد الأقصى الإجمالي 600 حرف.
3. تأكد إن الصياغة مش قريبة جداً من الأصل (بأسلوبك الخاص، مش نسخ).
4. اكتب وصف تصويري بالإنجليزية لصورة تعبيرية عامة عن الخبر (ملعب، كرة، أضواء استاد، بدون وجوه حقيقية أو شعارات أو نصوص).
{examples_block}
رجّع الرد بصيغة JSON فقط بالشكل ده بالظبط، من غير أي شرح إضافي:
{{"title": "العنوان مع الإيموجي", "body": "الفقرتين مع بعض", "image_prompt": "الوصف بالإنجليزية"}}

العنوان الأصلي: {title}

النص الأصلي: {body}"""


def build_final_review_prompt(original_body, draft_json_text):
    return f"""راجع المسودة دي قبل النشر النهائي. تأكد من: (1) دقة نقل الحقائق عن الأصل، (2) العنوان والنص ووصف الصورة متسقين مع بعض، (3) الصياغة مش قريبة جداً من الأصل. صحح أي مشكلة لو موجودة. رجّع بنفس صيغة JSON فقط: {{"title": "...", "body": "...", "image_prompt": "..."}}

النص الأصلي: {original_body}

المسودة: {draft_json_text}"""


def parse_json_safe(text, fallback_title="", fallback_body="", fallback_image=""):
    import json
    import re
    try:
        cleaned = re.sub(r"```json|```", "", text).strip()
        parsed = json.loads(cleaned)
        return (
            parsed.get("title", fallback_title),
            parsed.get("body", fallback_body),
            parsed.get("image_prompt", fallback_image),
        )
    except Exception:
        return fallback_title, fallback_body, fallback_image


def process_article(source_name, link, correction_examples):
    print(f"\n--- معالجة: {link} ---")

    if supabase_client.is_duplicate(config.SUPABASE_URL, config.SUPABASE_KEY, link):
        print("  مكرر، تخطي.")
        return False

    article = extractor.extract_article(link)
    if not article or len(article["text"]) < 100:
        print("  فشل سحب المقال أو النص قصير جداً، تخطي.")
        return False

    title, body = article["title"], article["text"]

    # الطلب الأول: ترجمة + صياغة + فحص تطابق + وصف صورة، كل ده مع بعض
    draft_raw = gemini.call_gemini(build_main_prompt(...), config.GEMINI_API_KEY, config.GEMINI_MODELS, config.GROQ_API_KEY)
    
    if not draft_raw:
        print("  فشلت المعالجة الأساسية، تخطي.")
        return False

    r_title, r_body, image_prompt = parse_json_safe(draft_raw)
    if not r_title or not r_body:
        print("  فشل تحليل الرد، تخطي.")
        return False

    ai_draft_text = f"{r_title}\n\n{r_body}"

    # الطلب الثاني: مراجعة نهائية شاملة
    final_raw = gemini.call_gemini(build_main_prompt(...), config.GEMINI_API_KEY, config.GEMINI_MODELS, config.GROQ_API_KEY)
    )
    if final_raw:
        r_title, r_body, image_prompt = parse_json_safe(final_raw, r_title, r_body, image_prompt)

    if not image_prompt:
        image_prompt = "professional football stadium, cinematic lighting, no faces, no text"

    image_url = image_gen.generate_image_url(image_prompt)
    caption = f"{r_title}\n\n{r_body}"

    row = supabase_client.insert_article(
        config.SUPABASE_URL, config.SUPABASE_KEY,
        source_url=link, title=r_title, body=r_body, image_url=image_url,
    )
    if not row:
        print("  فشل حفظ الخبر في Supabase، تخطي الإرسال.")
        return False
    article_id = row["id"]

    msg_id = telegram.send_photo(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, image_url, caption)
    telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, f"المصدر: {link}")
    telegram.send_publish_buttons(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, article_id)

    if msg_id:
        supabase_client.update_article(
            config.SUPABASE_URL, config.SUPABASE_KEY, article_id,
            {"telegram_message_id": msg_id, "ai_draft_text": ai_draft_text},
        )

    print(f"  تم النشر بنجاح: {r_title}")
    return True


def main():
    processed_count = 0
    all_candidates = []

    correction_examples = supabase_client.get_recent_corrections(
        config.SUPABASE_URL, config.SUPABASE_KEY, limit=config.MAX_CORRECTION_EXAMPLES
    )
    print(f"عدد أمثلة التصحيح المستخدمة: {len(correction_examples)}")

    for source_name, rss_url in config.RSS_SOURCES:
        links = rss_sources.get_latest_links(rss_url, limit=config.LINKS_PER_SOURCE)
        for item in links:
            all_candidates.append((source_name, item["link"]))

    print(f"إجمالي الروابط المرشحة: {len(all_candidates)}")

    for source_name, link in all_candidates:
        if processed_count >= config.MAX_ARTICLES_PER_RUN:
            print(f"\nوصلنا للحد الأقصى ({config.MAX_ARTICLES_PER_RUN}) لهذه التشغيلة. توقف.")
            break
        try:
            if process_article(source_name, link, correction_examples):
                processed_count += 1
        except Exception as e:
            print(f"  خطأ غير متوقع في معالجة {link}: {e}")

    print(f"\n=== انتهى التشغيل. عدد الأخبار المنشورة: {processed_count} ===")


if __name__ == "__main__":
    main()
