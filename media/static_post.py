import os
import json
from dataclasses import dataclass, field
from typing import Optional

from google import genai
from google.genai import types


# ============================================================
# DATA CLASS
# ============================================================

@dataclass
class PostResult:
    idea_index:  int
    status:      str
    image_path:  Optional[str] = None
    json_path:   Optional[str] = None
    error:       Optional[str] = None


# ============================================================
# IMAGE PROMPT BUILDER
# ============================================================

class ImagePromptBuilder:
    """
    Converts a static post idea (from ContentAgent JSON)
    into an optimized Gemini image prompt.
    """

    # كلمات بتشير إن الـ LLM طلب ألوان براند في الصورة
    _COLOR_KEYWORDS = (
        "brand color", "brand colours", "brand accent",
        "hex", "color scheme", "colour scheme",
        "use the color", "use the colour",
        "incorporate color", "incorporate colour",
    )

    @classmethod
    def _should_use_brand_colors(cls, visual_dir: str) -> bool:
        """
        بيرجع True بس لو الـ visual_direction صراحةً طلب ألوان البراند
        وبيكون منطقي نضيفها (مش هتبوظ الصورة).
        """
        vd_lower = visual_dir.lower()
        return any(kw in vd_lower for kw in cls._COLOR_KEYWORDS)

    @classmethod
    def build(cls, idea: dict, brand_colors: list[str]) -> str:
        """
        Args:
            idea:         Single idea dict from {"ideas": [...]}
            brand_colors: List of hex colors e.g. ["#EE3322"]

        Returns:
            Optimized English prompt for Gemini image generation.
        """
        image_desc  = str(idea.get("image_description", "") or "")
        visual_dir  = str(idea.get("visual_direction", "")  or "")

        # ── ألوان البراند: بس لو منطقي ──────────────────────────
        color_instruction = ""
        if brand_colors and cls._should_use_brand_colors(visual_dir):
            color_str = ", ".join(brand_colors)
            color_instruction = (
                f"Subtly incorporate brand accent color(s) {color_str} "
                f"as a background element, prop color, or light tint — "
                f"only if it fits naturally with the scene. "
                f"Do NOT force the color if it clashes with the subject. "
            )

        # ── النص الصارم لمنع أي كتابة في الصورة ────────────────
        no_text_instruction = (
            "CRITICAL: Do NOT include any text, words, letters, numbers, "
            "hashtags, captions, watermarks, logos, overlays, labels, "
            "price tags, or any written content anywhere in the image. "
            "The image must be completely text-free and clean. "
        )

        prompt = (
            f"{image_desc} "
            f"Visual style: {visual_dir} "
            f"{color_instruction}"
            f"High-quality social media post image, vertical 4:5 format, "
            f"professional photography, cinematic lighting, "
            f"sharp focus, modern aesthetic. "
            f"{no_text_instruction}"
        )

        return prompt.strip()


# ============================================================
# STATIC POST GENERATOR
# ============================================================

