import asyncio
import aiohttp
from scraping.base_scraper import BaseScraper

BASE_URL = "https://hacker-news.firebaseio.com/v0"
TIMEOUT = aiohttp.ClientTimeout(total=10)
CONCURRENT_LIMIT = 20


class HackerNewsScraper(BaseScraper):
    SOURCE_NAME = "hackernews"

    def fetch(self, limit: int = 100) -> list:
        try:
            return asyncio.run(self._scrape_async(limit))
        except Exception as e:
            self.logger.error(f"HackerNews failed: {e}")
            return []

    async def _scrape_async(self, limit: int) -> list:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            ids_data = await self._fetch_json(session, f"{BASE_URL}/topstories.json")
            if not ids_data:
                return []
            ids = ids_data[:limit]
            self.logger.info(f"Fetching {len(ids)} HackerNews stories concurrently")
            semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
            tasks = [self._fetch_item(session, semaphore, i) for i in ids]
            items = await asyncio.gather(*tasks)
            posts = []
            for item in items:
                if not item:
                    continue
                post = self.make_post(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    source="hackernews",
                    score=item.get("score", 0),
                )
                if post:
                    posts.append(post)
            self.logger.info(f"HackerNews returned {len(posts)} posts")
            return posts

    async def _fetch_json(self, session, url):
        try:
            async with session.get(url) as r:
                if r.status == 200:
                    return await r.json()
        except Exception:
            pass
        return None

    async def _fetch_item(self, session, semaphore, item_id):
        async with semaphore:
            return await self._fetch_json(session, f"{BASE_URL}/item/{item_id}.json")


def scrape_hackernews(limit: int = 100) -> list:
    return HackerNewsScraper().fetch(limit)
