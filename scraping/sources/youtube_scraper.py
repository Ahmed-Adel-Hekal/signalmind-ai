"""engine/scraping_sources/youtube_scraper.py — Sprint 4"""
import re
from urllib.parse import urlparse

from scraping.base_scraper import BaseScraper

# channels تقنية معروفة
CHANNELS = {
    "UC_x5XG1OV2P6uZZ5FSM9Ttw": "Google Developers",
    "UCnUYZLuoy1rq1aVMwx4aTzw":  "Google Cloud",
    "UCVHFbw7woebKtX3KiNIOJiA":  "Fireship",
    "UCsBjURrPoezykLs9EqgamOA":  "Fireship (alt)",
}


class YouTubeScraper(BaseScraper):
    SOURCE_NAME = "youtube"

    def fetch_from_url(self, channel_url: str) -> list[dict]:
        """
        Extracts channel ID from a YouTube URL then fetches RSS.
        Supports: youtube.com/channel/ID, youtube.com/@handle
        Returns same format as fetch()
        """
        if not channel_url:
            return []

        channel_id = ""
        parsed = urlparse(channel_url)
        path = parsed.path or ""

        if "/channel/" in path:
            channel_id = path.split("/channel/", 1)[1].split("/", 1)[0].strip()
        elif "/@" in path:
            handle = path.split("/@", 1)[1].split("/", 1)[0].strip()
            html = self.get_html(f"https://www.youtube.com/@{handle}")
            m = re.search(r'"channelId":"(UC[^"]+)"', html)
            if m:
                channel_id = m.group(1)

        if not channel_id:
            self.logger.warning("Could not resolve YouTube channel from URL: %s", channel_url)
            return []

        entries = self.get_feed(
            f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        )
        posts = []
        for entry in entries:
            title = getattr(entry, "title", "").strip()
            url = getattr(entry, "link", "")
            post = self.make_post(title, url, "youtube", 1)
            if post:
                posts.append(post)

        return posts

    def fetch(self, limit: int = 50) -> list[dict]:
        posts = []
        seen  = set()
        per_ch = max(limit // len(CHANNELS), 5)

        for channel_id in CHANNELS:
            entries = self.get_feed(
                f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            )
            for entry in entries[:per_ch]:
                title = getattr(entry, "title", "").strip()
                url   = getattr(entry, "link",  "")
                if title and title not in seen:
                    seen.add(title)
                    post = self.make_post(title, url, "youtube", 1)
                    if post:
                        posts.append(post)
            if len(posts) >= limit:
                break

        self.logger.info(f"YouTube returned {len(posts)} posts")
        return posts[:limit]


def scrape_youtube(limit: int = 50) -> list[dict]:
    return YouTubeScraper().fetch(limit)