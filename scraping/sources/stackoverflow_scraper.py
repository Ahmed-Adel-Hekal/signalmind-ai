"""engine/scraping_sources/stackoverflow_scraper.py — Sprint 4"""
from scraping.base_scraper import BaseScraper


class StackOverflowScraper(BaseScraper):
    SOURCE_NAME = "stackoverflow"

    def fetch(self, limit: int = 50) -> list[dict]:
        data = self.get_json(
            "https://api.stackexchange.com/2.3/questions",
            params={
                "order": "desc", "sort": "hot",
                "site": "stackoverflow",
                "pagesize": limit,
                "filter": "default",
            },
        )
        if not data:
            return []

        posts = []
        for item in data.get("items", [])[:limit]:
            post = self.make_post(
                title=item.get("title", ""),
                url=item.get("link", ""),
                source="stackoverflow",
                score=item.get("score", 0) + item.get("answer_count", 0),
            )
            if post:
                posts.append(post)

        self.logger.info(f"StackOverflow returned {len(posts)} posts")
        return posts


def scrape_stackoverflow(limit: int = 50) -> list[dict]:
    return StackOverflowScraper().fetch(limit)