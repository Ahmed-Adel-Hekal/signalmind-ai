from core.logger import get_logger

logger = get_logger("Deduplicator")


def deduplicate_posts(posts):
    """
    إزالة البوستات المتكررة بناءً على العنوان.
    Bug Fix: الاسم كان remove_duplicates — غُيِّر لـ deduplicate_posts
    ليتوافق مع trend_intelligence_agent.
    """
    seen = set()
    unique_posts = []

    for post in posts:
        title = post.get("title", "").strip()

        if not title:
            continue

        if title in seen:
            continue

        seen.add(title)
        unique_posts.append(post)

    logger.info(f"Deduplicated: {len(posts)} → {len(unique_posts)} posts")
    return unique_posts


remove_duplicates = deduplicate_posts