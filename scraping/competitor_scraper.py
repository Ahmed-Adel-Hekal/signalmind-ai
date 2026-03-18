import re
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from core.logger import get_logger

logger = get_logger("CompetitorScraper")


class CompetitorScraper:
    def scrape(self, url: str) -> list[dict]:
        """
        Main entry. Detects platform from URL and routes accordingly.
        Always returns [] on failure -- never raises.
        Returns list of {"caption", "url", "source", "platform"}
        """
        try:
            if not url:
                return []

            platform = self._detect_platform(url)
            if platform == "youtube":
                return self._scrape_youtube(url)

            rows = self._scrape_generic(url)
            for row in rows:
                row["platform"] = platform
            return rows
        except Exception as exc:
            logger.error("Competitor scrape failed for %s: %s", url, exc)
            return []

    def _scrape_youtube(self, url: str) -> list[dict]:
        """
        Extract channel ID from URL (handles /channel/ID and /@handle).
        Fetch RSS: youtube.com/feeds/videos.xml?channel_id={ID}
        Parse entries -- return titles as captions.
        """
        try:
            channel_id = ""
            parsed = urlparse(url)
            path = parsed.path or ""

            if "/channel/" in path:
                channel_id = path.split("/channel/", 1)[1].split("/", 1)[0].strip()
            elif "/@" in path:
                handle = path.split("/@", 1)[1].split("/", 1)[0].strip()
                html = requests.get(f"https://www.youtube.com/@{handle}", timeout=10).text
                match = re.search(r'"channelId":"(UC[^"]+)"', html)
                if match:
                    channel_id = match.group(1)

            if not channel_id:
                return []

            feed = feedparser.parse(
                f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            )
            posts = []
            for entry in feed.entries[:10]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "")
                if not title:
                    continue
                posts.append(
                    {
                        "caption": title,
                        "url": link,
                        "source": "youtube_rss",
                        "platform": "youtube",
                    }
                )
            return posts
        except Exception as exc:
            logger.warning("YouTube competitor scrape failed: %s", exc)
            return []

    def _scrape_generic(self, url: str) -> list[dict]:
        """
        requests.get the page.
        BeautifulSoup: extract <p> tags and <meta> description.
        Clean and return as captions.
        Max 10 items. Timeout 10s.
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            posts = []
            desc = soup.find("meta", attrs={"name": "description"})
            if desc and desc.get("content"):
                text = " ".join(desc["content"].split())
                if len(text) >= 12:
                    posts.append(
                        {
                            "caption": text,
                            "url": url,
                            "source": "meta_description",
                            "platform": "generic",
                        }
                    )

            for paragraph in soup.find_all("p"):
                text = " ".join(paragraph.get_text(" ", strip=True).split())
                if len(text) < 20:
                    continue
                posts.append(
                    {
                        "caption": text,
                        "url": url,
                        "source": "html_paragraph",
                        "platform": "generic",
                    }
                )
                if len(posts) >= 10:
                    break

            return posts[:10]
        except Exception as exc:
            logger.warning("Generic competitor scrape failed: %s", exc)
            return []

    def _detect_platform(self, url: str) -> str:
        """Returns: youtube | instagram | tiktok | linkedin | twitter | generic"""
        lowered = (url or "").lower()
        if "youtube.com" in lowered or "youtu.be" in lowered:
            return "youtube"
        if "instagram.com" in lowered:
            return "instagram"
        if "tiktok.com" in lowered:
            return "tiktok"
        if "linkedin.com" in lowered:
            return "linkedin"
        if "twitter.com" in lowered or "x.com" in lowered:
            return "twitter"
        return "generic"
