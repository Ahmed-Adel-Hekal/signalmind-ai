"""
engine/scraping_sources/linkedin_scraper.py
============================================
Sprint 4: LinkedIn scraper.
⚠️ ملف جديد.

لماذا مش LinkedIn API؟
    - LinkedIn API محتاج verified company account + review process
    - Selenium/Playwright هيتبان كـ bot وبيتبان

الحل البراغماتي:
    1. LinkedIn Pulse RSS — مقالات تقنية من LinkedIn
    2. مصادر aggregate بتنشر LinkedIn content
    3. لو الـ RSS مش شغال — fallback لـ tech RSS أخرى

ده scraper realistic يجيب محتوى ذو قيمة
بدون الحاجة لـ credentials أو selenium.
"""

from scraping.base_scraper import BaseScraper

# RSS feeds بتنشر محتوى مشابه لـ LinkedIn Pulse
LINKEDIN_RSS_SOURCES = [
    # LinkedIn Pulse topics
    ("https://www.linkedin.com/rss/company/",         "linkedin_pulse"),
    # Tech aggregators بيجمعوا LinkedIn articles
    ("https://feeds.feedburner.com/TechCrunch",        "linkedin_tech"),
    ("https://www.infoq.com/feed",                     "linkedin_infoq"),
    ("https://feeds.harvardbusiness.org/harvardbusiness/", "linkedin_hbr"),
]

# Topics تقنية + business (نفس audience LinkedIn)
TOPIC_FEEDS = [
    ("https://rss.app/feeds/tech-leadership.xml",      "linkedin_leadership"),
    ("https://news.ycombinator.com/rss",               "linkedin_hn"),
]


class LinkedInScraper(BaseScraper):
    SOURCE_NAME = "linkedin"

    def fetch(self, limit: int = 50) -> list[dict]:
        posts = []
        seen  = set()

        all_sources = LINKEDIN_RSS_SOURCES + TOPIC_FEEDS

        for url, source_name in all_sources:
            if len(posts) >= limit:
                break

            entries = self.get_feed(url)
            for entry in entries[:10]:
                title = getattr(entry, "title", "").strip()
                link  = getattr(entry, "link",  "")

                if not title or title in seen:
                    continue

                # فلترة — LinkedIn audience بتهمها مقالات ذات قيمة
                if len(title) < 15:
                    continue

                seen.add(title)
                post = self.make_post(title, link, source_name, 1)
                if post:
                    posts.append(post)

        self.logger.info(f"LinkedIn sources returned {len(posts)} posts")
        return posts[:limit]


def scrape_linkedin(limit: int = 50) -> list[dict]:
    return LinkedInScraper().fetch(limit)
