import os
import time
from dotenv import load_dotenv
try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover - graceful fallback for missing SDK
    genai = None
    types = None

from core.logger import get_logger

load_dotenv()

logger = get_logger("GeminiClient")


class Agent:
    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        api_env: str = "GEMINI_API_KEY",
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        key = api_key or os.getenv(api_env, "")
        self.client = genai.Client(api_key=key) if key and genai else None

    def ask(self, prompt: str, max_tokens: int = 8192, temperature: float = 0.7) -> str:
        if not self.client or not types:
            logger.warning("Gemini client unavailable; returning empty response")
            return ""

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                    ),
                )
                return response.text or ""
            except Exception as exc:
                logger.warning(
                    "Gemini attempt %s/%s failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)
                else:
                    logger.error("Gemini failed after %s attempts", self.max_retries)
        return ""


class GeminiClient(Agent):
    """Backward-compatible alias for older modules."""

    def __init__(self):
        super().__init__(model="gemini-2.5-flash")
