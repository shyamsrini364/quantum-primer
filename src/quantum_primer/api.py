import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from .config import Settings
from .models import Answer, Question
from .service import create_graph

SAMPLE_QUESTIONS = [
    {"category": "Start here", "question": "What is quantum biology in plain language?"},
    {"category": "Start here", "question": "Explain electron tunnelling for a complete beginner."},
    {"category": "Explore the books", "question": "How does Jack Kruse describe mitochondria?"},
    {"category": "Explore the books", "question": "What does the author mean by EZ water?"},
    {
        "category": "Connect ideas",
        "question": "How do these sources connect light and circadian rhythms?",
    },
]
DEMO_QUESTIONS = [
    {"category": "Demo", "question": q}
    for q in ["What is Quantum Primer?", "How do citations work?", "What is in the demo library?"]
]


def create_app(settings=None, graph=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if settings.mode == "live" and not settings.api_key.get_secret_value():
            raise ValueError("Set QP_API_KEY before running the live API")
        app.state.graph = graph or create_graph(settings)
        yield

    app = FastAPI(title="Quantum Primer", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def authorize(key=Depends(key_header)):
        expected = settings.api_key.get_secret_value()
        if expected and (not key or not secrets.compare_digest(key, expected)):
            raise HTTPException(status_code=401, detail="Invalid API key")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": settings.mode}

    @app.get("/sample-questions")
    def questions():
        return {"questions": DEMO_QUESTIONS if settings.mode == "demo" else SAMPLE_QUESTIONS}

    @app.post("/chat", response_model=Answer, dependencies=[Depends(authorize)])
    def ask(request: Question):
        try:
            return app.state.graph.invoke({"question": request.question})["response"]
        except Exception:
            # Avoid provider exceptions logging credentials, questions or private passages.
            logging.getLogger(__name__).error("Chat provider request failed")
            raise HTTPException(
                status_code=503, detail="Knowledge service unavailable. Please retry."
            ) from None

    return app


app = create_app()
