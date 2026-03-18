from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests

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
        self.cache_ttl_seconds = 24 * 60 * 60
        self.cache_path = Path("data/processed/trend_agent_cache.json")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

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
        topic: str = "",
        niche: str = "tech",
        markets: list[str] = None,
        limit_per_source: int = 100,
        force_refresh: bool = False,
    ) -> dict:
        """
        Runs scraping + deep search + 9-stage trend pipeline.
        Results are cached for 24h for the same input tuple.
        Falls back to DataLoader.load_trends() if scraping fails.
        Never raises -- always returns a dict.
        """
        try:
            cache_key = self._cache_key(topic, platforms, niche, markets or [], limit_per_source)
            if not force_refresh:
                cached = self._read_cached_result(cache_key)
                if cached is not None:
                    cached["cache"] = {"used": True, "ttl_hours": 24}
                    return cached

            posts = self._run_scrapers(platforms, limit_per_source, topic=topic)
            posts.extend(self._run_topic_probes(topic, limit=max(10, min(50, limit_per_source // 2))))
            posts.extend(self._run_deep_search(topic, niche, markets or []))

            if not posts:
                fallback = self.loader.load_trends(platform=None, niche=niche, limit=30)
                result = self._format_from_trends_fallback(fallback, topic=topic)
                result["cache"] = {"used": False, "ttl_hours": 24}
                self._write_cached_result(cache_key, result)
                return result

            ranked = self._run_trend_pipeline(posts)
            result = self._format_for_content_agent(ranked)
            result["cache"] = {"used": False, "ttl_hours": 24}
            self._write_cached_result(cache_key, result)
            return result
        except Exception as exc:
            logger.error("Trend analysis failed: %s", exc)
            fallback = self.loader.load_trends(platform=None, niche=niche, limit=30)
            return self._format_from_trends_fallback(fallback, topic=topic)

    def _cache_key(
        self,
        topic: str,
        platforms: list[str],
        niche: str,
        markets: list[str],
        limit_per_source: int,
    ) -> str:
        raw = {
            "topic": topic or "",
            "platforms": sorted(platforms or []),
            "niche": niche or "",
            "markets": sorted(markets or []),
            "limit_per_source": int(limit_per_source or 0),
        }
        return hashlib.sha256(json.dumps(raw, sort_keys=True).encode("utf-8")).hexdigest()

    def _read_cache_store(self) -> dict:
        if not self.cache_path.exists():
            return {}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _write_cache_store(self, store: dict):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_cached_result(self, cache_key: str) -> dict | None:
        store = self._read_cache_store()
        item = store.get(cache_key)
        if not isinstance(item, dict):
            return None
        ts = int(item.get("timestamp", 0))
        if int(time.time()) - ts > self.cache_ttl_seconds:
            return None
        result = item.get("result")
        return result if isinstance(result, dict) else None

    def _write_cached_result(self, cache_key: str, result: dict):
        store = self._read_cache_store()
        store[cache_key] = {"timestamp": int(time.time()), "result": result}
        self._write_cache_store(store)

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

    def _run_scrapers(self, platforms: list[str], limit: int, topic: str = "") -> list[dict]:
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

        return self._rank_posts_by_topic(posts, topic)

    def _topic_keywords(self, topic: str) -> list[str]:
        words = [w.strip().lower() for w in (topic or "").replace("/", " ").replace("-", " ").split()]
        words = [w for w in words if len(w) >= 3]
        return words[:8]

    def _post_topic_score(self, post: dict, keywords: list[str]) -> int:
        if not keywords:
            return 1
        title = str(post.get("title", "")).lower()
        source = str(post.get("source", "")).lower()
        text = f"{title} {source}"
        score = 0
        for kw in keywords:
            if kw in text:
                score += 1
        return score

    def _rank_posts_by_topic(self, posts: list[dict], topic: str) -> list[dict]:
        keywords = self._topic_keywords(topic)
        if not keywords:
            return posts
        ranked = sorted(posts, key=lambda p: (self._post_topic_score(p, keywords), p.get("score", 0)), reverse=True)
        # Keep all matched first, then some non-matched for diversity.
        matched = [p for p in ranked if self._post_topic_score(p, keywords) > 0]
        others = [p for p in ranked if self._post_topic_score(p, keywords) == 0][:80]
        return matched + others

    def _run_topic_probes(self, topic: str, limit: int = 20) -> list[dict]:
        """
        True topic-driven probes against queryable sources.
        Returns normalized post dicts: title, source, url, score.
        """
        if not (topic or "").strip():
            return []

        rows = []
        rows.extend(self._probe_reddit(topic, limit))
        rows.extend(self._probe_hackernews(topic, limit))
        rows.extend(self._probe_google_news(topic, limit))
        rows.extend(self._probe_github(topic, limit))
        return rows

    def _probe_reddit(self, topic: str, limit: int) -> list[dict]:
        try:
            url = "https://www.reddit.com/search.json"
            params = {"q": topic, "sort": "top", "t": "week", "limit": limit}
            headers = {"User-Agent": "AI-Content-Factory/1.0"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            posts = []
            for item in data.get("data", {}).get("children", []):
                payload = item.get("data", {})
                title = payload.get("title", "").strip()
                if not title:
                    continue
                posts.append(
                    {
                        "title": title,
                        "source": f"reddit_search/{topic}",
                        "url": payload.get("url", ""),
                        "score": int(payload.get("score", 1) or 1),
                    }
                )
            return posts
        except Exception as exc:
            logger.warning("Topic probe reddit failed: %s", exc)
            return []

    def _probe_hackernews(self, topic: str, limit: int) -> list[dict]:
        try:
            url = "https://hn.algolia.com/api/v1/search"
            params = {"query": topic, "tags": "story", "hitsPerPage": limit}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            posts = []
            for hit in data.get("hits", []):
                title = (hit.get("title") or "").strip()
                if not title:
                    continue
                posts.append(
                    {
                        "title": title,
                        "source": f"hackernews_search/{topic}",
                        "url": hit.get("url", "") or "",
                        "score": int(hit.get("points", 1) or 1),
                    }
                )
            return posts
        except Exception as exc:
            logger.warning("Topic probe hackernews failed: %s", exc)
            return []

    def _probe_google_news(self, topic: str, limit: int) -> list[dict]:
        # Parse RSS with simple XML parser to avoid external dependency.
        try:
            import xml.etree.ElementTree as et

            query = quote_plus(topic)
            url = (
                "https://news.google.com/rss/search"
                f"?q={query}&hl=en-US&gl=US&ceid=US:en"
            )
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            root = et.fromstring(response.content)
            posts = []
            for item in root.findall(".//item")[:limit]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if not title:
                    continue
                posts.append(
                    {
                        "title": title,
                        "source": f"google_news_search/{topic}",
                        "url": link,
                        "score": 1,
                    }
                )
            return posts
        except Exception as exc:
            logger.warning("Topic probe google news failed: %s", exc)
            return []

    def _probe_github(self, topic: str, limit: int) -> list[dict]:
        try:
            url = "https://api.github.com/search/repositories"
            params = {"q": topic, "sort": "stars", "order": "desc", "per_page": max(1, min(30, limit))}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            posts = []
            for item in data.get("items", []):
                full_name = (item.get("full_name") or "").strip()
                if not full_name:
                    continue
                desc = (item.get("description") or "").strip()
                title = f"{full_name} - {desc}" if desc else full_name
                posts.append(
                    {
                        "title": title,
                        "source": f"github_search/{topic}",
                        "url": item.get("html_url", ""),
                        "score": int(item.get("stargazers_count", 1) or 1),
                    }
                )
            return posts
        except Exception as exc:
            logger.warning("Topic probe github failed: %s", exc)
            return []

    def _run_deep_search(self, topic: str, niche: str, markets: list[str]) -> list[dict]:
        market_text = ", ".join(markets) if markets else "global"
        prompt = f"""
You are a trend analyst.
Focus on this topic: {topic or "general"}.
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

    def _format_from_trends_fallback(self, trends: list[dict], topic: str = "") -> dict:
        keywords = self._topic_keywords(topic)
        if keywords:
            filtered = []
            for trend in trends:
                text = f"{trend.get('topic', '')} {trend.get('marketing_angle', '')}".lower()
                if any(kw in text for kw in keywords):
                    filtered.append(trend)
            if filtered:
                trends = filtered

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
