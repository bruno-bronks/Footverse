"""Camada HTTP (FastAPI) — casca fina sobre o facade `World`."""

from .app import create_app

__all__ = ["create_app"]
