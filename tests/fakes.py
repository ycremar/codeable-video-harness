"""Browser-free stand-ins for the html renderer, so the evidence pipeline can be tested without Chromium.

A FakeRenderer draws frames from a Python function of t and can return synthesized samples the way a
composition's window.__vch.audio does. The test signals here are fixtures, not sounds for films.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw

from vch.core import Frame

PLACEHOLDER_HTML = "<!doctype html><title>fixture</title>"
CLICK_HZ = 3000
CLICK_DECAY = 400


class FakeRenderer:
    def __init__(self, draw: Callable[[float], Image.Image], *, elements: Callable[[float], list] | None = None,
                 audio: Callable[[int], np.ndarray] | None = None):
        self.draw = draw
        self.elements = elements or (lambda t: [])
        self.synthesize = audio
        self.provenance = {"name": "fake-renderer (tests)"}

    def sampled(self, t: float) -> Frame:
        return Frame(self.draw(t), self.elements(t))

    def audio(self, rate: int) -> np.ndarray:
        if self.synthesize is None:
            raise ValueError("fixture renderer has no audio")
        return self.synthesize(rate)

    def close(self) -> None:
        pass


def html_project(root: Path) -> dict:
    """Contract fields for a minimal html project in `root` (a placeholder composition, so contracts validate)."""
    (root / "comp").mkdir(parents=True, exist_ok=True)
    (root / "comp/index.html").write_text(PLACEHOLDER_HTML)
    return {"backend": "html", "html": {"entry": "comp/index.html"}}


def moving_disc(*, size: int = 96, background: str = "#CCCCCC", color: str = "#2255AA", speed: float = 10) -> Callable:
    def draw(t: float) -> Image.Image:
        image = Image.new("RGB", (size, size), background)
        x = 20 + t * speed
        ImageDraw.Draw(image).ellipse((x, 20, x + 20, 40), fill=color)
        return image
    return draw


def click(rate: int) -> np.ndarray:
    """A 20 ms decaying 3 kHz burst whose loudest sample is its first quarter period."""
    t = np.arange(int(0.02 * rate)) / rate
    return np.sin(2 * np.pi * CLICK_HZ * t) * np.exp(-t * CLICK_DECAY)


def clicks(*, times: list[float], duration: float, level: float = 0.5, bed: float = 0.0) -> Callable[[int], np.ndarray]:
    """Composition-style audio: clicks at `times` over an optional quiet 220 Hz bed, as (frames, 2) samples."""
    def synthesize(rate: int) -> np.ndarray:
        n = round(rate * duration)
        signal = bed * np.sin(2 * np.pi * 220 * np.arange(n) / rate)
        burst = click(rate)
        for t in times:
            start = round(t * rate)
            end = min(n, start + len(burst))
            signal[start:end] += level * burst[:end - start]
        return np.stack([signal, signal], axis=1)
    return synthesize
