from collections import defaultdict
from core.logger import get_logger

logger = get_logger("TrendTimeAnalyzer")

EXPLODING_THRESHOLD = 15
GROWING_THRESHOLD = 8


class TrendTimeAnalyzer:

    def enrich(self, posts: list) -> list:
        if not posts:
            return posts
        if "cluster" not in posts[0]:
            logger.warning("Posts not clustered yet — skipping TrendTimeAnalyzer")
            return posts
        if "trend_velocity" not in posts[0]:
            logger.warning("Velocity not calculated yet — skipping TrendTimeAnalyzer")
            return posts

        clusters = defaultdict(list)
        for post in posts:
            clusters[post["cluster"]].append(post)

        cluster_states = {}
        for cluster_id, items in clusters.items():
            avg_velocity = sum(p.get("trend_velocity", 0) for p in items) / len(items)
            avg_novelty  = sum(p.get("novelty_score", 0) for p in items) / len(items)
            cluster_score = (avg_velocity * 0.6) + (avg_novelty * 0.4)

            if cluster_score > EXPLODING_THRESHOLD:
                state = "exploding"
            elif cluster_score > GROWING_THRESHOLD:
                state = "growing"
            else:
                state = "stable"

            cluster_states[cluster_id] = {
                "cluster_score": round(cluster_score, 3),
                "cluster_state": state,
                "cluster_size":  len(items),
            }

        for post in posts:
            c = cluster_states.get(post["cluster"], {})
            post["cluster_score"] = c.get("cluster_score", 0)
            post["cluster_state"] = c.get("cluster_state", "stable")
            post["cluster_size"]  = c.get("cluster_size", 1)

        exploding = sum(1 for c in cluster_states.values() if c["cluster_state"] == "exploding")
        growing   = sum(1 for c in cluster_states.values() if c["cluster_state"] == "growing")
        stable    = sum(1 for c in cluster_states.values() if c["cluster_state"] == "stable")

        logger.info(
            f"Cluster analysis done — "
            f"exploding: {exploding}, growing: {growing}, stable: {stable} "
            f"(across {len(clusters)} clusters, {len(posts)} posts)"
        )
        return posts

    def get_cluster_summary(self, posts: list) -> list:
        clusters = defaultdict(list)
        for post in posts:
            clusters[post["cluster"]].append(post)

        summary = []
        for cluster_id, items in clusters.items():
            summary.append({
                "cluster_id":    cluster_id,
                "cluster_state": items[0].get("cluster_state", "stable"),
                "cluster_score": items[0].get("cluster_score", 0),
                "size":          len(items),
                "top_topics":    [p["title"] for p in
                                  sorted(items, key=lambda x: x.get("trend_score", 0), reverse=True)[:5]],
            })

        return sorted(summary, key=lambda x: x["cluster_score"], reverse=True)
