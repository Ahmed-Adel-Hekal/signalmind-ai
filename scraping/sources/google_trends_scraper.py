"""engine/scraping_sources/google_trends_scraper.py — Sprint 4"""
from scraping.base_scraper import BaseScraper

REGIONS = ["united_states", "egypt", "united_kingdom"]


class GoogleTrendsScraper(BaseScraper):
    SOURCE_NAME = "google_trends"

    def fetch(self, limit: int = 50) -> list[dict]:
        try:
            from pytrends.request import TrendReq
        except ImportError:
            self.logger.warning("pytrends not installed — skipping Google Trends")
            return []

        posts = []
        seen  = set()

        try:
            pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
            for region in REGIONS:
                try:
                    df = pt.trending_searches(pn=region)
                    for kw in df[0].tolist():
                        kw = str(kw).strip()
                        if kw and kw not in seen:
                            seen.add(kw)
                            post = self.make_post(
                                kw, "https://trends.google.com/", "google_trends", 1
                            )
                            if post:
                                posts.append(post)
                except Exception as e:
                    self.logger.warning(f"Google Trends region {region} failed: {e}")

        except Exception as e:
            self.logger.error(f"Google Trends failed: {e}")

        self.logger.info(f"Google Trends returned {len(posts)} posts")
        return posts[:limit]


def scrape_google_trends(limit: int = 50) -> list[dict]:
    return GoogleTrendsScraper().fetch(limit)