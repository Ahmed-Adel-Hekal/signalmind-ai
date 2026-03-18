import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from core.gemini_client import Agent
from media.video_generator import parse_llm_json, VideoGenerator
from media.static_post import StaticPostGenerator

load_dotenv()


@dataclass
class AgentConfig:
    video_content: bool = False
    images: bool = True
    brand_color: list[str] = field(default_factory=lambda: ["#3B82F6"])
    brand_img: str | None = None
    target_platform: list[str] = field(default_factory=lambda: ["Instagram"])
    model: str = "gemini-2.5-flash"
    language: str = "English"
    number_idea: int = 3


class ContentAgent(Agent):
    def __init__(self, config: AgentConfig):
        self.config = config
        super().__init__(model=config.model)

    def generate(
        self,
        topic: str,
        comp_insight: str | None = None,
        trend_insight: str | None = None,
    ) -> str:
        prompt = self._build_prompt(topic, comp_insight, trend_insight)
        return self.ask(prompt, max_tokens=4096)

    def _build_prompt(
        self,
        topic: str,
        comp_insight: str | None = None,
        trend_insight: str | None = None,
    ) -> str:
        base_context = [
            f"Topic: {topic}",
            f"Language: {self.config.language}",
            f"Platforms: {', '.join(self.config.target_platform)}",
            f"Brand colors: {self.config.brand_color}",
            f"Number of ideas: {self.config.number_idea}",
        ]

        if comp_insight:
            base_context.append(f"Competitor insights: {comp_insight}")
        if trend_insight:
            base_context.append(f"Trend insights: {trend_insight}")

        if self.config.video_content:
            schema = """
Return ONLY valid JSON:
{
  "ideas": [
    {
      "hook": {"text": "...", "duration_seconds": 3},
      "script": [
        {"scene": 1, "visuals": "...", "voiceover": "...", "duration_seconds": 5}
      ],
      "caption": "...",
      "hashtags": ["tag1", "tag2"],
      "cta": {"text": "...", "placement": "end"},
      "estimated_duration_seconds": 30,
      "visual_direction": {"pacing": "fast", "transitions": "cut", "color_usage": "clean"}
    }
  ]
}
"""
        else:
            schema = """
Return ONLY valid JSON:
{
  "ideas": [
    {
      "hook": "...",
      "post_copy": "...",
      "hashtags": ["tag1", "tag2"],
      "image_description": "...",
      "visual_direction": "..."
    }
  ]
}
"""

        return "\n".join(base_context) + "\n\n" + schema


def run_content_pipeline(
    topic:            str,
    platforms:        list[str],
    content_type:     str,
    language:         str,
    brand_color:      list[str],
    brand_img:        str | None,
    number_idea:      int,
    comp_insight:     dict | None,
    trend_insight:    dict | None,
    output_dir:       str = "output_posts",
    image_url:        str = "",
) -> dict:
    """
    Full end-to-end content generation.
    Returns:
    {
      "type": "static" | "video",
      "ideas": [...],
      "results": [...],
      "raw_json": {...}
    }
    """
    try:
        platform_literals = [p for p in platforms if p in ["X", "Facebook", "Instagram", "LinkedIn", "TikTok"]]
        config = AgentConfig(
            video_content=(content_type == "video"),
            images=True,
            brand_color=brand_color,
            brand_img=brand_img,
            target_platform=platform_literals,
            model="gemini-2.5-flash",
            language=language,
            number_idea=number_idea,
        )

        comp_str = str(comp_insight) if comp_insight else None
        trend_str = str(trend_insight) if trend_insight else None

        agent = ContentAgent(config=config)
        raw = agent.generate(topic, comp_str, trend_str)
        parsed = parse_llm_json(raw)

        if not isinstance(parsed, dict):
            parsed = {"ideas": []}

        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.join(base_dir, "..", output_dir)

        if content_type == "video":
            gen = VideoGenerator(
                api_key=os.environ.get("AIML_API_KEY", ""),
                image_url=image_url,
                language=language,
                brand_colors=brand_color,
                aspect_ratio="9:16",
                output_dir=out_dir,
            )
        else:
            gen = StaticPostGenerator(
                GEMINI_API_KEY=os.environ.get("GEMINI_API_KEY", ""),
                brand_colors=brand_color,
                output_dir=out_dir,
                aspect_ratio="4:5",
            )

        results = gen.generate_all(parsed)

        return {
            "type": content_type,
            "ideas": parsed.get("ideas", []),
            "results": results,
            "raw_json": parsed,
        }
    except Exception as exc:
        return {
            "type": content_type,
            "ideas": [],
            "results": [],
            "raw_json": {"ideas": []},
            "error": str(exc),
        }
