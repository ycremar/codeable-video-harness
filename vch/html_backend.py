"""HTML composition backend: agent-written HTML/CSS/SVG/Canvas/WebGL rendered as f(t).

This mirrors how most code-rendered launch films are made (a page exposing a pure
`seek(t)`, captured frame by frame in headless Chromium, then encoded by FFmpeg)
while keeping this harness's evidence model: exact seek checks, visible-text
telemetry, encoded-output QA and artifact-bound review.

Composition JavaScript runs inside Chromium, not Python. Chromium's own sandbox is
enabled unless VCH_CHROMIUM_NO_SANDBOX=1 (some root containers need that). Only
the composition folder and declared assets are served on loopback; DNS for any
other host fails, other requests are aborted, and any attempt blocks the render.
This is defence in depth, not an OS-level sandbox for untrusted code.
"""
from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import numpy as np
from PIL import Image

from .core import Frame, contained, contrast_rgb, finite, temporal_average

RUNTIME = Path(__file__).with_name("html_runtime.js")
PAGE_TIMEOUT_MS = 60000
# Playwright's own screenshot hid text carets; keep that so a focused field never blinks into a frame.
HIDE_CARET_CSS = "* { caret-color: transparent !important; }"
TEXT_COLOR_TOLERANCE = 60.0
MIN_BACKING_FRACTION = 0.15
CHROMIUM_ARGS = [
    "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
    "--proxy-server=http://127.0.0.1:9",
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--disable-background-networking", "--no-pings", "--font-render-hinting=none",
    # Partial re-raster makes antialiasing at clip edges depend on the previously drawn frame.
    "--disable-partial-raster",
    # GPU-rasterised 2D canvas caches paths: a page's first draw of a shape can differ from later draws.
    "--disable-accelerated-2d-canvas",
]
EXTRA_TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm",
               ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".woff2": "font/woff2"}


def text_contrast(rgb: np.ndarray, element: dict[str, Any]) -> float | None:
    """Contrast of the rendered text colour against the median non-text pixel inside its box."""
    color = element.get("color")
    if not color or color[3] < 0.05:
        return None
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = (int(round(v)) for v in element["bbox"])
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 1 or y1 - y0 < 1:
        return None
    pixels = rgb[y0:y1, x0:x1].reshape(-1, 3).astype(np.float64)
    # What the viewer sees this frame: colour alpha times inherited opacity.
    alpha = color[3] * element.get("opacity", 1)
    ink = np.array(color[:3], dtype=np.float64)
    backing = np.median(pixels, axis=0)
    for _ in range(2):
        rendered = alpha * ink + (1 - alpha) * backing
        far = pixels[np.linalg.norm(pixels - rendered, axis=1) > TEXT_COLOR_TOLERANCE]
        if len(far) < MIN_BACKING_FRACTION * len(pixels):
            backing = rendered
            break
        backing = np.median(far, axis=0)
    rendered = alpha * ink + (1 - alpha) * backing
    return round(contrast_rgb(rendered, backing), 4)


