"""
engine/scraping_sources/twitter_scraper.py
==========================================
Sprint 4: Twitter scraper عبر Nitter RSS.
⚠️ ملف جديد.

لماذا Nitter؟
    - Twitter API v2 Basic = $100/شهر
    - Nitter = frontend مفتوح المصدر يقرأ Twitter بدون API
    - بيوفر RSS feeds مجانية لـ hashtags وaccounts
    - لو Nitter instance واحد مش شغال، بنجرب تاني

الـ hashtags المستهدفة:
    تقنية + ستارتاب + AI + dev
"""

from scraping.base_scraper import BaseScraper

# قائمة Nitter instances العامة — لو واحد مش شغال بنجرب التاني
NITTER_INSTANCES = [
    "nitter.net",
    "nitter.privacydev.net",
    "nitter.poast.org",
]

HASHTAGS = [
    "AItools", "MachineLearning", "LLM",
    "DevOps", "WebDev", "Startup",
    "OpenSource", "SoftwareEngineering",
]


class TwitterScraper(BaseScraper):
    SOURCE_NAME = "twitter"

    def _fetch_hashtag(self, hashtag: str, instance: str) -> list[dict]:
        """جلب tweets لـ hashtag معين من Nitter instance."""
        url     = f"https://{instance}/search/rss?q=%23{hashtag}&f=tweets"
        entries = self.get_feed(url)
        posts   = []

        for entry in entries[:15]:
            title = getattr(entry, "title", "").strip()
            link  = getattr(entry, "link",  "")

            # تنظيف الـ title من الـ RT وزيادة
            if title.startswith("RT "):
                title = title[3:].strip()
            if len(title) < 10:
                continue

            # إضافة الـ hashtag للـ source
            post = self.make_post(
                title=title,
                url=link,
                source=f"twitter/#{hashtag}",
                score=1,
            )
            if post:
                posts.append(post)

        return posts

    def fetch(self, limit: int = 100) -> list[dict]:
        posts = []
        seen  = set()

        for hashtag in HASHTAGS:
            fetched = False
            for instance in NITTER_INSTANCES:
                try:
                    new_posts = self._fetch_hashtag(hashtag, instance)
                    if new_posts:
                        for p in new_posts:
                            if p["title"] not in seen:
                                seen.add(p["title"])
                                posts.append(p)
                        fetched = True
                        break   # instance شغال — توقف
                except Exception as e:
                    self.logger.warning(
                        f"Nitter {instance} failed for #{hashtag}: {e}"
                    )

            if not fetched:
                self.logger.warning(f"All Nitter instances failed for #{hashtag}")

            if len(posts) >= limit:
                break

        self.logger.info(f"Twitter/Nitter returned {len(posts)} posts")
        return posts[:limit]


def scrape_twitter(limit: int = 100) -> list[dict]:
    return TwitterScraper().fetch(limit)
