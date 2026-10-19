"""Website service. Provider credentials and library passages stay in Python."""

import json
import os
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .models import Answer, Question
from .service import create_graph

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


def create_website(settings=None, graph=None):
    settings = settings or Settings(_env_file=ROOT / ".env")
    if not settings.manifest_path.is_absolute():
        settings = settings.model_copy(update={"manifest_path": ROOT / settings.manifest_path})
    app = FastAPI(title="Quantum Primer website", docs_url=None, redoc_url=None)
    allowed_hosts = ["127.0.0.1", "localhost", "[::1]"]
    # Vercel provides these server-side values for the current deployment/project.
    if os.environ.get("VERCEL") == "1":
        allowed_hosts.extend(filter(None, [os.environ.get("VERCEL_URL"),
                                          os.environ.get("VERCEL_PROJECT_PRODUCTION_URL"),
                                          os.environ.get("VERCEL_BRANCH_URL")]))
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.state.graph = graph
    graph_lock = Lock()

    @app.get("/")
    def home():
        return FileResponse(WEB / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": settings.mode}

    @app.get("/api/library")
    def library():
        try:
            manifest = json.loads(settings.manifest_path.read_text(encoding="utf-8"))
            sources = {}
            for chunk in manifest["chunks"]:
                sources.setdefault(chunk["source_id"], {
                    "id": chunk["source_id"], "title": chunk["title"], "author": chunk["author"]
                })
            return {"sources": list(sources.values()), "mode": settings.mode}
        except (OSError, ValueError, KeyError):
            raise HTTPException(503, "The library is temporarily unavailable. Please try again.") from None

    @app.post("/api/ask", response_model=Answer)
    def ask(question: Question, request: Request):
        # Browser requests must originate from this website.
        origin = request.headers.get("origin")
        if (origin and origin.rstrip("/") != str(request.base_url).rstrip("/")) or (
            request.headers.get("sec-fetch-site") == "cross-site"
        ):
            raise HTTPException(403, "Open the assistant from this website.")
        if not request.headers.get("content-type", "").startswith("application/json"):
            raise HTTPException(415, "Send a JSON question.")
        try:
            with graph_lock:
                if app.state.graph is None:
                    app.state.graph = create_graph(settings)
            return app.state.graph.invoke({"question": question.question})["response"]
        except Exception:
            raise HTTPException(
                503, "The library couldn't be reached. Please try again in a moment."
            ) from None

    app.mount("/assets", StaticFiles(directory=WEB), name="website-assets")
    return app


app = create_website()
