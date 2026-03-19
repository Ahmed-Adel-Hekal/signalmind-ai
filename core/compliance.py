import copy
import re


class ContentComplianceGuard:
    """
    Lightweight rule-based compliance layer for generated content.
    - Sanitizes risky marketing claims.
    - Masks prohibited/harmful terms.
    - Normalizes hashtags.
    - Replaces severely non-compliant ideas with safe fallback templates.
    """

    PROHIBITED_TERMS = {
        "hate",
        "kill",
        "racist",
        "terrorist",
        "suicide",
        "nazi",
    }

    CLAIM_REPLACEMENTS = {
        r"\bguaranteed\b": "can help",
        r"\b100%\b": "highly",
        r"\bno risk\b": "lower risk",
        r"\binstant results?\b": "faster results",
        r"\bcure\b": "improve",
        r"\bget rich quick\b": "grow steadily",
    }

    RISKY_PATTERNS = [
        ("harmful_term", re.compile(r"\b(hate|kill|terrorist|suicide|nazi|racist)\b", re.IGNORECASE), "high"),
        ("medical_claim", re.compile(r"\b(cure|treat disease|guaranteed recovery)\b", re.IGNORECASE), "medium"),
        ("financial_promise", re.compile(r"\b(100% return|guaranteed profit|get rich quick)\b", re.IGNORECASE), "medium"),
    ]

    def __init__(self, language: str = "English"):
        self.language = language

    def _normalize_whitespace(self, text: str) -> str:
        return " ".join(str(text or "").split())

    def _sanitize_text(self, text: str) -> tuple[str, list[dict]]:
        original = self._normalize_whitespace(text)
        updated = original
        issues = []

        for pattern, replacement in self.CLAIM_REPLACEMENTS.items():
            if re.search(pattern, updated, flags=re.IGNORECASE):
                updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
                issues.append({"issue": "claim_softened", "severity": "medium"})

        for term in self.PROHIBITED_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", updated, flags=re.IGNORECASE):
                updated = re.sub(rf"\b{re.escape(term)}\b", "***", updated, flags=re.IGNORECASE)
                issues.append({"issue": "harmful_term_masked", "severity": "high"})

        return self._normalize_whitespace(updated), issues

    def _scan_severity(self, text: str) -> str:
        content = str(text or "")
        max_level = "none"
        order = {"none": 0, "low": 1, "medium": 2, "high": 3}
        for _, regex, severity in self.RISKY_PATTERNS:
            if regex.search(content):
                if order[severity] > order[max_level]:
                    max_level = severity
        return max_level

    def _normalize_hashtags(self, hashtags: list) -> list[str]:
        normalized = []
        for tag in hashtags or []:
            cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(tag).replace("#", ""))
            if cleaned:
                normalized.append(cleaned[:32])
        # preserve order + unique
        out = []
        seen = set()
        for tag in normalized:
            low = tag.lower()
            if low not in seen:
                seen.add(low)
                out.append(tag)
        return out[:12]

    def _safe_static_idea(self, topic: str, idx: int) -> dict:
        return {
            "hook": f"Simple framework for {topic} (Idea {idx})",
            "post_copy": (
                f"Here is a practical and ethical approach to {topic}: "
                "start with value, share proof, then invite action."
            ),
            "hashtags": ["marketing", "content", "strategy"],
            "image_description": f"Clean brand-safe visual concept about {topic}",
            "visual_direction": "clean, positive, professional",
        }

    def _safe_video_idea(self, topic: str, idx: int) -> dict:
        return {
            "hook": {"text": f"{topic}: practical tips (Idea {idx})", "duration_seconds": 3},
            "script": [
                {"scene": 1, "visuals": f"Context around {topic}", "voiceover": "Let us break this down simply.", "duration_seconds": 4},
                {"scene": 2, "visuals": "Three clear steps on screen", "voiceover": "Use this practical framework in your next post.", "duration_seconds": 5},
                {"scene": 3, "visuals": "Positive CTA slide", "voiceover": "Save this and apply it today.", "duration_seconds": 3},
            ],
            "caption": f"Practical and brand-safe tips for {topic}.",
            "hashtags": ["marketing", "content", "socialmedia"],
            "cta": {"text": "Save for later", "placement": "end"},
            "estimated_duration_seconds": 12,
            "visual_direction": {"pacing": "medium", "transitions": "cut", "color_usage": "clean"},
        }

    def moderate_content(self, payload: dict, content_type: str, topic: str) -> tuple[dict, dict]:
        moderated = copy.deepcopy(payload if isinstance(payload, dict) else {"ideas": []})
        ideas = moderated.get("ideas", [])
        if not isinstance(ideas, list):
            ideas = []
            moderated["ideas"] = ideas

        report = {
            "total_ideas": len(ideas),
            "sanitized_count": 0,
            "replaced_count": 0,
            "issues": [],
            "status": "passed",
        }

        for idx, idea in enumerate(ideas):
            local_issues = []

            if content_type == "video":
                hook = idea.get("hook", {})
                if isinstance(hook, dict):
                    text, issues = self._sanitize_text(hook.get("text", ""))
                    hook["text"] = text
                    local_issues.extend([{"field": "hook.text", **i} for i in issues])
                caption, issues = self._sanitize_text(idea.get("caption", ""))
                idea["caption"] = caption
                local_issues.extend([{"field": "caption", **i} for i in issues])
                for scene_i, scene in enumerate(idea.get("script", []) or []):
                    voice, issues = self._sanitize_text(scene.get("voiceover", ""))
                    scene["voiceover"] = voice
                    local_issues.extend([{"field": f"script[{scene_i}].voiceover", **i} for i in issues])
                    visuals, issues = self._sanitize_text(scene.get("visuals", ""))
                    scene["visuals"] = visuals
                    local_issues.extend([{"field": f"script[{scene_i}].visuals", **i} for i in issues])
            else:
                hook, issues = self._sanitize_text(idea.get("hook", ""))
                idea["hook"] = hook
                local_issues.extend([{"field": "hook", **i} for i in issues])
                post_copy, issues = self._sanitize_text(idea.get("post_copy", ""))
                idea["post_copy"] = post_copy
                local_issues.extend([{"field": "post_copy", **i} for i in issues])

            idea["hashtags"] = self._normalize_hashtags(idea.get("hashtags", []))

            # Severe detection based on combined text.
            combined = " ".join(
                [
                    str(idea.get("hook", "")),
                    str(idea.get("post_copy", "")),
                    str(idea.get("caption", "")),
                ]
            )
            severity = self._scan_severity(combined)
            if severity == "high":
                report["replaced_count"] += 1
                ideas[idx] = self._safe_video_idea(topic, idx + 1) if content_type == "video" else self._safe_static_idea(topic, idx + 1)
                local_issues.append({"field": "idea", "issue": "replaced_for_compliance", "severity": "high"})
            elif local_issues:
                report["sanitized_count"] += 1

            if local_issues:
                report["issues"].append({"idea_index": idx, "details": local_issues})

        if report["replaced_count"] > 0:
            report["status"] = "adjusted"
        elif report["sanitized_count"] > 0:
            report["status"] = "sanitized"
        return moderated, report
