"""Vercel ASGI entrypoint; the same service is used by the local website."""

from src.quantum_primer.website import app

__all__ = ["app"]
