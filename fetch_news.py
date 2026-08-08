"""
السكريبت الرئيسي لبوت الأخبار.
بيسحب من كل المصادر، يفحص التكرار، يترجم ويصيغ (مع تعلم من تصحيحات سابقة)، يولد صورة، ويبعت تليجرام.
"""
import config
from utils import rss_sources, extractor, gemini, supabase_client, telegram, image_gen


def build_translate_prompt(title, body):
    return f"""انت مترجم صحفي محترف. ترجم الخبر ده من الإنجليزية للعربية الفصحى الصحفية، بأسلوب طبيعي مش حرفي. حافظ على كل الحقائق والأرقام والأسماء زي ما هي بالظبط. رجّع الترجمة فقط بدون أي شرح.

العنوان: {title}

النص: {body}"""


def build_review_translation_prompt(original, translated):
    return f"""انت مراجع لغوي. قارن النص الأصلي بالترجمة. تأكد إن كل حقيقة ورقم واسم اتنقل صح. لو فيه خطأ صححه. رجّع النسخة النهائية فقط.

النص الأصلي: {original}

الترجمة: {translated}"""


def build_rewrite_prompt(article_text, correction_examples):
    examples_block = ""
    if correction_examples:
        examples_block = "\n\nأمثلة على تصحيحات سابقة، خد بالك من نفس الأسلوب والملاحظات دي:\n"
        for i, ex in enumerate(correction_examples, 1):
            examples_block += f"\nمثال {i}:\nالمسودة الأصلية: {ex['original_ai_text']}\nالنسخة المصححة (الأفضل): {ex['corrected_text']}\n"

    return f"""انت محرر أخبار رياضية في صحيفة كبرى. اكتب منشور سوشيال ميديا مختصر عن الخبر ده، بالشكل ده بالظبط:
- سطر أول: إيموجي كورة قدم ⚽ متبوع بعنوان قصير جذاب (سطر واحد)
- سطر فاضي
- فقرة أولى: 2-3 جمل تلخص الخبر الأساسي
- سطر فاضي
- فقرة تانية: 2-3 جمل فيها تفاصيل أو سياق إضافي

الحد الأقصى الإجمالي 600 حرف. رجّع الرد بصيغة JSON فقط بالشكل ده: {{"title": "العنوان مع الإيموجي", "body": "الفقرتين مع بعض"}}
{examples_block}
الخبر: {article_text}"""


def build_check_similarity_prompt(original, rewritten):
    return f"""قارن النص المُعاد صياغته بالنص الأصلي. لو فيه جملة أو أكتر قريبة جداً من الأصل، أعد كتابتها بأسلوب مختلف. رجّع الرد بنفس صيغة JSON: {{"title": "...", "body": "..."}}

الأصل: {original}

المُعاد صياغته: {rewritten}"""


def build_image_prompt(article_text):
    return f"""اكتب وصف تصويري (image prompt) بالإنجليزية فقط لصورة تعبيرية عامة عن خبر كورة قدم، من غير محاولة رسم وجوه لاعبين حقيقيين أو شعارات أندية أو أي نص مكتوب داخل الصورة. ركّز على عناصر بصرية رمزية زي: ملعب، كرة قدم، أضواء الاستاد، ألوان عامة، جمهور من بعيد بدون ملامح واضحة. الأسلوب: تصوير احترافي سينمائي، بدون تفاصيل دقيقة لوجوه أو نصوص. رجّع الوصف فقط بدون أي شرح.

الخبر: {article_text}"""


def build_final_review_prompt(title, body, image_prompt):
    return f"""راجع الخبر ده قبل النشر النهائي. تأكد إن العنوان والنص ووصف الصورة متسقين ومنطقيين مع بعض. لو كل حاجة تمام رجّع نفس المحتوى، ولو فيه مشكلة صححها. رجّع JSON فقط: {{"title": "...", "body": "..."}}

العنوان: {title}
النص: {body}
وصف الصورة المستخدمة: {image_prompt}"""


def parse_json_safe(text, fallback_title="", fallback_body=""):
    import json
    import re
    try:
        cleaned = re.sub(r"```json|```", "", text).strip()
        parsed = json.loads(cleaned)
        return parsed.get("title", fallback_title), parsed.get("body", fallback_body)
    except Exception:
        return fallback_title, fallback_body


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

    translation = gemini.call_gemini(build_translate_prompt(title, body), config.GEMINI_API_KEY, config.GEMINI_MODELS)
    if not translation:
        print("  فشلت الترجمة، تخطي.")
        return False

    reviewed_translation = gemini.call_gemini(
        build_review_translation_prompt(body, translation), config.GEMINI_API_KEY, config.GEMINI_MODELS
    )
    reviewed_translation = reviewed_translation or translation

    rewrite_raw = gemini.call_gemini(
        build_rewrite_prompt(reviewed_translation, correction_examples), config.GEMINI_API_KEY, config.GEMINI_MODELS
    )
    if not rewrite_raw:
        print("  فشلت إعادة الصياغة، تخطي.")
        return False
    r_title, r_body = parse_json_safe(rewrite_raw)
    ai_draft_text = f"{r_title}\n\n{r_body}"  # هنحتفظ بيها لو حصل تعديل لاحقاً

    check_raw = gemini.call_gemini(
        build_check_similarity_prompt(body, ai_draft_text), config.GEMINI_API_KEY, config.GEMINI_MODELS
    )
    if check_raw:
        r_title, r_body = parse_json_safe(check_raw, r_title, r_body)

    image_prompt = gemini.call_gemini(
        build_image_prompt(r_title + "\n" + r_body), config.GEMINI_API_KEY, config.GEMINI_MODELS
    )
    image_prompt = image_prompt or "professional football stadium, cinematic lighting, no faces, no text"

    image_url = image_gen.generate_image_url(image_prompt)

    final_raw = gemini.call_gemini(
        build_final_review_prompt(r_title, r_body, image_prompt), config.GEMINI_API_KEY, config.GEMINI_MODELS
    )
    if final_raw:
        r_title, r_body = parse_json_safe(final_raw, r_title, r_body)

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

    # الجارديان (API رسمي)
    try:
        import requests
        resp = requests.get(config.GUARDIAN_URL, params={
            "api-key": config.GUARDIAN_API_KEY,
            "show-fields": "body,headline",
            "page-size": 5,
        }, timeout=20)
        if resp.status_code == 200:
            results = resp.json().get("response", {}).get("results", [])
            for r in results:
                all_candidates.append(("Guardian", r.get("webUrl")))
    except Exception as e:
        print(f"خطأ في جلب الجارديان: {e}")
        
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
