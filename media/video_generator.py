import os
import json
import re
import time
import subprocess
import requests
from typing import Optional
from dataclasses import dataclass


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class VideoResult:
    idea_index:    int
    scene_index:   int
    generation_id: str
    status:        str
    video_url:     Optional[str] = None
    error:         Optional[str] = None


# ============================================================
# JSON PARSER  (robust — handles messy LLM output)
# ============================================================

def parse_llm_json(raw: str) -> dict:
    """
    Robust JSON parser that handles all messy LLM outputs.
    """
    # Step 1: extract from markdown block if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        raw = match.group(1)
    else:
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]

    raw = raw.strip()

    # Step 2: fix real newlines inside JSON strings
    def fix_string_newlines(text: str) -> str:
        result = []
        i      = 0
        in_str = False
        while i < len(text):
            ch = text[i]
            if in_str and ch == '\\' and i + 1 < len(text):
                result.append(ch)
                result.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = not in_str
                result.append(ch)
            elif in_str and ch in ('\n', '\r'):
                result.append(' ')
            else:
                result.append(ch)
            i += 1
        return ''.join(result)

    raw = fix_string_newlines(raw)

    # Step 3: try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Step 4: remove trailing commas
    cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Step 5: json_repair as last resort
    try:
        from json_repair import repair_json
        return json.loads(repair_json(cleaned))
    except Exception:
        pass

    raise ValueError(
        f"Could not parse JSON from LLM output.\nFirst 300 chars:\n{raw[:300]}"
    )


# ============================================================
# PROMPT SERIALIZER
# Saves the structured prompt fields to JSON.
# Any field that is empty/None/False is stripped to save tokens.
# ============================================================

