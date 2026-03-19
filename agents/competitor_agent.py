from core.gemini_client import Agent
from media.video_generator import parse_llm_json


class CompetitorAgent(Agent):
    def analyze(self, posts: list[dict]) -> dict:
        """
        Takes competitor posts (from scraper or data file).
        Builds a prompt summarizing the posts.
        Asks Gemini to extract patterns.
        Returns structured dict.
        """
        if not posts:
            return {}

        prompt = self._build_prompt(posts)
        raw = self.ask(prompt, max_tokens=2048)
        if not raw:
            return {}

        try:
            parsed = parse_llm_json(raw)
            if not isinstance(parsed, dict):
                return {}
            return parsed
        except Exception:
            return {}

    def _build_prompt(self, posts: list[dict]) -> str:
        """
        Format posts into readable text block.
        Ask Gemini to return ONLY valid JSON matching the output shape.
        """
        lines = []
        for i, post in enumerate(posts[:30], start=1):
            caption = post.get("caption") or post.get("title") or ""
            hook = post.get("hook", "")
            platform = post.get("platform", "unknown")
            lines.append(f"{i}. [{platform}] hook={hook} | caption={caption[:280]}")

        block = "\n".join(lines)
        return f"""
You are a social media competitor intelligence analyst.
Analyze the following competitor posts and extract winning patterns.

Posts:
{block}

Return ONLY valid JSON with this exact shape:
{{
  "top_hooks": ["hook 1", "hook 2", "hook 3"],
  "top_format": "short reels 15-30s with text overlay",
  "content_patterns": ["problem -> solution", "before/after"],
  "winning_angles": ["price shock", "social proof"],
  "audience_signals": "young females 18-28, beauty-focused"
}}
""".strip()
