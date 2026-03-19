from core.logger import get_logger

logger = get_logger("TrendScorer")


def score_trends(posts):
    """
    حساب الـ trend_score النهائي لكل بوست.
    Formula: score = (velocity * 0.7) + (novelty * 0.3)
    - velocity تأخذ وزن 70%: الانتشار السريع الأهم
    - novelty تأخذ وزن 30%: الجِدّة مكمّلة مش أساسية

    Bug Fix: الاسم كان compute_trend_score — غُيِّر لـ score_trends
    ليتوافق مع trend_intelligence_agent.
    """
    if not posts:
        logger.warning("No posts to score")
        return posts

    for post in posts:
        velocity = post.get("trend_velocity", 0)
        novelty = post.get("novelty_score", 0)
        score = (velocity * 0.7) + (novelty * 0.3)
        post["trend_score"] = round(score, 3)

    logger.info(f"Trend scores computed for {len(posts)} posts")
    return posts


compute_trend_score = score_trends