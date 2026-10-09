"""Renderer selection. The html backend is the only renderer: a composition that draws any moment from t."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .html_backend import HtmlRenderer


def create_renderer(spec: dict[str, Any], root: Path, trust_code: bool = False) -> HtmlRenderer:
    if spec.get("backend") != "html":
        raise ValueError(f"Unknown backend: {spec.get('backend')}")
    return HtmlRenderer(spec, root, trust_code)
