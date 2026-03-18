"""engine/scraping_sources/github_trending_scraper.py — Sprint 4"""
from bs4 import BeautifulSoup
from scraping.base_scraper import BaseScraper

TIMEFRAMES = ["daily", "weekly"]


class GitHubTrendingScraper(BaseScraper):
    SOURCE_NAME = "github_trending"

    def fetch(self, limit: int = 50) -> list[dict]:
        posts = []
        seen = set()

        for tf in TIMEFRAMES:
            html = self.get_html(
                f"https://github.com/trending?since={tf}&spoken_language_code=en"
            )
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            for repo in soup.select("article.Box-row"):
                # اسم الـ repo
                h2 = repo.select_one("h2 a")
                if not h2:
                    continue
                name = " ".join(h2.text.split())   # ينظف whitespace
                href = h2.get("href", "")

                # عدد النجوم
                stars_el = repo.select_one("span.d-inline-block.float-sm-right")
                stars = 0
                if stars_el:
                    try:
                        stars = int(stars_el.text.strip().replace(",", ""))
                    except ValueError:
                        pass

                # وصف مختصر
                desc_el = repo.select_one("p.col-9")
                desc = desc_el.text.strip() if desc_el else ""

                title = f"{name} — {desc}" if desc else name
                url   = f"https://github.com{href}"

                if title not in seen:
                    seen.add(title)
                    post = self.make_post(title, url, "github_trending", stars)
                    if post:
                        posts.append(post)

            if len(posts) >= limit:
                break

        self.logger.info(f"GitHub Trending returned {len(posts)} posts")
        return posts[:limit]


def scrape_github_trending(limit: int = 50) -> list[dict]:
    return GitHubTrendingScraper().fetch(limit)


def scrape_github(limit: int = 50) -> list[dict]:
    return scrape_github_trending(limit)
