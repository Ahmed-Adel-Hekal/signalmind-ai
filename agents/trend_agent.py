from concurrent.futures import ThreadPoolExecutor, as_completed

from core.data_loader import DataLoader
from core.gemini_client import Agent
from core.logger import get_logger
from media.video_generator import parse_llm_json
from scraping.sources.devto_scraper import scrape_devto
from scraping.sources.github_scraper import scrape_github, scrape_github_trending
from scraping.sources.google_news_scraper import scrape_google_news
from scraping.sources.google_trends_scraper import scrape_google_trends
from scraping.sources.hackernews_scraper import scrape_hackernews
from scraping.sources.instagram_scraper import scrape_instagram
from scraping.sources.linkedin_scraper import scrape_linkedin
from scraping.sources.medium_scraper import scrape_medium
from scraping.sources.producthunt_scraper import scrape_producthunt
from scraping.sources.reddit_scraper import scrape_reddit
from scraping.sources.stackoverflow_scraper import scrape_stackoverflow
from scraping.sources.tiktok_scraper import scrape_tiktok
from scraping.sources.twitter_scraper import scrape_twitter
from scraping.sources.youtube_scraper import scrape_youtube
from trend_engine.deduplicator import deduplicate_posts
from trend_engine.keyword_extractor import extract_keywords
from trend_engine.novelty_detector import detect_novelty
from trend_engine.topic_clusterer import cluster_topics
from trend_engine.trend_classifier import classify_trends
from trend_engine.trend_forecaster import TrendForecaster
from trend_engine.trend_ranker import TrendRanker
from trend_engine.trend_scorer import score_trends
from trend_engine.trend_time_analyzer import TrendTimeAnalyzer
from trend_engine.trend_velocity import calculate_velocity

logger = get_logger("TrendAgent")


