"""
سحب نص المقال الكامل من أي رابط باستخدام trafilatura
(بيكتشف المحتوى الرئيسي تلقائياً من غير الحاجة لـ CSS selectors لكل موقع)
"""
import trafilatura


def extract_article(url):
    """
    يرجع dict فيه title و text، أو None لو فشل السحب
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None

        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if not text or len(text.strip()) < 100:
            return None

        metadata = trafilatura.extract_metadata(downloaded)
        title = metadata.title if metadata and metadata.title else ""

        return {"title": title, "text": text.strip()}
    except Exception as e:
        print(f"  خطأ في سحب المقال من {url}: {e}")
        return None
