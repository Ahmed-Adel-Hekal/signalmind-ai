"""engine/scraping_sources/producthunt_scraper.py — Sprint 4

Sprint 4 Fix:
    الـ API القديمة /v1/posts تحتاج auth token ومش public.
    الحل: استخدام RSS feed الرسمي (مجاني وبدون auth).
"""
from scraping.base_scraper import BaseScraper


class ProductHuntScraper(BaseScraper):
    SOURCE_NAME = "producthunt"

    def fetch(self, limit: int = 50) -> list[dict]:
        entries = self.get_feed("https://www.producthunt.com/feed")
        posts   = []

        for entry in entries[:limit]:
            title = getattr(entry, "title", "").strip()
            url   = getattr(entry, "link",  "")
            # ProductHunt RSS بيحط عدد الـ votes في summary أحياناً
            summary = getattr(entry, "summary", "")
            score = 1
            if "upvote" in summary.lower():
                import re
                m = re.search(r"(\d+)\s*upvote", summary, re.IGNORECASE)
                if m:
                    score = int(m.group(1))

            post = self.make_post(title, url, "producthunt", score)
            if post:
                posts.append(post)

        self.logger.info(f"ProductHunt returned {len(posts)} posts")
        return posts


def scrape_producthunt(limit: int = 50) -> list[dict]:
    return ProductHuntScraper().fetch(limit)