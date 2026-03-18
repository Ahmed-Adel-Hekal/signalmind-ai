from collections import Counter
from core.logger import get_logger

logger = get_logger("TrendVelocity")


def calculate_velocity(posts):
    """
    حساب سرعة الترند بناءً على عدد البوستات في نفس الـ cluster.
    كلما زاد عدد البوستات في cluster → velocity أعلى → ترند أسرع انتشاراً.

    Bug Fix: الاسم كان compute_velocity — غُيِّر لـ calculate_velocity
    ليتوافق مع trend_intelligence_agent.
    """
    if not posts:
        logger.warning("No posts to calculate velocity")
        return posts

    clusters = [p.get("cluster", 0) for p in posts]
    counts = Counter(clusters)

    for post in posts:
        post["trend_velocity"] = counts[post.get("cluster", 0)]

    logger.info(f"Velocity calculated across {len(counts)} clusters")
    return posts


compute_velocity = calculate_velocity