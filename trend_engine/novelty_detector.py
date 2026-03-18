from collections import Counter
from core.logger import get_logger

logger = get_logger("NoveltyDetector")


def detect_novelty(posts):
    """
    حساب درجة الجِدّة لكل بوست.
    الـ cluster الأصغر (عدد بوستات أقل) = موضوع أندر = novelty score أعلى.

    Formula: novelty = 1 - (cluster_size / max_cluster_size)
    النتيجة: قيمة بين 0 (شائع جداً) و 1 (جديد/نادر)

    Bug Fix: الاسم كان compute_novelty — غُيِّر لـ detect_novelty
    ليتوافق مع trend_intelligence_agent.
    """
    if not posts:
        logger.warning("No posts to detect novelty")
        return posts

    clusters = [p.get("cluster", 0) for p in posts]
    counts = Counter(clusters)

    if not counts:
        return posts

    max_count = max(counts.values())

    for post in posts:
        cluster_size = counts.get(post.get("cluster", 0), 1)
        novelty = 1 - (cluster_size / max_count)
        post["novelty_score"] = round(novelty, 3)

    logger.info("Novelty scores computed")
    return posts


compute_novelty = detect_novelty