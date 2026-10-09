"""Audio for a run: composition-authored synthesis, licensed layers, mastering. No built-in sounds.

The harness ships no sound palette. A film's sound is either synthesized by the composition itself
(`audio.mode: "composition"`, see `window.__vch.audio` in docs/AUTHORING.md), mixed from declared,
licensed files (`mix`), or one declared file (`file`). The harness only places layers, applies one
linear loudness gain under a peak ceiling, writes the WAV and measures the encoded result. There is
no compressor or limiter, so a ceiling can stop a loudness target from being reached; that is
reported, never hidden.
"""
from __future__ import annotations

import hashlib
import math
import subprocess
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .core import contained, digest
from .signals import loudness_of_samples

SAMPLE_RATE = 48000
DEFAULT_CEILING_DBFS = -1.0
DECODE_TIMEOUT_S = 300


def place(track: np.ndarray, clip: np.ndarray, *, at: float, align: str, rate: int = SAMPLE_RATE) -> dict[str, float]:
    """Add clip into track so its start (or measured peak) lands on `at` seconds."""
    mono = clip if clip.ndim == 1 else np.max(np.abs(clip), axis=1)
    peak_offset = int(np.argmax(np.abs(mono))) if align == "peak" else 0
    start = round(at * rate) - peak_offset
    a, b = max(0, start), min(len(track), start + len(clip))
    if b > a:
        track[a:b] += clip[a - start:b - start]
    return {"at": at, "align": align, "peak_offset_s": round(peak_offset / rate, 6),
            "start_s": round(start / rate, 6), "clipped": bool(start < 0 or start + len(clip) > len(track))}


def decode_layer(path: Path, *, rate: int = SAMPLE_RATE) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "2", "-ar", str(rate),
                          "-f", "f32le", "-"], check=True, capture_output=True, timeout=DECODE_TIMEOUT_S).stdout
    data = np.frombuffer(out, dtype="<f4").astype(np.float64)
    if not len(data):
        raise ValueError(f"Audio layer decoded to no samples: {path}")
    return data.reshape(-1, 2)


def master(signal: np.ndarray, *, target: float | None, ceiling_dbfs: float,
           rate: int = SAMPLE_RATE) -> tuple[np.ndarray, dict[str, Any]]:
    """Optional linear loudness gain toward `target` LUFS, never exceeding the sample-peak ceiling."""
    peak = float(np.max(np.abs(signal))) if len(signal) else 0.0
    report: dict[str, Any] = {"target_lufs": target, "ceiling_dbfs": ceiling_dbfs}
    if target is None or peak <= 0:
        report["gain_db"] = 0.0
        return signal, report
    measured = loudness_of_samples(signal.astype(np.float32), rate=rate)["integrated_lufs"]
    if measured is None:
        raise ValueError("Mix is too quiet or short to measure integrated loudness")
    gain_db = target - measured
    ceiling_gain_db = ceiling_dbfs - 20 * math.log10(peak)
    limited = gain_db > ceiling_gain_db
    gain_db = min(gain_db, ceiling_gain_db)
    report.update(measured_lufs_before=measured, gain_db=round(gain_db, 3), limited_by_ceiling=limited)
    return signal * 10 ** (gain_db / 20), report


def write_wav(path: Path, signal: np.ndarray, *, rate: int = SAMPLE_RATE) -> None:
    channels = 1 if signal.ndim == 1 else signal.shape[1]
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(np.rint(np.clip(signal, -1, 1) * 32767).astype("<i2").tobytes())


def mix_track(spec: dict[str, Any], root: Path) -> tuple[np.ndarray, dict[str, Any]]:
    config, duration = spec["audio"], spec["video"]["duration"]
    track = np.zeros((round(SAMPLE_RATE * duration), 2), dtype=np.float64)
    layers = []
    for layer in config.get("layers", []):
        path = contained(root, layer["path"])
        clip = decode_layer(path) * 10 ** (layer.get("gain_db", 0) / 20)
        record = place(track, clip, at=layer.get("at", 0), align=layer.get("align", "start"))
        layers.append({"path": layer["path"], "sha256": digest(path), "gain_db": layer.get("gain_db", 0), **record})
    return track, {"mode": "mix", "layers": layers}


def composition_track(spec: dict[str, Any], renderer: Any) -> tuple[np.ndarray, dict[str, Any]]:
    """Samples the composition synthesized in code, as (frames, channels) floats."""
    if renderer is None or not hasattr(renderer, "audio"):
        raise ValueError("audio.mode 'composition' needs a renderer that can call window.__vch.audio")
    samples = np.asarray(renderer.audio(SAMPLE_RATE), dtype=np.float64)
    expected = round(SAMPLE_RATE * spec["video"]["duration"])
    if samples.ndim != 2 or samples.shape[0] != expected or samples.shape[1] not in (1, 2):
        raise ValueError(f"Composition audio must be {expected} frames of 1 or 2 channels")
    if not np.all(np.isfinite(samples)):
        raise ValueError("Composition audio contains non-finite samples")
    fingerprint = hashlib.sha256(samples.astype("<f4").tobytes()).hexdigest()
    return samples, {"mode": "composition", "channels": int(samples.shape[1]), "sha256": fingerprint}


def render_audio(spec: dict[str, Any], root: Path, out: Path, renderer: Any = None) -> tuple[Path | None, dict[str, Any] | None]:
    """Produce the audio track for a run; returns (path or None, placement/mastering report)."""
    config = spec.get("audio", {"mode": "none"})
    if config["mode"] == "none":
        return None, None
    if config["mode"] == "file":
        return contained(root, config["path"]), {"mode": "file", "path": config["path"]}
    track, info = composition_track(spec, renderer) if config["mode"] == "composition" else mix_track(spec, root)
    track, info["mastering"] = master(track, target=config.get("loudness_target"),
                                      ceiling_dbfs=config.get("peak_ceiling_dbfs", DEFAULT_CEILING_DBFS))
    if float(np.max(np.abs(track))) > 1:
        raise ValueError("Audio clips above 0 dBFS; lower levels or set a loudness_target with a ceiling")
    path = out / "audio.wav"
    write_wav(path, track)
    info["sample_peak_dbfs"] = round(20 * math.log10(max(float(np.max(np.abs(track))), 1e-12)), 3)
    return path, info
