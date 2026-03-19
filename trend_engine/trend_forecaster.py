from core.logger import get_logger

logger = get_logger("TrendForecaster")


class TrendForecaster:

    def forecast(self, posts):
        if not posts:
            logger.warning("No posts to forecast")
            return posts

        counts = {"viral": 0, "future_trend": 0, "stable": 0}

        for post in posts:
            score = post.get("trend_score", 0)
            state = post.get("trend_state", "stable")

            if state == "exploding":
                post["forecast"] = "viral"
                counts["viral"] += 1

            elif state == "growing" and score > 12:
                post["forecast"] = "future_trend"
                counts["future_trend"] += 1

            else:
                post["forecast"] = "stable"
                counts["stable"] += 1

        logger.info(
            f"Forecast done — "
            f"viral: {counts['viral']}, "
            f"future: {counts['future_trend']}, "
            f"stable: {counts['stable']}"
        )
        return posts
