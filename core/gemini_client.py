import os
import time
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency fallback
    def load_dotenv(*_args, **_kwargs):
        return False
try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover - graceful fallback for missing SDK
    genai = None
    types = None
try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency fallback
    OpenAI = None

from core.logger import get_logger

load_dotenv()

logger = get_logger("GeminiClient")


class Agent:
    def __init__(
        self,
        provider: str = "google",
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        api_env: str | None = None,
        max_retries: int = 3,
        retry_delay: int = 2,
        reasoning_enabled: bool = True,
    ):
        normalized_provider = (provider or "google").strip().lower()
        if normalized_provider in {"openapi", "openai"}:
            normalized_provider = "openrouter"

        self.provider = normalized_provider
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.reasoning_enabled = reasoning_enabled
        self.last_assistant_message: dict | None = None
        self.last_reasoning_details = None

        if not api_env:
            api_env = "OPENROUTER_API_KEY" if self.provider == "openrouter" else "GEMINI_API_KEY"

        key = api_key or os.getenv(api_env, "")
        self.client = None
        if self.provider == "openrouter":
            self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key) if key and OpenAI else None
        else:
            self.client = genai.Client(api_key=key) if key and genai else None

    def _ask_google(self, prompt: str, max_tokens: int = 8192, temperature: float = 0.7) -> str:
        if not self.client or not types:
            logger.warning("Google client unavailable; returning empty response")
            return ""

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return response.text or ""

    def _ask_openrouter(self, prompt: str, max_tokens: int = 8192, temperature: float = 0.7) -> str:
        if not self.client:
            logger.warning("OpenRouter client unavailable; returning empty response")
            return ""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body={"reasoning": {"enabled": bool(self.reasoning_enabled)}},
        )
        message = response.choices[0].message
        content = getattr(message, "content", "") or ""
        self.last_reasoning_details = getattr(message, "reasoning_details", None)
        self.last_assistant_message = {"role": "assistant", "content": content}
        if self.last_reasoning_details is not None:
            self.last_assistant_message["reasoning_details"] = self.last_reasoning_details
        return content

    def ask_with_messages(
        self,
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> dict:
        """
        OpenRouter-compatible multi-turn call that preserves reasoning_details.
        Returns assistant message dict: {"role","content","reasoning_details?"}
        """
        if self.provider != "openrouter" or not self.client:
            # Fallback behavior for non-openrouter provider.
            prompt = "\n".join([str(m.get("content", "")) for m in messages if m.get("role") == "user"])
            content = self.ask(prompt, max_tokens=max_tokens, temperature=temperature)
            return {"role": "assistant", "content": content}

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body={"reasoning": {"enabled": bool(self.reasoning_enabled)}},
        )
        msg = response.choices[0].message
        assistant = {"role": "assistant", "content": getattr(msg, "content", "") or ""}
        reasoning_details = getattr(msg, "reasoning_details", None)
        if reasoning_details is not None:
            assistant["reasoning_details"] = reasoning_details
        self.last_assistant_message = assistant
        self.last_reasoning_details = reasoning_details
        return assistant

    def ask(self, prompt: str, max_tokens: int = 8192, temperature: float = 0.7) -> str:
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.provider == "openrouter":
                    return self._ask_openrouter(prompt, max_tokens=max_tokens, temperature=temperature)
                return self._ask_google(prompt, max_tokens=max_tokens, temperature=temperature)
            except Exception as exc:
                logger.warning(
                    "LLM attempt %s/%s failed [%s]: %s",
                    attempt,
                    self.max_retries,
                    self.provider,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)
                else:
                    logger.error("LLM failed after %s attempts (%s)", self.max_retries, self.provider)
        return ""


class GeminiClient(Agent):
    """Backward-compatible alias for older modules."""

    def __init__(self):
        super().__init__(model="gemini-2.5-flash")
