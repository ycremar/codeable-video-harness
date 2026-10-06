"""Contract validation, instrumented scene API and deterministic time math.

Python scene plugins are executable code, NOT sandboxed. Only load reviewed code.
This API does not pretend scene-supplied telemetry proves decoded visual semantics.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from dataclasses import dataclass, field
from PIL import Image, ImageDraw, ImageFont, ImageColor


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


def validate(s, root):
    if s.get("version") != 1:
        raise ValueError("Unsupported contract version")
    if s.get('backend','pillow') not in ('pillow','pdoom'):
        raise ValueError('Unknown renderer backend')
    if s.get('backend') == 'pdoom' and s.get('render',{}).get('samples',1) != 1:
        raise ValueError('pdoom primitive adapter currently supports one temporal sample only')
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
        if not contained(root, scene["module"]).is_file():
            raise ValueError("Missing scene module")
        end = b
    if abs(end-v["duration"]) > 1e-8:
        raise ValueError("Scene coverage must equal duration")
    if len(s["scenes"]) > 100:
        raise ValueError("Resource cap: 100 scenes")
    for asset in s.get("assets", []):
        if not asset.get("license") or not asset.get("source"):
            raise ValueError("Every asset needs source and license/rights provenance")
        if not contained(root, asset["path"]).is_file():
            raise ValueError(f"Missing asset: {asset['path']}")
    audio = s.get("audio", {"mode": "none"})
    if audio["mode"] not in ("none", "procedural", "file"):
        raise ValueError("Unknown audio mode")
    if audio["mode"] == "file":
        if audio["path"] not in [a["path"] for a in s.get("assets", [])]:
            raise ValueError("Audio file must be declared as a licensed asset")
    if audio["mode"] == "procedural":
        if not finite(audio.get("gain")) or not 0 <= audio["gain"] <= .9:
            raise ValueError("Procedural gain must be 0..0.9")
    timing = s.get("timing", {})
    if "bpm" in timing and (not finite(timing["bpm"]) or timing["bpm"] <= 0):
        raise ValueError("BPM must be positive")
    if not finite(timing.get("beat_offset", 0)):
        raise ValueError("Beat offset must be finite")
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
    excluded = {".git", "runs", ".venv", "__pycache__", "reference-inputs", "node_modules", "dist", "models"}
    files = {}
    for current,dirs,names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in excluded and not d.endswith('.egg-info'))
        for name in sorted(names):
            p=Path(current)/name
            if name == '.env' or p.suffix in ('.pyc','.zip','.bundle'):continue
            files[str(p.relative_to(root))]=digest(p)
    # Bind the executing harness too, even when an author project is staged elsewhere.
    implementation={};base=Path(__file__).resolve().parents[1]
    for folder in [base/'vch',base/'backends/pdoom']:
        if not folder.exists():continue
        for current,dirs,names in os.walk(folder):
            dirs[:]=sorted(d for d in dirs if d not in excluded)
            for name in sorted(names):
                p=Path(current)/name
                if p.suffix in ('.py','.ts','.json','.html'):implementation[str(p.relative_to(base))]=digest(p)
    return {"contract": hashlib.sha256(canonical(spec).encode()).hexdigest(), "files": files, 'implementation':implementation}


def luminance(color):
    rgb = ImageColor.getrgb(color)[:3]
    c = [v/255 for v in rgb]
    c = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in c]
    return .2126*c[0]+.7152*c[1]+.0722*c[2]


def contrast(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y+.05)/(x+.05)


def ease(p):
    p = min(1, max(0, p))
    return p*p*(3-2*p)


def noise(seed, key):
    """Stateless keyed randomness; never dependent on invocation order."""
    raw = hashlib.sha256(f"{seed}:{key}".encode()).digest()[:8]
    return int.from_bytes(raw, "big") / 2**64


@dataclass
class Frame:
    image: Image.Image
    elements: list = field(default_factory=list)


class Canvas:
    """Instrumented primitives; bounds are measured by the actual font rasterizer.

    Contrast is against the declared backing color, NOT arbitrary overlapping art.
    Declared telemetry is a proxy: decoded evidence still needs visual review.
    """
    def __init__(self, width, height, bg):
        self.image = Image.new("RGB", (width, height), bg)
        self.draw = ImageDraw.Draw(self.image)
        self.bg, self.elements = bg, []

    def text(self, element_id, xy, text, font_path, size, fill, background=None):
        font = ImageFont.truetype(str(font_path), size)
        bbox = self.draw.textbbox(xy, text, font=font, anchor="lt")
        self.draw.text(xy, text, font=font, anchor="lt", fill=fill)
        self.elements.append({"id": element_id, "type": "text", "text": text,
                              "bbox": list(bbox), "size": size,
                              "contrast": contrast(fill, background or self.bg)})

    def finish(self):
        return Frame(self.image, self.elements)


class SceneRenderer:
    def __init__(self, spec, root, trust_code=False):
        if not trust_code:
            raise PermissionError("Scene plugins execute Python. Review code and use --trust-scene-code.")
        self.spec, self.root, self.modules = spec, Path(root), {}
        for scene in spec["scenes"]:
            path = contained(root, scene["module"])
            if str(path) not in self.modules:
                ms = importlib.util.spec_from_file_location("vch_scene_"+digest(path)[:12], path)
                module = importlib.util.module_from_spec(ms)
                ms.loader.exec_module(module)
                self.modules[str(path)] = module

    def render(self, t):
        duration = self.spec["video"]["duration"]
        if not finite(t) or not 0 <= t < duration:
            raise ValueError("Timestamp outside [0,duration)")
        scene = next(x for x in self.spec["scenes"] if x["start"] <= t < x["end"])
        module = self.modules[str(contained(self.root, scene["module"]))]
        ctx = {"root": self.root, "spec": self.spec, "scene": scene, "t": t,
               "local_t": t-scene["start"], "progress": (t-scene["start"])/(scene["end"]-scene["start"]),
               "seed": self.spec["seed"]}
        result = module.render(ctx)
        w, h = self.spec["video"]["width"], self.spec["video"]["height"]
        if not isinstance(result, Frame) or result.image.size != (w, h) or result.image.mode != "RGB":
            raise ValueError("Scene must return Frame with contract-size RGB pixels")
        return result

    def sampled(self, t):
        import numpy as np
        settings, fps = self.spec.get("render", {}), self.spec["video"]["fps"]
        count = settings.get("samples", 1)
        if count == 1:
            return self.render(t)
        scene = next(x for x in self.spec["scenes"] if x["start"] <= t < x["end"])
        width = settings.get("shutter", .3)/fps
        frames = []
        for i in range(count):
            st = t + ((i+.5)/count-.5)*width
            st = min(scene["end"]-1e-9, max(scene["start"], st))
            srgb = np.asarray(self.render(st).image).astype(np.float32)/255
            # Average in linear light, not sRGB (which darkens blur).
            frames.append(np.where(srgb <= .04045, srgb/12.92, ((srgb+.055)/1.055)**2.4))
        linear = np.mean(frames, axis=0)
        srgb = np.where(linear <= .0031308, linear*12.92, 1.055*linear**(1/2.4)-.055)
        image = Image.fromarray(np.clip(np.rint(srgb*255), 0, 255).astype('uint8'))
        return Frame(image, self.render(t).elements)
