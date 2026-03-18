"""engine/scraping_sources/reddit_scraper.py — Sprint 4"""
from scraping.base_scraper import BaseScraper

SUBREDDITS = ["programming", "technology", "MachineLearning",
              "artificial", "webdev", "devops", "startups"]


class RedditScraper(BaseScraper):
    SOURCE_NAME = "reddit"

    def fetch(self, limit: int = 100) -> list[dict]:
        posts = []
        per_sub = max(limit // len(SUBREDDITS), 10)

        for sub in SUBREDDITS:
            data = self.get_json(
                f"https://www.reddit.com/r/{sub}/top.json",
                headers={"User-Agent": "ai-trend-engine/1.0"},
                params={"limit": per_sub, "t": "week"},
            )
            if not data:
                continue
            for item in data.get("data", {}).get("children", []):
                p = item.get("data", {})
                post = self.make_post(
                    title=p.get("title", ""),
                    url=p.get("url", ""),
                    source=f"reddit/r/{sub}",
                    score=p.get("score", 0),
                )
                if post:
                    posts.append(post)

        self.logger.info(f"Reddit returned {len(posts)} posts")
        return posts[:limit]


def scrape_reddit(limit: int = 100) -> list[dict]:
    return RedditScraper().fetch(limit)