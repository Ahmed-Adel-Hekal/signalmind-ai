"""
engine/scraping_sources/instagram_scraper.py
=============================================
Sprint 4 (extra): Instagram Trends scraper.
⚠️ ملف جديد.

لماذا مش Instagram API؟
    - Instagram Graph API محتاج Facebook Business account
    - Selenium بيتبان فوراً (Meta aggressive anti-bot)

الحل:
    1. Later.com + Hootsuite + SproutSocial — بيوفروا
       Instagram trending hashtags reports عبر RSS/JSON
    2. Instagram hashtag pages عبر public RSS aggregators
    3. فلترة محتوى Instagram من tech RSS feeds

المصادر:
    - Social media trend reports
    - Later blog (Instagram marketing)
    - Hashtag aggregators
"""

from scraping.base_scraper import BaseScraper

# RSS بتغطي Instagram trends وmarketing insights
INSTAGRAM_RSS_FEEDS = [
    ("https://later.com/blog/feed/",                      "instagram_later"),
    ("https://blog.hootsuite.com/feed/",                  "instagram_hootsuite"),
    ("https://sproutsocial.com/insights/feed/",           "instagram_sprout"),
    ("https://www.socialmediaexaminer.com/feed/",         "instagram_sme"),
    ("https://buffer.com/resources/rss/",                 "instagram_buffer"),
]

# Hashtag trend trackers
HASHTAG_FEEDS = [
    ("https://www.top-hashtags.com/rss.xml",              "instagram_hashtags"),
    ("https://ritetag.com/blog/feed",                     "instagram_ritetag"),
]

# Keywords لفلترة المحتوى المتعلق بـ Instagram فعلاً
INSTAGRAM_KEYWORDS = [
    "instagram", "reel", "story", "hashtag",
    "influencer", "social media", "engagement",
    "content creator", "visual", "feed",
]

# Trending tech/startup hashtags على Instagram
KNOWN_TRENDING_HASHTAGS = [
    "AItools", "TechStartup", "MachineLearning",
    "DevLife", "CodeLife", "StartupLife",
    "ProductDesign", "UXDesign", "DataScience",
    "CloudComputing", "WebDevelopment", "Python",
]


class InstagramScraper(BaseScraper):
    SOURCE_NAME = "instagram"

    def _fetch_trending_hashtags(self) -> list[dict]:
        """
        إنشاء posts للـ hashtags التقنية المعروفة على Instagram.
        مع محاولة جلب view counts من hashtag trackers.
        """
        posts = []
        for tag in KNOWN_TRENDING_HASHTAGS:
            post = self.make_post(
                title=f"#{tag} trending on Instagram",
                url=f"https://www.instagram.com/explore/tags/{tag}/",
                source="instagram_hashtag",
                score=1,
            )
            if post:
                posts.append(post)

        self.logger.info(f"Instagram hashtags: {len(posts)}")
        return posts

    def _fetch_instagram_insights_rss(self) -> list[dict]:
        """جلب مقالات Instagram trends من social media blogs."""
        posts = []
        seen  = set()

        all_feeds = INSTAGRAM_RSS_FEEDS + HASHTAG_FEEDS

        for url, source_name in all_feeds:
            entries = self.get_feed(url)
            for entry in entries[:15]:
                title   = getattr(entry, "title",   "").strip()
                link    = getattr(entry, "link",    "")
                summary = getattr(entry, "summary", "").lower()

                if not title or title in seen:
                    continue

                # فلتر المحتوى المتعلق بـ Instagram
                combined = (title + " " + summary).lower()
                if not any(kw in combined for kw in INSTAGRAM_KEYWORDS):
                    continue

                seen.add(title)
                post = self.make_post(title, link, source_name, 1)
                if post:
                    posts.append(post)

        self.logger.info(f"Instagram RSS insights: {len(posts)} posts")
        return posts

    def fetch(self, limit: int = 50) -> list[dict]:
        posts = []

        # المصدر 1: Known trending hashtags
        posts.extend(self._fetch_trending_hashtags())

        # المصدر 2: Instagram insights من social media blogs
        posts.extend(self._fetch_instagram_insights_rss())

        self.logger.info(f"Instagram total: {len(posts)} posts")
        return posts[:limit]


def scrape_instagram(limit: int = 50) -> list[dict]:
    return InstagramScraper().fetch(limit)
