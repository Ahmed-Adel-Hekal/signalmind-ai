from core.logger import get_logger

logger = get_logger("TrendRanker")


class TrendRanker:
    """
    يرتب الترندات النهائية في 4 buckets مرتبة تنازلياً بالـ score.

    Bug Fix #5 (indirect): بعد إصلاح trend_classifier ليكتب trend_state
    بدل trend_type، الـ ranker الآن يصنّف الترندات صح.

    Output structure:
        {
            "exploding": [top 10],
            "growing":   [top 10],
            "future":    [top 10],
            "stable":    [top 10]
        }
    """

    def rank(self, posts):
        if not posts:
            logger.warning("No posts to rank")
            return {"exploding": [], "growing": [], "future": [], "stable": []}

        logger.info(f"Ranking {len(posts)} posts")

        buckets = {"exploding": [], "growing": [], "future": [], "stable": []}

        for post in posts:
            state = post.get("trend_state", "stable")
            forecast = post.get("forecast", "stable")
            post["rank_score"] = post.get("trend_score", 0)

            if state == "exploding":
                buckets["exploding"].append(post)
            elif state == "growing":
                buckets["growing"].append(post)
            elif forecast == "future_trend":
                buckets["future"].append(post)
            else:
                buckets["stable"].append(post)

        # ترتيب تنازلي بالـ rank_score داخل كل bucket
        for key in buckets:
            buckets[key] = sorted(
                buckets[key],
                key=lambda x: x["rank_score"],
                reverse=True
            )[:10]

        logger.info(
            f"Ranked — "
            f"exploding: {len(buckets['exploding'])}, "
            f"growing: {len(buckets['growing'])}, "
            f"future: {len(buckets['future'])}, "
            f"stable: {len(buckets['stable'])}"
        )
        return buckets