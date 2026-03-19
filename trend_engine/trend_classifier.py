from core.logger import get_logger

logger = get_logger("TrendClassifier")

# حدود التصنيف — سهل تعديلها من مكان واحد
EXPLODING_THRESHOLD = 20
GROWING_THRESHOLD = 10


def classify_trends(posts):
    """
    تصنيف كل بوست بناءً على الـ trend_score.

    Bug Fix #5: الكود القديم كان يكتب trend_type لكن
    TrendForecaster و TrendRanker يقرأون trend_state.
    الحل: استخدام trend_state فقط في كل مكان.

    Classes:
        exploding : score > 20
        growing   : score > 10
        stable    : score <= 10
    """
    if not posts:
        logger.warning("No posts to classify")
        return posts

    counts = {"exploding": 0, "growing": 0, "stable": 0}

    for post in posts:
        score = post.get("trend_score", 0)

        if score > EXPLODING_THRESHOLD:
            state = "exploding"
        elif score > GROWING_THRESHOLD:
            state = "growing"
        else:
            state = "stable"

        # Bug Fix: trend_state (موحّد) بدل trend_type (القديم)
        post["trend_state"] = state
        counts[state] += 1

    logger.info(
        f"Classification done — "
        f"exploding: {counts['exploding']}, "
        f"growing: {counts['growing']}, "
        f"stable: {counts['stable']}"
    )
    return posts