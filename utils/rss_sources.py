"""
جلب أحدث روابط الأخبار من كل مصدر RSS
"""
import feedparser


def get_latest_links(rss_url, limit=5):
    """يرجع قائمة dicts فيها link و title لأحدث الأخبار من مصدر RSS"""
    try:
        feed = feedparser.parse(rss_url)
        items = []
        for entry in feed.entries[:limit]:
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", "")
            if link:
                items.append({"link": link, "title": title})
        return items
    except Exception as e:
        print(f"  خطأ في جلب RSS من {rss_url}: {e}")
        return []
