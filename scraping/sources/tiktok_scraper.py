"""
engine/scraping_sources/tiktok_scraper.py
==========================================
Sprint 4 (extra): TikTok Trends scraper.
⚠️ ملف جديد.

مصدرين:
    1. TikTok Creative Center — trending hashtags (public API)
       https://ads.tiktok.com/business/creativecenter/hashtag/pc/en
       بتوفر trending hashtags بدون login

    2. RSS aggregators — video titles trending على TikTok
       مواقع بتتتبع TikTok trends وبتوفر RSS

الـ approach:
    - Creative Center API: JSON endpoint عام
    - Fallback: RSS feeds من trend trackers
    - مفيش selenium، مفيش login، مفيش ban
"""

import re
from scraping.base_scraper import BaseScraper

# TikTok Creative Center — trending hashtags endpoint
CREATIVE_CENTER_URL = (
    "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
    "?period=7&page=1&limit=50&country_code=US"
)

CREATIVE_CENTER_HEADERS = {
    "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":     "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
    "Accept":      "application/json",
}

# RSS feeds بتغطي TikTok trending content
TIKTOK_RSS_FEEDS = [
    ("https://www.socialmediatoday.com/rss.xml",           "tiktok_smt"),
    ("https://www.theverge.com/rss/index.xml",             "tiktok_verge"),
    ("https://techcrunch.com/feed/",                       "tiktok_tc"),
]

# Keywords لفلترة المقالات المتعلقة بـ TikTok
TIKTOK_KEYWORDS = [
    "tiktok", "viral", "trending", "short video",
    "reel", "creator", "for you", "fyp",
]


class TikTokScraper(BaseScraper):
    SOURCE_NAME = "tiktok"

    def _fetch_creative_center(self) -> list[dict]:
        """جلب trending hashtags من TikTok Creative Center API."""
        data = self.get_json(
            CREATIVE_CENTER_URL,
            headers=CREATIVE_CENTER_HEADERS,
        )
        if not data:
            return []

        posts = []
        hashtag_list = (
            data.get("data", {}).get("list", [])
            or data.get("data", [])
            or []
        )

        for item in hashtag_list:
            # اسم الـ hashtag
            tag = (
                item.get("hashtag_name")
                or item.get("name")
                or item.get("title", "")
            ).strip()

            if not tag:
                continue

            # عدد المشاهدات كـ score
            views = (
                item.get("video_views")
                or item.get("publish_cnt")
                or item.get("view_count", 0)
            )
            try:
                score = int(str(views).replace(",", "")) // 1_000_000
            except (ValueError, TypeError):
                score = 1

            post = self.make_post(
                title=f"#{tag} trending on TikTok",
                url=f"https://www.tiktok.com/tag/{tag}",
                source="tiktok_hashtag",
                score=max(score, 1),
            )
            if post:
                posts.append(post)

        self.logger.info(f"TikTok Creative Center: {len(posts)} hashtags")
        return posts

    def _fetch_trending_videos_rss(self) -> list[dict]:
        """جلب عناوين محتوى viral من RSS feeds."""
        posts = []
        seen  = set()

        for url, source_name in TIKTOK_RSS_FEEDS:
            entries = self.get_feed(url)
            for entry in entries[:20]:
                title   = getattr(entry, "title",   "").strip()
                link    = getattr(entry, "link",    "")
                summary = getattr(entry, "summary", "").lower()

                if not title or title in seen:
                    continue

                # فلتر المقالات المتعلقة بـ TikTok/viral فعلاً
                combined = (title + " " + summary).lower()
                if not any(kw in combined for kw in TIKTOK_KEYWORDS):
                    continue

                seen.add(title)
                post = self.make_post(title, link, source_name, 1)
                if post:
                    posts.append(post)

        self.logger.info(f"TikTok RSS feeds: {len(posts)} posts")
        return posts

    def fetch(self, limit: int = 100) -> list[dict]:
        posts = []

        # المصدر 1: Creative Center hashtags
        cc_posts = self._fetch_creative_center()
        posts.extend(cc_posts)

        # المصدر 2: RSS video titles
        rss_posts = self._fetch_trending_videos_rss()
        posts.extend(rss_posts)

        # لو Creative Center مش شغال — نعتمد على RSS بالكامل
        if not cc_posts:
            self.logger.warning(
                "TikTok Creative Center unavailable — using RSS only"
            )

        self.logger.info(f"TikTok total: {len(posts)} posts")
        return posts[:limit]


def scrape_tiktok(limit: int = 100) -> list[dict]:
    return TikTokScraper().fetch(limit)
