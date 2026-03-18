from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.orchestrator import Orchestrator

app = FastAPI(title="Content Factory Portal", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _normalize_platforms(platforms: list[str]) -> list[str]:
    allowed = {"Instagram", "TikTok", "LinkedIn", "Twitter/X", "Facebook"}
    normalized = [p for p in platforms if p in allowed]
    return normalized or ["Instagram", "LinkedIn"]


def _derive_niche(topic: str) -> str:
    text = (topic or "").lower()
    if any(k in text for k in ["ai", "ml", "llm", "tech", "software"]):
        return "tech"
    if any(k in text for k in ["fashion", "beauty"]):
        return "fashion/beauty"
    if any(k in text for k in ["fitness", "workout", "gym"]):
        return "fitness"
    if any(k in text for k in ["food", "recipe", "meal"]):
        return "food"
    return "marketing"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "defaults": {
                "topic": "AI content strategy",
                "language": "English",
                "content_type": "static",
                "number_idea": 3,
                "brand_color": "#3B82F6",
                "platforms": ["Instagram", "LinkedIn"],
                "llm_provider": "google",
                "llm_model": "gemini-2.5-flash",
                "llm_api_key": "",
            },
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    topic: str = Form(...),
    platforms: list[str] = Form(default=[]),
    content_type: str = Form("static"),
    language: str = Form("English"),
    number_idea: int = Form(3),
    brand_color: str = Form("#3B82F6"),
    competitor_urls: str = Form(""),
    llm_provider: str = Form("google"),
    llm_model: str = Form("gemini-2.5-flash"),
    llm_api_key: str = Form(""),
):
    selected_platforms = _normalize_platforms(platforms)
    urls = [u.strip() for u in competitor_urls.splitlines() if u.strip()]
    niche = _derive_niche(topic)

    try:
        result = Orchestrator().run(
            topic=topic,
            platforms=selected_platforms,
            content_type=content_type,
            language=language,
            brand_color=[brand_color],
            brand_img=None,
            number_idea=max(1, min(5, int(number_idea))),
            competitor_urls=urls,
            niche=niche,
            output_dir="output_posts",
            image_url="",
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key=llm_api_key or None,
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "error": str(exc),
                "result": {},
                "selected_platforms": selected_platforms,
            },
            status_code=500,
        )

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "result": result,
            "selected_platforms": selected_platforms,
            "topic": topic,
            "content_type": content_type,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
