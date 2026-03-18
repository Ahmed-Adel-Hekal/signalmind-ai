import time

from dotenv import load_dotenv

from agents.competitor_agent import CompetitorAgent
from agents.content_agent import run_content_pipeline
from agents.trend_agent import TrendAgent
from core.data_loader import DataLoader
from core.logger import get_logger
from scraping.competitor_scraper import CompetitorScraper

load_dotenv()

logger = get_logger("Orchestrator")


class Orchestrator:
    def run(
        self,
        topic: str,
        platforms: list[str],
        content_type: str,
        language: str,
        brand_color: list[str],
        brand_img: str | None = None,
        number_idea: int = 3,
        competitor_urls: list[str] = None,
        niche: str = "tech",
        output_dir: str = "output_posts",
        image_url: str = "",
    ) -> dict:
        """
        Full pipeline:

        Step 1 -- Competitor Intelligence
          If competitor_urls provided:
            CompetitorScraper().scrape(url) for each url
            flatten results into one list
          Else:
            DataLoader().load_competitor_posts(platform=platforms[0])
          CompetitorAgent().analyze(posts) -> comp_insight

        Step 2 -- Trend Intelligence
          TrendAgent().analyze(
            platforms=platforms,
            niche=niche,
          ) -> trend_insight

        Step 3 -- Content Generation
          run_content_pipeline(...) -> result

        Return result dict from run_content_pipeline.
        Log each step with timing.
        """
        total_start = time.perf_counter()

        step1 = time.perf_counter()
        competitor_posts = []
        if competitor_urls:
            scraper = CompetitorScraper()
            for url in competitor_urls:
                competitor_posts.extend(scraper.scrape(url))
        else:
            selected_platform = platforms[0] if platforms else None
            if selected_platform:
                selected_platform = selected_platform.replace("/X", "").replace("/x", "")
            competitor_posts = DataLoader().load_competitor_posts(platform=selected_platform)
        comp_insight = CompetitorAgent().analyze(competitor_posts)
        logger.info("Step 1 complete in %.2fs", time.perf_counter() - step1)

        step2 = time.perf_counter()
        trend_insight = TrendAgent().analyze(platforms=platforms, niche=niche)
        logger.info("Step 2 complete in %.2fs", time.perf_counter() - step2)

        step3 = time.perf_counter()
        result = run_content_pipeline(
            topic,
            platforms,
            content_type,
            language,
            brand_color,
            brand_img,
            number_idea,
            comp_insight,
            trend_insight,
            output_dir,
            image_url,
        )
        logger.info("Step 3 complete in %.2fs", time.perf_counter() - step3)
        logger.info("Pipeline complete in %.2fs", time.perf_counter() - total_start)

        return result
