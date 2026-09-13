"""Arranque: uvicorn caleta.main:app --app-dir backend --port 8010."""

from caleta.main import app

__all__ = ["app"]
