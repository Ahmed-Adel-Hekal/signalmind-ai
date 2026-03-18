"""
engine/scraping_sources/base_scraper.py
========================================
Sprint 4: Base class مشترك لكل الـ scrapers.
⚠️ ملف جديد.

يوفر:
    - requests.Session مع retry adapter
    - timeout موحد (10 ثانية)
    - headers موحدة (User-Agent)
    - get_json() و get_html() و get_feed() helpers
    - error logging موحد
"""

import time
import requests
try:
    import feedparser
except Exception:  # pragma: no cover - optional dependency fallback
    feedparser = None
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.logger import get_logger

DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5
USER_AGENT = "Mozilla/5.0 (AI-Trend-Engine/1.0)"


def _make_session(retries: int = DEFAULT_RETRIES,
                  backoff: float = DEFAULT_BACKOFF) -> requests.Session:
    """Session مع retry adapter تلقائي."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


class BaseScraper:
    """
    Base class لكل الـ scrapers.
    كل scraper يعمل subclass منه ويـoverride فقط _fetch().
    """

    SOURCE_NAME = "base"

    def __init__(self):
        self.session = _make_session()
        self.logger  = get_logger(self.__class__.__name__)

    def get_json(self, url: str, headers: dict = None,
                 params: dict = None, timeout: int = DEFAULT_TIMEOUT) -> dict | list | None:
        """GET request → JSON أو None لو فشل."""
        try:
            r = self.session.get(url, headers=headers,
                                 params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self.logger.error(f"[{self.SOURCE_NAME}] JSON fetch failed: {e} | url: {url}")
            return None

    def get_html(self, url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """GET request → HTML string أو '' لو فشل."""
        try:
            r = self.session.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            self.logger.error(f"[{self.SOURCE_NAME}] HTML fetch failed: {e} | url: {url}")
            return ""

    def get_feed(self, url: str) -> list:
        """RSS/Atom feed → list of entries."""
        try:
            if feedparser is None:
                self.logger.warning("feedparser not installed; skipping RSS fetch for %s", url)
                return []
            feed = feedparser.parse(url)
            return feed.entries
        except Exception as e:
            self.logger.error(f"[{self.SOURCE_NAME}] Feed fetch failed: {e} | url: {url}")
            return []

    @staticmethod
    def make_post(title: str, url: str, source: str, score: int = 1) -> dict | None:
        """بناء post dict موحد — يرجع None لو العنوان فاضي."""
        title = title.strip() if title else ""
        if not title:
            return None
        return {"title": title, "url": url or "", "source": source, "score": score}
