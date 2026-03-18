import json
from pathlib import Path


class DataLoader:
    def load_competitor_posts(
        self,
        path: str = "data/competitor_posts.json",
        platform: str = None,
        limit: int = 50,
    ) -> list[dict]:
        """Load and optionally filter competitor posts."""
        file_path = Path(path)
        if not file_path.exists():
            return []

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
        except Exception:
            return []

        if platform:
            data = [p for p in data if str(p.get("platform", "")).lower() == platform.lower()]

        return data[: max(limit, 0)]

    def load_trends(
        self,
        path: str = "data/trends.json",
        platform: str = None,
        niche: str = None,
        limit: int = 30,
    ) -> list[dict]:
        """Load and optionally filter trend data."""
        file_path = Path(path)
        if not file_path.exists():
            return []

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
        except Exception:
            return []

        if platform:
            data = [t for t in data if str(t.get("platform", "")).lower() == platform.lower()]

        if niche:
            data = [t for t in data if str(t.get("niche", "")).lower() == niche.lower()]

        return data[: max(limit, 0)]