class TrendAgent:
    def __init__(self):
        self.loader = DataLoader()
        self.deep_search_agent = Agent(model="gemini-2.5-flash")
        self.forecaster = TrendForecaster()
        self.ranker = TrendRanker()
        self.time_analyzer = TrendTimeAnalyzer()

        self.scrapers = {
            "reddit": scrape_reddit,
            "hackernews": scrape_hackernews,
            "devto": scrape_devto,
            "medium": scrape_medium,
            "github": scrape_github,
            "github_trending": scrape_github_trending,
            "stackoverflow": scrape_stackoverflow,
            "youtube": scrape_youtube,
            "producthunt": scrape_producthunt,
            "google_news": scrape_google_news,
            "google_trends": scrape_google_trends,
            "twitter": scrape_twitter,
            "linkedin": scrape_linkedin,
            "tiktok": scrape_tiktok,
            "instagram": scrape_instagram,
        }

    def analyze(
        self,
        platforms: list[str],
        niche: str = "tech",
        markets: list[str] = None,
        limit_per_source: int = 100,
    ) -> dict:
        """
        Runs scraping + deep search + 9-stage trend pipeline.
        Falls back to DataLoader.load_trends() if scraping fails.
        Never raises -- always returns a dict.
        """
        try:
            posts = self._run_scrapers(platforms, limit_per_source)
            posts.extend(self._run_deep_search(niche, markets or []))

            if not posts:
                fallback = self.loader.load_trends(platform=None, niche=niche, limit=30)
                return self._format_from_trends_fallback(fallback)

            ranked = self._run_trend_pipeline(posts)
            return self._format_for_content_agent(ranked)
        except Exception as exc:
            logger.error("Trend analysis failed: %s", exc)
            fallback = self.loader.load_trends(platform=None, niche=niche, limit=30)
            return self._format_from_trends_fallback(fallback)

    def _normalize_platform(self, value: str) -> str:
        lowered = (value or "").strip().lower()
        aliases = {
            "twitter/x": "twitter",
            "x": "twitter",
            "twitter": "twitter",
            "yt": "youtube",
            "youtube": "youtube",
            "insta": "instagram",
            "instagram": "instagram",
            "tiktok": "tiktok",
            "linkedin": "linkedin",
            "facebook": "",
        }
        return aliases.get(lowered, lowered)

    def _run_scrapers(self, platforms: list[str], limit: int) -> list[dict]:
        """Run selected scrapers in parallel using ThreadPoolExecutor."""
        selected = [self._normalize_platform(p) for p in (platforms or [])]
        selected = [p for p in selected if p]

        if not selected:
            funcs = list({k: v for k, v in self.scrapers.items() if k != "github_trending"}.values())
        else:
            funcs = [self.scrapers[p] for p in selected if p in self.scrapers]
            if "github" in selected and scrape_github_trending not in funcs:
                funcs.append(scrape_github_trending)

        posts: list[dict] = []
        if not funcs:
            return posts

        with ThreadPoolExecutor(max_workers=min(14, len(funcs))) as executor:
            futures = {executor.submit(fn, limit): fn.__name__ for fn in funcs}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    rows = future.result(timeout=40)
                    if rows:
                        posts.extend(rows)
                    logger.info("%s -> %s posts", name, len(rows or []))
                except Exception as exc:
                    logger.warning("scraper %s failed: %s", name, exc)

        return posts

    def _run_deep_search(self, niche: str, markets: list[str]) -> list[dict]:
        market_text = ", ".join(markets) if markets else "global"
        prompt = f"""
You are a trend analyst.
Find 8 emerging social-media trends for niche: {niche} in markets: {market_text}.
Return ONLY JSON: {{"trends": ["trend 1", "trend 2"]}}
""".strip()
        raw = self.deep_search_agent.ask(prompt, max_tokens=1024)
        if not raw:
            return []

        trends = []
        try:
            data = parse_llm_json(raw)
            for item in data.get("trends", [])[:8]:
                title = str(item).strip()
                if title:
                    trends.append(
                        {"title": title, "source": "deep_search", "url": "", "score": 1}
                    )
        except Exception:
            return []
        return trends

    def _run_trend_pipeline(self, posts: list[dict]) -> dict:
        """Run all 9 stages. Return TrendRanker output dict."""
        rows = deduplicate_posts(posts)

        if not rows:
            return {"exploding": [], "growing": [], "future": [], "stable": []}

        n_clusters = max(2, min(10, len(rows) // 8 or 2))
        rows = cluster_topics(rows, n_clusters=n_clusters)
        rows = calculate_velocity(rows)
        rows = detect_novelty(rows)
        rows = self.time_analyzer.enrich(rows)
        rows = score_trends(rows)
        rows = classify_trends(rows)
        rows = self.forecaster.forecast(rows)
        ranked = self.ranker.rank(rows)
        ranked["keywords"] = extract_keywords(rows, top_k=12)
        return ranked

    def _format_for_content_agent(self, ranked: dict) -> dict:
        """Convert ranked dict to ContentAgent-ready trend_insight dict."""
        all_rows = (
            ranked.get("exploding", [])
            + ranked.get("growing", [])
            + ranked.get("future", [])
            + ranked.get("stable", [])
        )

        top = []
        for row in all_rows[:12]:
            state = row.get("trend_state", "stable")
            strength = "high" if state == "exploding" else "medium" if state == "growing" else "low"
            top.append(
                {
                    "topic": row.get("title", ""),
                    "trend_strength": strength,
                    "content_format": "short" if row.get("source") in {"youtube", "tiktok", "instagram"} else "post",
                    "marketing_angle": f"Leverage {row.get('source', 'social')} momentum",
                    "hook_style": "question" if len(row.get("title", "")) % 2 else "shocking statistic",
                    "forecast": row.get("forecast", "stable"),
                }
            )

        return {
            "top_trends": top,
            "keywords": ranked.get("keywords", []),
            "raw_ranked": ranked,
        }

    def _format_from_trends_fallback(self, trends: list[dict]) -> dict:
        top = []
        for trend in trends:
            top.append(
                {
                    "topic": trend.get("topic", ""),
                    "trend_strength": trend.get("trend_strength", "medium"),
                    "content_format": trend.get("content_format", "post"),
                    "marketing_angle": trend.get("marketing_angle", ""),
                    "hook_style": trend.get("hook_style", "question"),
                    "forecast": "future_trend" if trend.get("score", 0) >= 80 else "stable",
                }
            )

        raw_ranked = {
            "exploding": [],
            "growing": [],
            "future": [],
            "stable": [],
        }
        for trend in trends:
            state = "exploding" if trend.get("trend_strength") == "high" else "growing" if trend.get("trend_strength") == "medium" else "stable"
            raw_ranked[state].append(
                {
                    "title": trend.get("topic", ""),
                    "source": trend.get("source", "data_loader"),
                    "trend_score": trend.get("score", 0),
                    "trend_state": state,
                    "forecast": "future_trend" if trend.get("score", 0) >= 80 else "stable",
                }
            )

        return {
            "top_trends": top[:12],
            "keywords": [trend.get("topic", "").split()[0] for trend in trends[:8] if trend.get("topic")],
            "raw_ranked": raw_ranked,
        }
