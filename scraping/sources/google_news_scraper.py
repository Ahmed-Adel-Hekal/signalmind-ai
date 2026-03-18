"""engine/scraping_sources/google_news_scraper.py — Sprint 4"""
from scraping.base_scraper import BaseScraper

QUERIES = [
    "artificial intelligence startup",
    "machine learning technology",
    "software engineering trends",
    "tech startup funding",
]


class GoogleNewsScraper(BaseScraper):
    SOURCE_NAME = "google_news"

    def fetch(self, limit: int = 100) -> list[dict]:
        posts = []
        seen  = set()
        per_q = max(limit // len(QUERIES), 10)

        for query in QUERIES:
            url = (
                f"https://news.google.com/rss/search"
                f"?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
            )
            entries = self.get_feed(url)
            for entry in entries[:per_q]:
                title = getattr(entry, "title", "").strip()
                link  = getattr(entry, "link",  "")
                if title and title not in seen:
                    seen.add(title)
                    post = self.make_post(title, link, "google_news", 1)
                    if post:
                        posts.append(post)
            if len(posts) >= limit:
                break

        self.logger.info(f"Google News returned {len(posts)} posts")
        return posts[:limit]


def scrape_google_news(limit: int = 100) -> list[dict]:
    return GoogleNewsScraper().fetch(limit)