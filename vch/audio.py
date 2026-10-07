"""Original procedural audio, declared cue hits and licensed-layer mixing.

Everything is deterministic and local. Sounds are placed so their *measured peak*
lands on the cue time (the convention used by code-video authors who cannot hear:
analyse the waveform, then align numerically). Loudness normalisation is a single
linear gain computed from an FFmpeg BS.1770 measurement; there is no compressor or
limiter, so a peak ceiling can stop the target from being reached. That outcome is
reported, never hidden.
"""
from __future__ import annotations

import math
import subprocess
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .core import contained, digest, normalized_hits
from .signals import loudness_of_samples

SAMPLE_RATE = 48000
DEFAULT_BPM = 120
DEFAULT_CEILING_DBFS = -1.0
HIT_SECONDS = {"tick": 0.06, "impact": 0.35, "chime": 0.9}
DECODE_TIMEOUT_S = 300
FADE_OUT_S = 0.01


def beat_bed(*, duration: float, bpm: float, offset: float, rate: int = SAMPLE_RATE) -> np.ndarray:
    """The original percussive bed: a pitched thump on every beat, an accent on odd beats."""
    signal = np.zeros(round(rate * duration), dtype=np.float64)
    for i, start in enumerate(np.arange(offset, duration, 60 / bpm)):
        if start < 0:
            continue
        t = np.arange(int(rate * .22)) / rate
        hit = np.sin(2 * np.pi * (70 * t + 14 * (1 - np.exp(-32 * t)))) * np.exp(-28 * t)
        if i % 2:
            hit += .25 * np.sin(2 * np.pi * 720 * t) * np.exp(-60 * t)
        a = round(start * rate)
        b = min(a + len(hit), len(signal))
        signal[a:b] += hit[:b - a]
    return signal


def _synthesize(kind: str, t: np.ndarray) -> np.ndarray:
    if kind == "tick":
        return (np.sin(2 * np.pi * 2400 * t) + .5 * np.sin(2 * np.pi * 3700 * t)) * np.exp(-90 * t) * .6
    if kind == "impact":
        body = np.sin(2 * np.pi * (52 * t + 40 * (1 - np.exp(-25 * t)) / 25)) * np.exp(-9 * t)
        click = np.sin(2 * np.pi * 1800 * t) * np.exp(-140 * t) * .35
        return body + click
    partials = [(880, 1.0), (1320, .45), (1760, .25), (2640, .12)]
    return sum(a * np.sin(2 * np.pi * f * t) for f, a in partials) * np.exp(-5 * t) * (1 - np.exp(-900 * t)) * .5


def hit_sound(kind: str, *, rate: int = SAMPLE_RATE) -> np.ndarray:
    """Short original synthesized cue sounds with sharp, measurable attacks."""
    t = np.arange(int(rate * HIT_SECONDS[kind])) / rate
    # Fade the tail so truncation never adds a second, unintended transient.
    fade = np.clip((len(t) - 1 - np.arange(len(t))) / (FADE_OUT_S * rate), 0, 1)
    return _synthesize(kind, t) * fade


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


def _hit_placements(spec: dict[str, Any], track: np.ndarray) -> list[dict[str, Any]]:
    placed = []
    for hit in normalized_hits(spec.get("timing", {})):
        clip = hit_sound(hit["kind"])
        if track.ndim == 2:
            clip = np.repeat(clip[:, None], track.shape[1], axis=1)
        placed.append({"kind": hit["kind"], **place(track, clip, at=hit["t"], align="peak")})
    return placed


def procedural_track(spec: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    config, duration = spec["audio"], spec["video"]["duration"]
    timing = spec.get("timing", {})
    track = np.zeros(round(SAMPLE_RATE * duration), dtype=np.float64)
    if config.get("bed", True):
        track += beat_bed(duration=duration, bpm=timing.get("bpm", DEFAULT_BPM), offset=timing.get("beat_offset", 0))
    hits = _hit_placements(spec, track)
    # Same normalisation as the original bed: shrink only if the sum would clip, then apply gain.
    peak = max(1, float(np.max(np.abs(track))) if len(track) else 0.0)
    track = track / peak * config["gain"]
    return track, {"mode": "procedural", "bed": bool(config.get("bed", True)), "hits": hits}


def mix_track(spec: dict[str, Any], root: Path) -> tuple[np.ndarray, dict[str, Any]]:
    config, duration = spec["audio"], spec["video"]["duration"]
    track = np.zeros((round(SAMPLE_RATE * duration), 2), dtype=np.float64)
    layers = []
    for layer in config.get("layers", []):
        path = contained(root, layer["path"])
        clip = decode_layer(path) * 10 ** (layer.get("gain_db", 0) / 20)
        record = place(track, clip, at=layer.get("at", 0), align=layer.get("align", "start"))
        layers.append({"path": layer["path"], "sha256": digest(path), "gain_db": layer.get("gain_db", 0), **record})
    hits = _hit_placements(spec, track) if config.get("procedural_hits") else []
    return track, {"mode": "mix", "layers": layers, "hits": hits}


def render_audio(spec: dict[str, Any], root: Path, out: Path) -> tuple[Path | None, dict[str, Any] | None]:
    """Produce the audio track for a run; returns (path or None, placement/mastering report)."""
    config = spec.get("audio", {"mode": "none"})
    if config["mode"] == "none":
        return None, None
    if config["mode"] == "file":
        return contained(root, config["path"]), {"mode": "file", "path": config["path"]}
    track, info = procedural_track(spec) if config["mode"] == "procedural" else mix_track(spec, root)
    track, info["mastering"] = master(track, target=config.get("loudness_target"),
                                      ceiling_dbfs=config.get("peak_ceiling_dbfs", DEFAULT_CEILING_DBFS))
    if config["mode"] == "mix" and float(np.max(np.abs(track))) > 1:
        raise ValueError("Mix clips above 0 dBFS; lower layer gains or set a loudness_target with a ceiling")
    path = out / "audio.wav"
    write_wav(path, track)
    info["sample_peak_dbfs"] = round(20 * math.log10(max(float(np.max(np.abs(track))), 1e-12)), 3)
    return path, info
