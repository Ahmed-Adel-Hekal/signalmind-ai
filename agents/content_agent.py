import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency fallback
    def load_dotenv(*_args, **_kwargs):
        return False

from core.gemini_client import Agent
from media.video_generator import parse_llm_json

try:
    from media.video_generator import VideoGenerator
except Exception:  # pragma: no cover - optional dependency fallback
    VideoGenerator = None

try:
    from media.static_post import StaticPostGenerator
except Exception:  # pragma: no cover - optional dependency fallback
    StaticPostGenerator = None

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


def _build_fallback_payload(topic: str, content_type: str, number_idea: int) -> dict:
    idea_count = max(1, int(number_idea or 1))
    ideas = []
    for idx in range(idea_count):
        i = idx + 1
        if content_type == "video":
            ideas.append(
                {
                    "hook": {"text": f"{topic}: 3 things people miss (Idea {i})", "duration_seconds": 3},
                    "script": [
                        {"scene": 1, "visuals": f"Problem context for {topic}", "voiceover": f"Most people miss this about {topic}.", "duration_seconds": 4},
                        {"scene": 2, "visuals": "Actionable steps with text overlays", "voiceover": "Here is the simple framework to fix it.", "duration_seconds": 5},
                        {"scene": 3, "visuals": "CTA with branded visual", "voiceover": "Follow for more practical playbooks.", "duration_seconds": 3},
                    ],
                    "caption": f"Quick breakdown for {topic}. Save this for later.",
                    "hashtags": ["#marketing", "#content", "#ai"],
                    "cta": {"text": "Follow for more", "placement": "end"},
                    "estimated_duration_seconds": 12,
                    "visual_direction": {"pacing": "fast", "transitions": "cut", "color_usage": "clean"},
                }
            )
        else:
            ideas.append(
                {
                    "hook": f"Stop guessing your {topic} strategy (Idea {i})",
                    "post_copy": (
                        f"If your {topic} content feels random, use this sequence: "
                        "1) strong hook, 2) one insight, 3) one action. "
                        "Consistency beats complexity."
                    ),
                    "hashtags": ["marketing", "content", "socialmedia"],
                    "image_description": f"Modern social media graphic concept about {topic}",
                    "visual_direction": "minimal, high-contrast, brand-accented",
                }
            )
    return {"ideas": ideas}


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
        mapped_platforms = []
        for p in platforms:
            if p in ("Twitter/X", "Twitter", "X"):
                mapped_platforms.append("X")
            else:
                mapped_platforms.append(p)
        platform_literals = [p for p in mapped_platforms if p in ["X", "Facebook", "Instagram", "LinkedIn", "TikTok"]]
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
        try:
            parsed = parse_llm_json(raw) if raw else _build_fallback_payload(topic, content_type, number_idea)
            if not isinstance(parsed, dict):
                parsed = _build_fallback_payload(topic, content_type, number_idea)
        except Exception:
            parsed = _build_fallback_payload(topic, content_type, number_idea)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.join(base_dir, "..", output_dir)
        results = []
        warnings = []

        if content_type == "video":
            api_key = os.environ.get("AIML_API_KEY", "")
            if VideoGenerator is None or not api_key:
                warnings.append("Video generation dependency/API key unavailable; returned idea prompts only.")
                results = [
                    {"idea_index": i, "status": "mock_only", "error": "Video generation unavailable in current environment"}
                    for i, _ in enumerate(parsed.get("ideas", []))
                ]
            else:
                gen = VideoGenerator(
                    api_key=api_key,
                    image_url=image_url,
                    language=language,
                    brand_colors=brand_color,
                    aspect_ratio="9:16",
                    output_dir=out_dir,
                )
                results = gen.generate_all(parsed)
        else:
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if StaticPostGenerator is None or not api_key:
                warnings.append("Static image generation dependency/API key unavailable; returned post ideas only.")
                results = [
                    {"idea_index": i, "status": "mock_only", "error": "Image generation unavailable in current environment"}
                    for i, _ in enumerate(parsed.get("ideas", []))
                ]
            else:
                gen = StaticPostGenerator(
                    GEMINI_API_KEY=api_key,
                    brand_colors=brand_color,
                    output_dir=out_dir,
                    aspect_ratio="4:5",
                )
                results = gen.generate_all(parsed)

        output = {
            "type": content_type,
            "ideas": parsed.get("ideas", []),
            "results": results,
            "raw_json": parsed,
        }
        if warnings:
            output["warning"] = " | ".join(warnings)
        return output
    except Exception as exc:
        return {
            "type": content_type,
            "ideas": [],
            "results": [],
            "raw_json": {"ideas": []},
            "error": str(exc),
        }
