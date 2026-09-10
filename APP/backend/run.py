"""Arranque local: uvicorn baliza.main:app --reload --app-dir backend."""

from baliza.main import app

__all__ = ["app"]
