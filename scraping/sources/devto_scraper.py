"""engine/scraping_sources/devto_scraper.py — Sprint 4"""
from scraping.base_scraper import BaseScraper


class DevToScraper(BaseScraper):
    SOURCE_NAME = "devto"

    def fetch(self, limit: int = 50) -> list[dict]:
        data = self.get_json(
            "https://dev.to/api/articles",
            params={"per_page": limit, "top": 7},   # top articles آخر 7 أيام
        )
        if not data:
            return []

        posts = []
        for item in data[:limit]:
            post = self.make_post(
                title=item.get("title", ""),
                url=item.get("url", ""),
                source="devto",
                score=item.get("positive_reactions_count", 0)
                      + item.get("comments_count", 0),
            )
            if post:
                posts.append(post)

        self.logger.info(f"Dev.to returned {len(posts)} posts")
        return posts


def scrape_devto(limit: int = 50) -> list[dict]:
    return DevToScraper().fetch(limit)