class StaticPostGenerator:
    """
    Takes ContentAgent JSON output (video_content=False) and generates:
      - idea_1.png  ← Imagen 4 generated image
      - idea_1.json ← hook + post_copy + hashtags + visual_direction + image_path

    Args:
        GEMINI_API_KEY: Your Gemini API key (same key used by ContentAgent)
        brand_colors:   List of hex colors e.g. ["#EE3322"]
        output_dir:     Local folder to save all outputs
        aspect_ratio:   "4:5" for Instagram feed | "9:16" for Stories/TikTok
    """

    IMAGE_MODEL = "gemini-3.1-flash-image-preview"

    def __init__(
        self,
        GEMINI_API_KEY: str,
        brand_colors:   list  = None,
        output_dir:     str   = "output_content",
        aspect_ratio:   str   = "9:16",
    ):
        self.brand_colors  = brand_colors or ["#EE3322"]
        self.output_dir    = output_dir
        self.aspect_ratio  = aspect_ratio
        self.client        = genai.Client(api_key=GEMINI_API_KEY)
        os.makedirs(output_dir, exist_ok=True)

    # ----------------------------------------------------------
    # Helper: safely extract a string field from an idea dict
    # ----------------------------------------------------------
    @staticmethod
    def _safe_str(idea: dict, key: str, default: str = "") -> str:
        """
        Returns idea[key] as a plain string.
        Handles None, list, dict, int, etc. gracefully.
        """
        value = idea.get(key, default)
        if value is None:
            return default
        if isinstance(value, list):
            # Join list items if the field came back as an array
            return " ".join(str(v) for v in value)
        return str(value)

    # ----------------------------------------------------------
    # Generate image using Gemini Flash Image
    # ----------------------------------------------------------
    def _generate_image(self, prompt: str, filename: str) -> Optional[str]:
        try:
            model_id = "gemini-3.1-flash-image-preview"

            response = self.client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=self.aspect_ratio,
                    )
                )
            )

            for part in response.parts:
                if part.inline_data:
                    image_path = os.path.join(self.output_dir, filename)
                    from PIL import Image
                    import io

                    img = Image.open(io.BytesIO(part.inline_data.data))
                    img.save(image_path)
                    return image_path

            print(f"    [!] No image part found in response.")
            return None

        except Exception as e:
            print(f"    [!] Generation error: {e}")
            return None

    # ----------------------------------------------------------
    # Save post metadata as JSON
    # ----------------------------------------------------------
    def _save_json(self, idea: dict, idea_idx: int, image_path: Optional[str]) -> str:
        """
        Saves all post content to a JSON file with the same base name as the image.
        """
        post_data = {
            "idea_index":        idea_idx + 1,
            "hook":              self._safe_str(idea, "hook"),
            "post_copy":         self._safe_str(idea, "post_copy"),
            "hashtags":          idea.get("hashtags", []),
            "visual_direction":  self._safe_str(idea, "visual_direction"),
            "image_description": self._safe_str(idea, "image_description"),
            "image_path":        image_path,
        }

        json_filename = f"idea_{idea_idx + 1}.json"
        json_path     = os.path.join(self.output_dir, json_filename)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(post_data, f, ensure_ascii=False, indent=2)

        return json_path

    # ----------------------------------------------------------
    # MAIN: generate all static posts from ContentAgent JSON
    # ----------------------------------------------------------
    def generate_all(self, content_json: dict) -> list[PostResult]:
        """
        Args:
            content_json: Parsed dict from ContentAgent {"ideas": [...]}

        Returns:
            List of PostResult with status & file paths.
        """
        ideas   = content_json.get("ideas", [])
        results = []
        builder = ImagePromptBuilder()

        print(f"\n🖼️  Starting static post generation for {len(ideas)} idea(s)...\n")

        for idea_idx, idea in enumerate(ideas):
            base_name = f"idea_{idea_idx + 1}"
            print(f"━━━ Idea {idea_idx + 1}/{len(ideas)} ━━━")

            # Debug: show raw field types so unexpected structures are visible
            print(f"  🔍 Field types: { {k: type(v).__name__ for k, v in idea.items()} }")

            # Safely extract hook for display
            hook_preview = self._safe_str(idea, "hook")[:60]
            print(f"  📌 Hook: {hook_preview}...")

            # Build image prompt
            prompt = builder.build(idea, self.brand_colors)
            print(f"  📝 Image prompt ({len(prompt)} chars): {prompt[:100]}...")

            # Generate image
            print(f"  🎨 Generating image with Gemini Flash Image...")
            image_path = self._generate_image(prompt, f"{base_name}.png")

            if image_path:
                print(f"  ✅ Image saved → {image_path}")
            else:
                print(f"  ⚠️  Image generation failed, saving JSON anyway...")

            # Save JSON (always, even if image failed)
            json_path = self._save_json(idea, idea_idx, image_path)
            print(f"  💾 Data  saved → {json_path}\n")

            results.append(PostResult(
                idea_index = idea_idx,
                status     = "completed" if image_path else "partial",
                image_path = image_path,
                json_path  = json_path,
                error      = None if image_path else "Image generation failed",
            ))

        self._print_summary(results)
        return results

    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------
    @staticmethod
    def _print_summary(results: list[PostResult]):
        done    = [r for r in results if r.status == "completed"]
        partial = [r for r in results if r.status == "partial"]
        print("=" * 55)
        print(f"📊 SUMMARY  —  ✅ {len(done)} completed  |  ⚠️  {len(partial)} partial")
        print("=" * 55)
        for r in results:
            icon = "✅" if r.status == "completed" else "⚠️ "
            print(f"  {icon} Idea {r.idea_index+1}")
            print(f"      🖼️  {r.image_path or 'No image'}")
            print(f"      📄  {r.json_path}")
        print("=" * 55)