class _Server:
    """Loopback server for the composition folder, declared assets and the contract."""

    def __init__(self, *, spec: dict[str, Any], root: Path, folder: Path):
        self.missing: list[str] = []
        allowed = {a["path"] for a in spec.get("assets", [])}
        contract = json.dumps(spec, ensure_ascii=False).encode()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(handler):
                route = unquote(urlparse(handler.path).path).lstrip("/")
                if route == "favicon.ico":  # requested by the browser itself, not the composition
                    handler.send_error(404)
                    return
                try:
                    if route == "contract.json":
                        payload, mime = contract, "application/json"
                    else:
                        path = contained(root, route)
                        hidden = any(part.startswith(".") for part in Path(route).parts)
                        inside = path.is_relative_to(folder)
                        if hidden or not path.is_file() or not (inside or route in allowed):
                            raise FileNotFoundError(route)
                        payload = path.read_bytes()
                        mime = EXTRA_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                except (OSError, ValueError):
                    server.missing.append("/" + route)
                    handler.send_error(404)
                    return
                handler.send_payload(payload, mime)

            def send_payload(handler, payload: bytes, mime: str):
                start, end = 0, len(payload) - 1
                ranged = handler.headers.get("Range", "")
                if ranged.startswith("bytes="):
                    first, _, last = ranged[6:].partition("-")
                    start = int(first) if first else max(0, len(payload) - int(last))
                    end = int(last) if first and last else end
                    handler.send_response(206)
                    handler.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
                else:
                    handler.send_response(200)
                handler.send_header("Content-Type", mime)
                handler.send_header("Accept-Ranges", "bytes")
                handler.send_header("Content-Length", str(end - start + 1))
                handler.send_header("Cache-Control", "no-store")
                handler.end_headers()
                handler.wfile.write(payload[start:end + 1])

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.origin = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class HtmlRenderer:
    def __init__(self, spec: dict[str, Any], root: Path, trust_code: bool = False):
        if not trust_code:
            raise PermissionError("HTML compositions execute JavaScript. Review it and pass --trust-scene-code")
        from playwright.sync_api import Error as PlaywrightError, sync_playwright  # optional dependency
        self.PlaywrightError = PlaywrightError
        self.spec, self.root = spec, Path(root).resolve()
        entry = contained(self.root, spec["html"]["entry"])
        self.entry = entry.relative_to(self.root).as_posix()
        self.blocked: list[str] = []
        self.errors: list[str] = []
        self.server = _Server(spec=spec, root=self.root, folder=entry.parent)
        self.pw = self.browser = None
        try:
            self._launch(sync_playwright)
        except BaseException:
            self.close()
            raise

    def _launch(self, sync_playwright) -> None:
        v = self.spec["video"]
        sandbox = os.environ.get("VCH_CHROMIUM_NO_SANDBOX") != "1"
        config = {"seed": self.spec["seed"], "fps": v["fps"], "width": v["width"], "height": v["height"],
                  "duration": v["duration"]}
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True, chromium_sandbox=sandbox, args=CHROMIUM_ARGS)
        context = self.browser.new_context(viewport={"width": v["width"], "height": v["height"]},
                                           device_scale_factor=1, service_workers="block", locale="en-US",
                                           timezone_id="UTC", color_scheme="light", reduced_motion="no-preference")
        context.add_init_script(script=RUNTIME.read_text().replace("__VCH_CONFIG__", json.dumps(config)))
        context.route("**/*", self._route)
        self.page = context.new_page()
        self.page.set_default_timeout(PAGE_TIMEOUT_MS)
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.goto(f"{self.server.origin}/{self.entry}", wait_until="load")
        self.page.add_style_tag(content=HIDE_CARET_CSS)
        self.cdp = context.new_cdp_session(self.page)
        # Load every declared font face up front so no frame renders with a fallback font.
        self.page.evaluate("() => Promise.all([...document.fonts].map((f) => f.load().catch(() => null)))")
        self.page.evaluate("() => document.fonts.ready.then(() => true)")
        self._raise_problems()
        self.provenance = {
            "name": "html-composition / Playwright Chromium", "browser": self.browser.version,
            "entry": self.entry, "temporal_samples": self.spec.get("render", {}).get("samples", 1),
            "chromium_sandbox": sandbox, "network": "loopback composition folder + declared assets only",
            "clock": "virtual: performance.now, Date and rAF timestamps equal composition time",
            "randomness": "Math.random seeded per page load; use __vch.noise(key) inside seek",
            "telemetry": "visible DOM/SVG text nodes (+ data-vch-id text groups); contrast = rendered text colour vs median backing pixels in its box; canvas/WebGL text needs __vch.elements",
            "adapters": ["window.__vch.seek | window.seek", "window.__timelines (paused)", "document.getAnimations()"],
        }

    def _route(self, route) -> None:
        if route.request.url.startswith(self.server.origin + "/"):
            route.continue_()
        else:
            self.blocked.append(route.request.url)
            route.abort("blockedbyclient")

    def _raise_problems(self) -> None:
        if self.blocked:
            raise ValueError("Composition requested non-local resources (package them locally): "
                             + ", ".join(sorted(set(self.blocked))[:10]))
        if self.server.missing:
            raise ValueError("Composition requested files that are missing or outside its folder/declared assets: "
                             + ", ".join(sorted(set(self.server.missing))[:10]))
        if self.errors:
            raise RuntimeError("Browser page error: " + "; ".join(self.errors[:5]))

    def _seek(self, t: float) -> list[dict[str, Any]]:
        try:
            result = self.page.evaluate("(t) => window.__vchHarness.frame(t)", t)
        except self.PlaywrightError as exc:
            raise RuntimeError(f"Composition seek failed at t={t:.4f}s: {exc}") from exc
        self._raise_problems()
        return result["elements"]

    def _capture(self) -> Image.Image:
        # Lossless PNG with Chromium's fast zlib settings: pixel-identical to page.screenshot, about 2.5x faster.
        v = self.spec["video"]
        clip = {"x": 0, "y": 0, "width": v["width"], "height": v["height"], "scale": 1}
        shot = self.cdp.send("Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True, "clip": clip})
        return Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")

    def _with_contrast(self, image: Image.Image, elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rgb = np.asarray(image)
        for e in elements:
            if e.get("source") == "dom":
                e["contrast"] = text_contrast(rgb, e)
        return elements

    def render(self, t: float) -> Frame:
        if not finite(t) or not 0 <= t < self.spec["video"]["duration"]:
            raise ValueError("Timestamp out of range")
        elements = self._seek(t)
        image = self._capture()
        return Frame(image, self._with_contrast(image, elements))

    def sampled(self, t: float) -> Frame:
        settings, fps = self.spec.get("render", {}), self.spec["video"]["fps"]
        if settings.get("samples", 1) == 1:
            return self.render(t)
        scene = next(x for x in self.spec["scenes"] if x["start"] <= t < x["end"])

        def at(st: float) -> Image.Image:
            self._seek(st)
            return self._capture()
        image = temporal_average(at, t, scene, settings, fps)
        return Frame(image, self._with_contrast(image, self._seek(t)))

    def close(self) -> None:
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.pw:
            self.pw.stop()
            self.pw = None
        if getattr(self, "server", None):
            self.server.close()
            self.server = None