class PromptSerializer:
    """
    Saves the prompt as a structured JSON file (one per scene).
    Empty strings, None, False, empty dicts, and empty lists
    are all removed before saving so the file stays lean.
    """

    @staticmethod
    def _strip_empty(obj):
        """
        Recursively removes falsy values from dicts/lists.
        duration_seconds is always kept even if 0.
        """
        if isinstance(obj, dict):
            cleaned = {}
            for k, v in obj.items():
                if k == "duration_seconds":
                    cleaned[k] = v
                    continue
                v2 = PromptSerializer._strip_empty(v)
                if v2 or v2 == 0:
                    cleaned[k] = v2
            return cleaned
        elif isinstance(obj, list):
            cleaned = [PromptSerializer._strip_empty(i) for i in obj]
            return [i for i in cleaned if i or i == 0]
        else:
            return obj

    @staticmethod
    def build_prompt_dict(
        flat_prompt:      str,
        scene:            dict,
        hook:             dict,
        cta:              dict,
        visual_direction: dict,
        brand_colors:     list,
        language:         str,
        character:        dict = None,
        lighting:         dict = None,
        vo_props:         dict = None,
        is_first_scene:   bool = False,
        is_last_scene:    bool = False,
    ) -> dict:
        """
        Builds a structured dict that mirrors the prompt blocks.
        Saved to JSON for traceability. Empty fields are stripped.
        """
        visual_direction = visual_direction or {}
        visuals      = scene.get("visuals", "")
        voiceover    = scene.get("voiceover", "")
        text_overlay = scene.get("text_overlay", "")
        duration     = scene.get("duration_seconds", 8)

        # character
        char_dict = None
        if character:
            eye   = character.get("eye color")  or character.get("eye_color")
            face  = character.get("facial details") or character.get("facial_details")
            phys  = character.get("any other physical details") or character.get("physical_details")
            expr  = character.get("facial_expression")
            parts = [p for p in [eye, face, phys] if p]
            if parts:
                char_dict = {"description": ", ".join(parts)}
                if expr:
                    char_dict["expression_this_scene"] = expr

        # lighting
        light_dict = None
        if lighting:
            angle = lighting.get("camera angel") or lighting.get("camera_angle")
            cam   = lighting.get("camera type")  or lighting.get("camera_type")
            mode  = lighting.get("lighting mode") or lighting.get("lighting_mode")
            pos   = lighting.get("lighting position") or lighting.get("lighting_position")
            move  = lighting.get("camera position and movement") or lighting.get("camera_movement")
            parts = {}
            if angle: parts["camera_angle"]     = angle
            if cam:   parts["camera_type"]       = cam
            if mode:  parts["lighting_mode"]     = mode
            if pos:   parts["lighting_position"] = pos
            if move:  parts["camera_movement"]   = move
            if parts:
                light_dict = parts

        # voiceover
        vo_dict = None
        if voiceover:
            gender = (vo_props or {}).get("gender sound") or (vo_props or {}).get("gender", "Female")
            tone   = (vo_props or {}).get("tone", "confident")
            vo_dict = {
                "gender":   gender or "Female",
                "tone":     tone   or "confident",
                "language": language,
                "text":     voiceover,
            }

        # hook / cta
        hook_dict = hook if is_first_scene and hook else None
        cta_dict  = cta  if is_last_scene  and cta  else None

        # style
        style_dict = {
            "brand_color": brand_colors[0] if brand_colors else None,
            "color_notes": visual_direction.get("color_usage", ""),
            "pacing":      visual_direction.get("pacing", "medium"),
            "transitions": visual_direction.get("transitions", "cut"),
            "format":      "Vertical 9:16, professional social-media quality.",
        }

        raw = {
            "flat_prompt":   flat_prompt,
            "character":     char_dict,
            "lighting":      light_dict,
            "scene_visuals": {
                "duration_seconds": duration,
                "description":      visuals,
                "text_overlay":     text_overlay,
            },
            "voiceover":     vo_dict,
            "hook":          hook_dict,
            "cta":           cta_dict,
            "style":         style_dict,
        }

        return PromptSerializer._strip_empty(raw)

    @staticmethod
    def save(
        prompt_dict: dict,
        idea_idx:    int,
        scene_num:   int,
        output_dir:  str,
    ) -> str:
        """
        Saves to: output_dir/prompts/idea_{N}_scene_{M}_prompt.json
        Returns the saved file path.
        """
        prompts_dir = os.path.join(output_dir, "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        filepath = os.path.join(
            prompts_dir, f"idea_{idea_idx + 1}_scene_{scene_num}_prompt.json"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(prompt_dict, f, ensure_ascii=False, indent=2)
        return filepath


# ============================================================
# VEO PROMPT BUILDER  (old style — proven to produce good videos)
# ============================================================

class VeoPromptBuilder:
    """
    Converts ContentAgent JSON into an optimized Veo 3.1 prompt.
    Uses the original clean prompt style that produced good results,
    wired into the new infrastructure (JSON saving, delta merge, joining).
    """

    # ----------------------------------------------------------
    # Character block
    # ----------------------------------------------------------
    @staticmethod
    def _build_character(character: dict) -> str:
        if not character:
            return ""
        parts = []
        eye  = character.get("eye color")  or character.get("eye_color")
        face = character.get("facial details") or character.get("facial_details")
        phys = character.get("any other physical details") or character.get("physical_details")
        if eye:  parts.append(f"eye color: {eye}")
        if face: parts.append(face)
        if phys: parts.append(phys)
        if not parts:
            return ""
        return (
            "CONSISTENT CHARACTER across all scenes — "
            + ", ".join(parts)
            + ". Maintain identical appearance in every scene."
        )

    # ----------------------------------------------------------
    # Lighting & camera block
    # ----------------------------------------------------------
    @staticmethod
    def _build_lighting(lighting: dict) -> str:
        if not lighting:
            return ""
        parts = []
        angle = lighting.get("camera angel") or lighting.get("camera_angle")
        cam   = lighting.get("camera type")  or lighting.get("camera_type")
        mode  = lighting.get("lighting mode") or lighting.get("lighting_mode")
        pos   = lighting.get("lighting position") or lighting.get("lighting_position")
        move  = lighting.get("camera position and movement") or lighting.get("camera_movement")
        if angle: parts.append(f"camera angle: {angle}")
        if cam:   parts.append(f"camera: {cam}")
        if mode:  parts.append(f"lighting: {mode}")
        if pos:   parts.append(f"light position: {pos}")
        if move:  parts.append(f"movement: {move}")
        return "Cinematography — " + ", ".join(parts) + "." if parts else ""

    # ----------------------------------------------------------
    # Voiceover block
    # ----------------------------------------------------------
    @staticmethod
    def _build_voiceover_style(vo_props: dict, language: str, voiceover_text: str) -> str:
        if not voiceover_text:
            return ""
        gender = (vo_props or {}).get("gender sound") or (vo_props or {}).get("gender", "Female")
        tone   = (vo_props or {}).get("tone", "confident")
        return (
            f"Voiceover: {gender or 'Female'} voice, {tone or 'confident'} tone, "
            f'speaking in {language}: "{voiceover_text}".'
        )

    # ----------------------------------------------------------
    # Main build — returns (flat_string, prompt_dict)
    # ----------------------------------------------------------
    @staticmethod
    def build(
        scene:            dict,
        hook:             dict,
        cta:              dict,
        visual_direction: dict,
        brand_colors:     list,
        language:         str,
        character:        dict = None,
        lighting:         dict = None,
        vo_props:         dict = None,
        is_first_scene:   bool = False,
        is_last_scene:    bool = False,
    ) -> tuple[str, dict]:
        """
        Returns:
            (flat_prompt_string, prompt_dict)
        flat_prompt_string  → sent to Veo API
        prompt_dict         → saved to JSON for traceability
        """
        visual_direction = visual_direction or {}

        visuals      = scene.get("visuals", "")
        voiceover    = scene.get("voiceover", "")
        text_overlay = scene.get("text_overlay", "")
        pacing       = visual_direction.get("pacing", "medium")
        transitions  = visual_direction.get("transitions", "cut")
        color_notes  = visual_direction.get("color_usage", "")
        brand_color  = brand_colors[0] if brand_colors else "#FF0000"

        # build each block
        char_block     = VeoPromptBuilder._build_character(character or {})
        lighting_block = VeoPromptBuilder._build_lighting(lighting or {})
        vo_block       = VeoPromptBuilder._build_voiceover_style(
                             vo_props or {}, language, voiceover)

        # hook — first scene only
        hook_block = ""
        if is_first_scene and hook:
            hook_block = (
                f"OPENING HOOK ({hook.get('duration_seconds', 3)}s): "
                f'bold on-screen text reads "{hook.get("text", "")}" — '
                f"eye-catching, high contrast, centered on screen."
            )

        # CTA — last scene only
        cta_block = ""
        if is_last_scene and cta:
            cta_block = (
                f'END CALL-TO-ACTION: overlay text "{cta.get("text", "")}" '
                f'appears at {cta.get("placement", "end")} of video.'
            )

        visual_block  = f"Scene visuals: {visuals}."
        overlay_block = f'On-screen text overlay: "{text_overlay}".' if text_overlay else ""
        style_block   = (
            f"Brand color {brand_color} used in video. "
            f"{color_notes} "
            f"Pacing: {pacing}. Transitions: {transitions}. "
            f"Vertical 9:16 format, professional social-media production quality."
        )

        # assemble in priority order — character first = highest weight
        flat = " ".join(filter(None, [
            char_block,       # 1. character consistency — prime position
            lighting_block,   # 2. camera & lighting
            hook_block,       # 3. hook (first scene only)
            visual_block,     # 4. scene visuals
            vo_block,         # 5. voiceover with tone
            overlay_block,    # 6. on-screen text
            cta_block,        # 7. CTA (last scene only)
            style_block,      # 8. brand colors & style
        ])).strip()

        # build the JSON-saveable dict
        prompt_dict = PromptSerializer.build_prompt_dict(
            flat_prompt      = flat,
            scene            = scene,
            hook             = hook,
            cta              = cta,
            visual_direction = visual_direction,
            brand_colors     = brand_colors,
            language         = language,
            character        = character,
            lighting         = lighting,
            vo_props         = vo_props,
            is_first_scene   = is_first_scene,
            is_last_scene    = is_last_scene,
        )

        return flat, prompt_dict


# ============================================================
# VIDEO JOINER
# Concatenates scene mp4 files into one final video per idea.
# Requires ffmpeg installed on the system (ffmpeg.org).
# ============================================================

class VideoJoiner:
    """
    Joins individual scene mp4 files into one final video using FFmpeg.

    Strategy:
    - Attempt 1: concat demuxer with stream copy (no re-encode) — lossless & instant.
    - Attempt 2: concat demuxer with libx264 re-encode — handles codec/resolution mismatch.
    - Skips if fewer than 2 completed scenes exist.
    - Writes a concat list file to output_dir/concat/ for traceability.

    Output: output_dir/idea_{N}_full.mp4
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.concat_dir = os.path.join(output_dir, "concat")
        os.makedirs(self.concat_dir, exist_ok=True)

    @staticmethod
    def _ffmpeg_available() -> bool:
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _write_concat_list(self, scene_paths: list[str], idea_idx: int) -> str:
        list_path = os.path.join(self.concat_dir, f"idea_{idea_idx + 1}_concat.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for path in scene_paths:
                abs_path = os.path.abspath(path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
        return list_path

    def _run_ffmpeg(self, list_path: str, output_path: str) -> bool:
        # attempt 1: lossless copy
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_path, "-c", "copy", output_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return True

        print("    [~] Lossless concat failed — retrying with re-encode...")

        # attempt 2: re-encode for compatibility
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_path,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", output_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            print(f"    [!] FFmpeg error:\n{result.stderr.decode()[:400]}")
            return False
        return True

    def join(self, scene_paths: list[str], idea_idx: int) -> Optional[str]:
        """
        Join completed scene files into one video.
        Returns path to joined video, or None if failed/skipped.
        """
        valid = [p for p in scene_paths if p and os.path.isfile(p)]

        if len(valid) == 0:
            print(f"  ⚠️  Idea {idea_idx + 1}: no scene files found — skipping join.")
            return None
        if len(valid) == 1:
            print(f"  ⚠️  Idea {idea_idx + 1}: only 1 scene — no join needed.")
            return valid[0]
        if not self._ffmpeg_available():
            print("  [!] ffmpeg not found — install ffmpeg to enable scene joining.")
            return None

        output_path = os.path.join(self.output_dir, f"idea_{idea_idx + 1}_full.mp4")
        list_path   = self._write_concat_list(valid, idea_idx)

        print(f"\n  🎞️  Joining {len(valid)} scene(s) → {os.path.basename(output_path)}")

        if not self._run_ffmpeg(list_path, output_path):
            print(f"  ❌ Join failed for idea {idea_idx + 1}")
            return None

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  ✅ Full video → {output_path}  ({size_mb:.1f} MB)")
        return output_path


# ============================================================
# VIDEO GENERATOR
# ============================================================

class VideoGenerator:
    """
    Takes ContentAgent JSON output and generates one video per scene
    using Veo 3.1 Image-to-Video via AI/ML API, then joins all scenes
    into one full video per idea using FFmpeg.

    Args:
        api_key:        Your AI/ML API key  →  https://aimlapi.com
        image_url:      URL of the reference/product image
        language:       Language string e.g. "Egyptian Arabic"
        brand_colors:   List of hex colors  e.g. ["#EE3322"]
        aspect_ratio:   "9:16" vertical (Reels/TikTok) | "16:9" horizontal
        poll_interval:  Seconds between status-check calls
        output_dir:     Local folder to save downloaded videos
    """

    MODEL    = "google/veo-3.1-i2v"
    BASE_URL = "https://api.aimlapi.com/v2"

    def __init__(
        self,
        api_key:       str,
        image_url:     str,
        language:      str  = "Egyptian Arabic",
        brand_colors:  list = None,
        aspect_ratio:  str  = "9:16",
        poll_interval: int  = 20,
        output_dir:    str  = "output_videos",
    ):
        self.api_key       = api_key
        self.image_url     = image_url
        self.language      = language
        self.brand_colors  = brand_colors or [None]
        self.aspect_ratio  = aspect_ratio
        self.poll_interval = poll_interval
        self.output_dir    = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.joiner        = VideoJoiner(output_dir)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    # ----------------------------------------------------------
    # Submit generation job → returns generation_id
    # ----------------------------------------------------------
    def _submit(self, prompt: str) -> Optional[str]:
        payload = {
            "model":        self.MODEL,
            "prompt":       prompt,
            "image_url":    self.image_url,
            "aspect_ratio": self.aspect_ratio,
        }
        try:
            resp = requests.post(
                f"{self.BASE_URL}/video/generations",
                json=payload,
                headers=self._headers(),
                timeout=60,
            )
            if resp.status_code >= 400:
                print(f"    [!] Submit error {resp.status_code}: {resp.text}")
                return None
            return resp.json().get("id")
        except requests.RequestException as e:
            print(f"    [!] Submit request failed: {e}")
            return None

    # ----------------------------------------------------------
    # Poll until completed → returns video URL
    # ----------------------------------------------------------
    def _poll(self, gen_id: str) -> Optional[str]:
        print(f"    [~] Polling {gen_id}", end="", flush=True)
        while True:
            time.sleep(self.poll_interval)
            try:
                resp = requests.get(
                    f"{self.BASE_URL}/video/generations",
                    params={"generation_id": gen_id},
                    headers=self._headers(),
                    timeout=30,
                )
                if resp.status_code >= 400:
                    print(f"\n    [!] Poll error: {resp.text}")
                    return None

                data   = resp.json()
                status = data.get("status", "")
                print(".", end="", flush=True)

                if status == "completed":
                    print(" ✓")
                    return data.get("video", {}).get("url")
                elif status in ("failed", "error"):
                    print(f" ✗ ({data.get('error', 'unknown error')})")
                    return None

            except requests.RequestException as e:
                print(f"\n    [!] Poll request failed: {e}")
                return None

    # ----------------------------------------------------------
    # Download video to local output folder
    # ----------------------------------------------------------
    def _download(self, url: str, filename: str) -> str:
        path = os.path.join(self.output_dir, filename)
        try:
            resp = requests.get(url, timeout=120)
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
        except requests.RequestException as e:
            print(f"    [!] Download failed: {e}")
            return url

    # ----------------------------------------------------------
    # Safe key lookup — handles typos & key variations
    # ----------------------------------------------------------
    @staticmethod
    def _safe_get(idea: dict, *keys, default=None):
        """
        Tries each key in order, returns first non-empty value found.
        Handles typos like "charachter details" and spacing like "Lighting condition ".
        """
        for key in keys:
            val = idea.get(key)
            if val is not None and val != {} and val != []:
                return val
        return default if default is not None else {}

    # ----------------------------------------------------------
    # Delta merge — fills missing fields from previous scene
    # ----------------------------------------------------------
    @staticmethod
    def _merge_scene_delta(scene: dict, prev_scene: dict) -> dict:
        """
        The LLM only writes fields that changed (delta pattern).
        This fills gaps from the previous scene so every scene is complete.

        Fix: if use_character=False, character_details inherited from
        prev_scene are removed so product-only scenes never bleed in an actor.
        """
        if not prev_scene:
            return scene

        merged = dict(prev_scene)
        merged.update(scene)

        # respect explicit use_character=False
        if scene.get("use_character") is False:
            merged.pop("character_details", None)
            for key in ("lighting_conditions", "visual_direction"):
                prev_val = prev_scene.get(key) or {}
                curr_val = scene.get(key) or {}
                if prev_val or curr_val:
                    merged[key] = {**prev_val, **curr_val}
            return merged

        # normal deep merge for nested dicts
        for key in ("character_details", "lighting_conditions", "visual_direction"):
            prev_val = prev_scene.get(key) or {}
            curr_val = scene.get(key) or {}
            if prev_val or curr_val:
                merged[key] = {**prev_val, **curr_val}

        return merged

    # ----------------------------------------------------------
    # Save idea metadata as JSON
    # ----------------------------------------------------------
    def _save_idea_json(self, idea: dict, idea_idx: int, scenes: list[dict]) -> str:
        caption  = idea.get("caption", "")
        hashtags = idea.get("hashtags", [])
        if isinstance(caption, list):
            caption = " ".join(str(c) for c in caption)

        vo_props = self._safe_get(
            idea,
            "Voice over property",
            "voiceover_properties",
            "voiceover_props",
        )

        idea_data = {
            "idea_index":                 idea_idx + 1,
            "caption":                    str(caption),
            "hashtags":                   hashtags,
            "hook":                       idea.get("hook", {}),
            "cta":                        idea.get("cta", {}),
            "voiceover_properties":       vo_props,
            "script":                     idea.get("script", []),
            "estimated_duration_seconds": idea.get("estimated_duration_seconds", 0),
            "generated_scenes":           [s for s in scenes if s.get("status") == "completed"],
        }

        json_path = os.path.join(self.output_dir, f"idea_{idea_idx + 1}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(idea_data, f, ensure_ascii=False, indent=2)
        return json_path

    def _patch_idea_json_with_full_video(self, json_path: str, full_video_path: str):
        """Adds full_video_path field to the already-saved idea JSON."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["full_video_path"] = full_video_path
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"    [!] Could not patch idea JSON: {e}")

    # ----------------------------------------------------------
    # MAIN: generate all videos from ContentAgent JSON
    # ----------------------------------------------------------
    def generate_all(self, content_json: dict) -> list[VideoResult]:
        """
        Args:
            content_json: Parsed dict from ContentAgent  {"ideas": [...]}

        Returns:
            List of VideoResult with status & local file paths.
        """
        ideas   = content_json.get("ideas", [])
        results = []
        builder = VeoPromptBuilder()

        # tracks completed scene paths per idea for joining
        idea_scene_paths: dict[int, list[str]] = {}

        print(f"\n🎬 Starting video generation for {len(ideas)} idea(s)...\n")

        for idea_idx, idea in enumerate(ideas):

            # ── idea-level fields ────────────────────────────
            hook     = idea.get("hook", {})
            script   = idea.get("script", [])
            cta      = idea.get("cta", {})
            n_scenes = len(script)

            # visual_direction is idea-level — gives coherence across all scenes
            visual_direction = self._safe_get(
                idea,
                "visual_direction",
                "visual direction",
            )

            # character & lighting — supports both old schema (idea-level)
            # and new schema (per-scene via delta merge) simultaneously
            character = self._safe_get(
                idea,
                "charachter details",   # typo from old LLM output
                "character details",
                "character_details",
            )
            lighting = self._safe_get(
                idea,
                "Lighting condition ",  # trailing space from old LLM output
                "Lighting condition",
                "lighting_conditions",
                "lighting condition",
            )
            vo_props = self._safe_get(
                idea,
                "Voice over property",
                "voiceover_properties",
                "voiceover_props",
                "voice_over_property",
            )

            print(f"━━━ Idea {idea_idx + 1}/{len(ideas)} "
                  f"| {n_scenes} scene(s) "
                  f"| pacing: {(visual_direction or {}).get('pacing', '?')} ━━━")

            scenes_output: list[dict] = []
            prev_scene:    dict       = {}
            idea_scene_paths[idea_idx] = []

            for scene_idx, scene in enumerate(script):
                is_first  = scene_idx == 0
                is_last   = scene_idx == n_scenes - 1
                scene_num = scene.get("scene", scene_idx + 1)

                # delta merge — fills missing fields from previous scene
                full_scene = self._merge_scene_delta(scene, prev_scene)
                prev_scene = full_scene

                # per-scene character/lighting override (new schema)
                # falls back to idea-level if not present in scene
                scene_character = full_scene.get("character_details") or character or {}
                scene_lighting  = full_scene.get("lighting_conditions") or lighting or {}

                print(f"\n  ▶ Scene {scene_num}/{n_scenes}")

                # build prompt — returns (flat_string, prompt_dict)
                prompt, prompt_dict = builder.build(
                    scene            = full_scene,
                    hook             = hook,
                    cta              = cta,
                    visual_direction = visual_direction,
                    brand_colors     = self.brand_colors,
                    language         = self.language,
                    character        = scene_character,
                    lighting         = scene_lighting,
                    vo_props         = vo_props,
                    is_first_scene   = is_first,
                    is_last_scene    = is_last,
                )

                # save prompt to JSON
                prompt_json_path = PromptSerializer.save(
                    prompt_dict = prompt_dict,
                    idea_idx    = idea_idx,
                    scene_num   = scene_num,
                    output_dir  = self.output_dir,
                )
                print(f"  📄 Prompt JSON → {prompt_json_path}")
                print(f"  📝 Prompt ({len(prompt)} chars): {prompt[:120]}...")
                print(f"  📤 Submitting to Veo 3.1...")

                gen_id = self._submit(prompt)

                if not gen_id:
                    scenes_output.append({
                        "scene":       scene_num,
                        "status":      "failed",
                        "prompt_json": prompt_json_path,
                        "video_path":  None,
                        "error":       "Submission failed",
                    })
                    results.append(VideoResult(
                        idea_index=idea_idx, scene_index=scene_idx,
                        generation_id="", status="failed",
                        error="Submission failed",
                    ))
                    continue

                video_url = self._poll(gen_id)

                if not video_url:
                    scenes_output.append({
                        "scene":         scene_num,
                        "status":        "failed",
                        "generation_id": gen_id,
                        "prompt_json":   prompt_json_path,
                        "video_path":    None,
                        "error":         "Generation failed during polling",
                    })
                    results.append(VideoResult(
                        idea_index=idea_idx, scene_index=scene_idx,
                        generation_id=gen_id, status="failed",
                        error="Generation failed during polling",
                    ))
                    continue

                filename   = f"idea{idea_idx + 1}_scene{scene_num}.mp4"
                local_path = self._download(video_url, filename)

                print(f"  ✅ Saved → {local_path}")

                scenes_output.append({
                    "scene":         scene_num,
                    "status":        "completed",
                    "generation_id": gen_id,
                    "prompt_json":   prompt_json_path,
                    "video_path":    local_path,
                })
                results.append(VideoResult(
                    idea_index    = idea_idx,
                    scene_index   = scene_idx,
                    generation_id = gen_id,
                    status        = "completed",
                    video_url     = local_path,
                ))

                # keep ordered list for joining
                idea_scene_paths[idea_idx].append(local_path)

            # save idea metadata JSON
            json_path = self._save_idea_json(idea, idea_idx, scenes_output)
            print(f"\n  💾 Idea data saved → {json_path}")

            # join all scenes into one full video
            full_video_path = self.joiner.join(
                scene_paths = idea_scene_paths[idea_idx],
                idea_idx    = idea_idx,
            )
            if full_video_path:
                self._patch_idea_json_with_full_video(json_path, full_video_path)

        self._print_summary(results, idea_scene_paths)
        return results

    # ----------------------------------------------------------
    # Summary report
    # ----------------------------------------------------------
    def _print_summary(
        self,
        results:          list[VideoResult],
        idea_scene_paths: dict[int, list[str]] = None,
    ):
        done   = [r for r in results if r.status == "completed"]
        failed = [r for r in results if r.status == "failed"]
        print("\n" + "=" * 55)
        print(f"📊 SUMMARY  —  ✅ {len(done)} scenes completed  |  ❌ {len(failed)} failed")
        print("=" * 55)
        for r in done:
            print(f"  ✅ Idea {r.idea_index+1}  Scene {r.scene_index+1}  →  {r.video_url}")
        for r in failed:
            print(f"  ❌ Idea {r.idea_index+1}  Scene {r.scene_index+1}  →  {r.error}")

        # show full video paths
        if idea_scene_paths:
            print()
            for idea_idx in sorted(idea_scene_paths.keys()):
                full_path = os.path.join(self.output_dir, f"idea_{idea_idx + 1}_full.mp4")
                if os.path.isfile(full_path):
                    size_mb = os.path.getsize(full_path) / (1024 * 1024)
                    print(f"  🎬 Idea {idea_idx+1} full video  →  {full_path}  ({size_mb:.1f} MB)")
        print("=" * 55)