"""Contract validation, provenance hashing and deterministic time math.

A contract freezes what a film must satisfy before anything is rendered. Compositions are
agent-written HTML/JS that the html backend executes in Chromium; nothing here prescribes how a
film looks or sounds.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
import numpy as np
from PIL import Image

BACKENDS = ("html",)
# "composition": the composition synthesizes its own audio in code (window.__vch.audio).
AUDIO_MODES = ("none", "file", "mix", "composition")
MAX_HITS = 2000
MAX_LABEL_CHARS = 80
MAX_STYLE_BYTES = 64 * 1024
STYLE_MODES = ("dark", "light")
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Files that carry third-party rights when they sit inside an HTML composition folder.
COMPOSITION_MEDIA_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".ico",
    ".ttf", ".otf", ".woff", ".woff2",
    ".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".mp4", ".webm", ".mov",
    ".glb", ".gltf", ".bin", ".hdr", ".exr", ".ktx2", ".lottie",
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def contained(root, relative):
    root = Path(root).resolve()
    p = (root / relative).resolve()
    if not p.is_relative_to(root):
        raise ValueError(f"Path escapes project: {relative}")
    return p


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def normalized_hits(timing):
    """Declared sync points as [{'t': seconds, 'cue': name or None, 'kind': label or None}], sorted by time.

    A hit marks a moment that must carry an audible transient. Its name and label are the author's;
    the harness attaches no sound to them.
    """
    hits = []
    for hit in timing.get("hits", []):
        if isinstance(hit, dict):
            hits.append({"t": hit.get("t"), "cue": hit.get("cue"), "kind": hit.get("kind")})
        else:
            hits.append({"t": hit, "cue": None, "kind": None})
    return sorted(hits, key=lambda h: h["t"] if finite(h["t"]) else math.inf)


def _validate_hits(timing, duration):
    raw = timing.get("hits", [])
    if not isinstance(raw, list) or len(raw) > MAX_HITS:
        raise ValueError(f"timing.hits must be a list of at most {MAX_HITS} entries")
    names = set()
    for hit in normalized_hits(timing):
        if not finite(hit["t"]) or not 0 <= hit["t"] < duration:
            raise ValueError("Every timing hit needs a finite time inside [0, duration)")
        for key in ("cue", "kind"):
            if hit[key] is not None and (not isinstance(hit[key], str) or not 0 < len(hit[key]) <= MAX_LABEL_CHARS):
                raise ValueError(f"timing.hits {key} must be a short string")
        if hit["cue"] is not None:
            if hit["cue"] in names:
                raise ValueError(f"Duplicate cue name: {hit['cue']}")
            names.add(hit["cue"])


def _validate_mastering(audio):
    target = audio.get("loudness_target")
    if target is not None and (not finite(target) or not -40 <= target <= -5):
        raise ValueError("audio.loudness_target must be -40..-5 LUFS")
    ceiling = audio.get("peak_ceiling_dbfs", -1.0)
    if not finite(ceiling) or not -20 <= ceiling <= 0:
        raise ValueError("audio.peak_ceiling_dbfs must be -20..0")


def _validate_audio(audio, assets, duration):
    declared = {a["path"] for a in assets}
    mode = audio["mode"]
    if mode not in AUDIO_MODES:
        raise ValueError(f"audio.mode must be one of {', '.join(AUDIO_MODES)}")
    if mode == "file" and audio["path"] not in declared:
        raise ValueError("Audio file must be declared as a licensed asset")
    if mode == "mix":
        layers = audio.get("layers", [])
        if not isinstance(layers, list) or not layers:
            raise ValueError("Mix audio needs at least one layer")
        for layer in layers:
            if layer.get("path") not in declared:
                raise ValueError("Every mix layer must be a declared, licensed asset")
            if not finite(layer.get("at", 0)) or not -600 <= layer.get("at", 0) < duration:
                raise ValueError("Mix layer 'at' must be finite and before the end of the video")
            if layer.get("align", "start") not in ("start", "peak"):
                raise ValueError("Mix layer align must be 'start' or 'peak'")
            if not finite(layer.get("gain_db", 0)) or not -60 <= layer.get("gain_db", 0) <= 12:
                raise ValueError("Mix layer gain_db must be -60..12")
    if mode in ("mix", "composition"):
        _validate_mastering(audio)


def composition_media(folder):
    """Relative paths of rights-bearing files inside an HTML composition folder."""
    return sorted(p for p in Path(folder).rglob("*")
                  if p.is_file() and p.suffix.lower() in COMPOSITION_MEDIA_SUFFIXES)


def _validate_html(s, root):
    entry = s.get("html", {}).get("entry")
    if not isinstance(entry, str) or not entry.endswith(".html"):
        raise ValueError("html.entry must be a project-relative .html file")
    path = contained(root, entry)
    if not path.is_file():
        raise ValueError(f"Missing html.entry: {entry}")
    if path.parent == Path(root).resolve():
        raise ValueError("Place the HTML composition in its own folder; the project root is never served")
    if any(part.startswith(".") for part in path.relative_to(Path(root).resolve()).parts):
        raise ValueError("Hidden folders are never served")
    declared = {a["path"] for a in s.get("assets", [])}
    for media in composition_media(path.parent):
        rel = str(media.relative_to(Path(root).resolve()))
        if rel not in declared:
            raise ValueError(f"Undeclared media in composition: {rel}; add source and license to assets")


def _check_style_colors(value, where="style"):
    if isinstance(value, dict):
        for key, item in value.items():
            _check_style_colors(item, f"{where}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_style_colors(item, f"{where}[{i}]")
    elif isinstance(value, str) and value.startswith("#") and not HEX_COLOR.match(value):
        raise ValueError(f"{where}: colours must be #RRGGBB")


def resolve_style(style, root):
    """A style pack (design tokens) as an object; a project-relative .json path is loaded and inlined.

    Inlining puts the tokens into the run's contract.json, so the style a run used is part of its record.
    """
    if isinstance(style, str):
        path = contained(root, style)
        if path.suffix != ".json" or not path.is_file():
            raise ValueError("style must be an object or a project-relative .json file")
        if path.stat().st_size > MAX_STYLE_BYTES:
            raise ValueError("Style pack too large")
        style = {**json.loads(path.read_text()), "source": Path(style).as_posix()}
    if not isinstance(style, dict):
        raise ValueError("style must be a JSON object")
    if style.get("mode", "dark") not in STYLE_MODES:
        raise ValueError("style.mode must be dark or light")
    _check_style_colors(style)
    return style


def validate(s, root):
    if s.get("version") != 1:
        raise ValueError("Unsupported contract version")
    if "style" in s:
        s["style"] = resolve_style(s["style"], root)
    if s.get("backend") not in BACKENDS:
        raise ValueError("backend must be 'html': a composition that renders any moment from t")
    v = s["video"]
    for k in ("width", "height", "fps"):
        if type(v[k]) is not int or v[k] <= 0:
            raise ValueError(f"video.{k} must be a positive integer")
    if v["width"] % 2 or v["height"] % 2:
        raise ValueError("H.264 yuv420p requires even width and height")
    if max(v["width"], v["height"]) > 4096 or v["fps"] > 120:
        raise ValueError("Resource cap: max 4096px / 120fps")
    if not finite(v["duration"]) or not 0 < v["duration"] <= 600:
        raise ValueError("Duration must be finite, >0 and <=600 seconds")
    n = v["duration"] * v["fps"]
    if abs(n - round(n)) > 1e-7:
        raise ValueError("Duration must be an integer number of frames")
    if type(s.get("seed")) is not int:
        raise ValueError("An explicit integer seed is required")
    if not s.get("requirements"):
        raise ValueError("At least one requirement is required")
    ids = set()
    for req in s["requirements"]:
        if not req.get("id") or req["id"] in ids:
            raise ValueError("Requirement IDs must be nonempty and unique")
        ids.add(req["id"])
        if not req.get("description") or req.get("kind") not in ("hard", "proxy", "human"):
            raise ValueError("Requirement needs description and kind: hard/proxy/human")
        if req["kind"] == "human":
            if not req.get("rubric"):
                raise ValueError("Human review requires a concrete rubric")
        elif not req.get("metric") or req.get("op") not in ("eq", "le", "ge") or "target" not in req:
            raise ValueError("Machine requirement needs metric, op and target")
        elif type(req["target"]) in (int, float) and not finite(req["target"]):
            raise ValueError("Requirement targets must be finite")
    end, scene_ids = 0., set()
    for scene in s["scenes"]:
        if scene["id"] in scene_ids:
            raise ValueError("Duplicate scene ID")
        scene_ids.add(scene["id"])
        a, b = scene["start"], scene["end"]
        if not finite(a) or not finite(b) or abs(a-end) > 1e-8 or b <= a:
            raise ValueError("Scenes must be ordered, contiguous and non-overlapping")
        for t in (a, b):
            if abs(t*v["fps"] - round(t*v["fps"])) > 1e-7:
                raise ValueError("Scene boundaries must fall on frame boundaries")
        end = b
    if abs(end-v["duration"]) > 1e-8:
        raise ValueError("Scene coverage must equal duration")
    if len(s["scenes"]) > 100:
        raise ValueError("Resource cap: 100 scenes")
    for asset in s.get("assets", []):
        if not asset.get("license") or not asset.get("source"):
            raise ValueError("Every asset needs source and license/rights provenance")
        # A path ending in "/" declares a whole folder (a vendored library) under one licence record.
        folder = asset["path"].endswith("/")
        if any(part.startswith(".") for part in Path(asset["path"]).parts):
            raise ValueError(f"Hidden asset paths are never served: {asset['path']}")
        target = contained(root, asset["path"])
        if not (target.is_dir() if folder else target.is_file()):
            raise ValueError(f"Missing asset: {asset['path']}")
    _validate_audio(s.get("audio", {"mode": "none"}), s.get("assets", []), v["duration"])
    timing = s.get("timing", {})
    if "bpm" in timing and (not finite(timing["bpm"]) or timing["bpm"] <= 0):
        raise ValueError("BPM must be positive")
    if not finite(timing.get("beat_offset", 0)):
        raise ValueError("Beat offset must be finite")
    _validate_hits(timing, v["duration"])
    _validate_html(s, root)
    interval = s.get("qa", {}).get("sample_every", 1.)
    if not finite(interval) or interval < 1/v["fps"]:
        raise ValueError("QA sample interval must be finite and at least one frame")
    samples = s.get("render", {}).get("samples", 1)
    if type(samples) is not int or not 1 <= samples <= 16:
        raise ValueError("Motion samples must be 1..16")
    shutter = s.get("render", {}).get("shutter", .3)
    if not finite(shutter) or not 0 <= shutter <= 1:
        raise ValueError("Shutter fraction must be 0..1")
    return s


def load_contract(path):
    p = Path(path).resolve()
    s = json.loads(p.read_text())
    root = p.parent.parent if p.parent.name == "examples" else p.parent
    return validate(s, root), root


def source_manifest(root, spec):
    # Hash all project code/prompts/assets, not only imported entry points.
    # No secrets or source bytes are copied into the report.
    excluded = {".git", "runs", ".venv", "__pycache__", "node_modules", "dist"}
    files = {}
    for current,dirs,names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in excluded and not d.endswith('.egg-info'))
        for name in sorted(names):
            p=Path(current)/name
            if name == '.env' or p.suffix in ('.pyc','.zip','.bundle'):continue
            files[str(p.relative_to(root))]=digest(p)
    # Bind the executing harness too, even when an author project is staged elsewhere.
    implementation={};base=Path(__file__).resolve().parents[1]
    for folder in [base/'vch']:
        for current,dirs,names in os.walk(folder):
            dirs[:]=sorted(d for d in dirs if d not in excluded)
            for name in sorted(names):
                p=Path(current)/name
                if p.suffix in ('.py','.js','.json','.html'):implementation[str(p.relative_to(base))]=digest(p)
    return {"contract": hashlib.sha256(canonical(spec).encode()).hexdigest(), "files": files, 'implementation':implementation}


def contrast_rgb(a, b):
    """WCAG contrast of two 0..255 RGB triples (floats allowed for blended colors)."""
    def lum(rgb):
        c = [v/255 for v in rgb]
        c = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in c]
        return .2126*c[0]+.7152*c[1]+.0722*c[2]
    x, y = sorted((lum(a), lum(b)))
    return (y+.05)/(x+.05)


def temporal_average(render_at, t, scene, settings, fps):
    """Average fixed sub-frame samples in linear light, clipped to the scene window."""
    count = settings.get("samples", 1)
    width = settings.get("shutter", .3)/fps
    frames = []
    for i in range(count):
        st = t + ((i+.5)/count-.5)*width
        st = min(scene["end"]-1e-9, max(scene["start"], st))
        srgb = np.asarray(render_at(st)).astype(np.float32)/255
        # Average in linear light, not sRGB (which darkens blur).
        frames.append(np.where(srgb <= .04045, srgb/12.92, ((srgb+.055)/1.055)**2.4))
    linear = np.mean(frames, axis=0)
    srgb = np.where(linear <= .0031308, linear*12.92, 1.055*linear**(1/2.4)-.055)
    return Image.fromarray(np.clip(np.rint(srgb*255), 0, 255).astype('uint8'))


@dataclass
class Frame:
    image: Image.Image
    elements: list = field(default_factory=list)
