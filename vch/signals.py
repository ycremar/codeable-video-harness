"""Signals measured from decoded media: motion, holds, single-frame pops, loudness, onsets.

Every value here comes from pixels or samples that FFmpeg decoded from a file. They
are named proxies with stated units, not quality, excitement or "impact" scores.
The same functions back `vch profile` (reference/candidate inspection) and the
evaluator's decoded-evidence metrics, so research numbers stay reproducible.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Iterator

import numpy as np

ANALYSIS_MAX_SIDE = 160
ANALYSIS_SAMPLE_RATE = 24000
ONSET_FFT = 1024
ONSET_HOP = 128
ONSET_BLOCK_FRAMES = 4096
ONSET_DELTA = 0.07
ONSET_MEDIAN_S = 0.25
ONSET_MIN_GAP_S = 0.05
PEAK_SEARCH_S = (-0.01, 0.06)
TEMPO_RANGE_BPM = (60.0, 200.0)
TEMPO_REFINE = 0.03
TEMPO_REFINE_STEPS = 601
HIST_BINS_PER_CHANNEL = 8
CUT_HIST_JUMP = 0.35
CUT_PIXEL_FLOOR = 18.0
VISUAL_ONSET_FLOOR = 2.0
VISUAL_ONSET_RATIO = 2.5
VISUAL_ONSET_GAP_S = 0.25
DEFAULT_STILL_DELTA = 0.5
DEFAULT_POP_RATIO = 3.0
DEFAULT_POP_FLOOR = 8.0
SEAM_WINDOW_S = 0.5
DARK_LUMA, LIGHT_LUMA = 0.3, 0.6
SUBPROCESS_TIMEOUT_S = 600
DENSITY_MAX_SIDE = 480
DENSITY_EVERY_S = 0.5
EDGE_STEP = 24.0
CELL_GRID = (12, 6)
CELL_EDGE_FRACTION = 0.02
STYLE_EVERY_S = 1.0
HUE_BINS = 12
HUE_NAMES = ("red", "orange", "yellow", "lime", "green", "teal", "cyan", "azure", "blue", "violet", "magenta", "rose")
VIVID_SATURATION, VIVID_VALUE = 0.35, 0.25
MIN_VIVID_FOR_HUE = 0.02
PALETTE_MIN_SHARE = 0.01
# Typical spread of each descriptor across the 511 measured corpus posters (p90 - p10, rounded).
STYLE_SCALES = {"luma": 0.72, "vivid_share": 0.64, "colourfulness": 75.0, "edge_density": 0.17, "palette": 19.0}


def analysis_size(width: int, height: int) -> tuple[int, int]:
    """Small, aspect-preserving decode size; motion means are insensitive to resolution."""
    scale = ANALYSIS_MAX_SIDE / max(width, height)
    return max(2, round(width * scale)), max(2, round(height * scale))


def probe_video(path: Path) -> dict[str, Any]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,avg_frame_rate", "-of", "json", str(path)],
                         check=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT_S).stdout
    streams = json.loads(out).get("streams", [])
    if not streams:
        raise ValueError(f"No video stream in {path}")
    return streams[0]


def _decoded_frames(path: Path, *, size: tuple[int, int], max_fps: float | None) -> Iterator[np.ndarray]:
    w, h = size
    vf = f"scale={w}:{h}:flags=area,format=rgb24"
    if max_fps:
        vf = f"fps={max_fps}," + vf
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-an", "-vf", vf, "-fps_mode", "passthrough",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = w * h * 3
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
    finally:
        proc.stdout.close()
        proc.wait(timeout=SUBPROCESS_TIMEOUT_S)


def _luma(rgb: np.ndarray) -> np.ndarray:
    f = rgb.astype(np.float32)
    return 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]


def _histogram(rgb: np.ndarray) -> np.ndarray:
    q = (rgb // (256 // HIST_BINS_PER_CHANNEL)).astype(np.int32)
    idx = (q[..., 0] * HIST_BINS_PER_CHANNEL + q[..., 1]) * HIST_BINS_PER_CHANNEL + q[..., 2]
    counts = np.bincount(idx.ravel(), minlength=HIST_BINS_PER_CHANNEL ** 3).astype(np.float64)
    return counts / counts.sum()


def decoded_motion(path: Path, *, width: int, height: int, max_fps: float | None = None,
                   thumbnail_stride: int = 0) -> dict[str, Any]:
    """Per-frame change signals of the decoded video at a small analysis size.

    diff[i]   = mean |luma(i) - luma(i-1)| on a 0..255 scale (diff[0] = 0)
    bridge[i] = mean |luma(i) - luma(i-2)|, used to tell one-frame pops from cuts
    hist_jump[i] = total-variation distance of colour histograms (cut proxy)
    loop_seam = mean |luma(last) - luma(first)|
    thumbnail_stride > 0 keeps every n-th analysis frame as {index: rgb} for contact sheets.
    """
    diffs, bridges, jumps, lumas, thumbs = [], [], [], [], {}
    prev = prev2 = prev_hist = first = last = None
    for rgb in _decoded_frames(path, size=analysis_size(width, height), max_fps=max_fps):
        y = _luma(rgb)
        hist = _histogram(rgb)
        diffs.append(0.0 if prev is None else float(np.mean(np.abs(y - prev))))
        bridges.append(0.0 if prev2 is None else float(np.mean(np.abs(y - prev2))))
        jumps.append(0.0 if prev_hist is None else float(0.5 * np.abs(hist - prev_hist).sum()))
        lumas.append(float(y.mean() / 255))
        if first is None:
            first = y
        if thumbnail_stride and (len(diffs) - 1) % thumbnail_stride == 0:
            thumbs[len(diffs) - 1] = rgb
        prev2, prev, prev_hist, last = prev, y, hist, y
    if first is None:
        raise ValueError(f"No decodable frames in {path}")
    result = {
        "analysis_size": list(analysis_size(width, height)), "frames": len(diffs),
        "diff": [round(x, 3) for x in diffs], "bridge": [round(x, 3) for x in bridges],
        "hist_jump": [round(x, 4) for x in jumps], "luma": [round(x, 4) for x in lumas],
        "loop_seam": round(float(np.mean(np.abs(last - first))), 3),
        "units": "mean absolute 8-bit luma difference at analysis size",
    }
    if thumbnail_stride:
        result["thumbnails"] = thumbs
    return result


def frame_density(rgb: np.ndarray) -> dict[str, float]:
    """Visual-detail proxies for one frame; none of them measures information or quality.

    edge_density = share of pixels whose Sobel luma step exceeds EDGE_STEP (0..255 scale)
    used_cells   = share of a 12x6 grid whose cells contain at least 2% such edge pixels
    colourfulness = Hasler & Suesstrunk (2003) opponent-colour statistic
    """
    y = _luma(rgb)
    gx = np.zeros_like(y)
    gy = np.zeros_like(y)
    gx[1:-1, 1:-1] = (y[:-2, 2:] + 2 * y[1:-1, 2:] + y[2:, 2:]) - (y[:-2, :-2] + 2 * y[1:-1, :-2] + y[2:, :-2])
    gy[1:-1, 1:-1] = (y[2:, :-2] + 2 * y[2:, 1:-1] + y[2:, 2:]) - (y[:-2, :-2] + 2 * y[:-2, 1:-1] + y[:-2, 2:])
    # A Sobel response is 4x the luma step across an ideal edge.
    edges = np.hypot(gx, gy) / 4 > EDGE_STEP
    cols, rows = CELL_GRID
    h, w = edges.shape
    cells = edges[:h - h % rows, :w - w % cols].reshape(rows, h // rows, cols, w // cols).mean(axis=(1, 3))
    f = rgb.astype(np.float64)
    rg = f[..., 0] - f[..., 1]
    yb = 0.5 * (f[..., 0] + f[..., 1]) - f[..., 2]
    colourfulness = math.hypot(rg.std(), yb.std()) + 0.3 * math.hypot(rg.mean(), yb.mean())
    return {"edge_density": float(edges.mean()), "used_cells": float((cells >= CELL_EDGE_FRACTION).mean()),
            "colourfulness": float(colourfulness)}


def _hue_saturation(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    f = rgb.astype(np.float64) / 255
    top, low = f.max(axis=2), f.min(axis=2)
    delta = top - low
    sat = np.where(top > 0, delta / np.maximum(top, 1e-9), 0.0)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    hue = np.zeros_like(top)
    chroma = delta > 1e-9
    red = chroma & (top == r)
    green = chroma & (top == g) & ~red
    blue = chroma & ~red & ~green
    hue[red] = ((g - b)[red] / delta[red]) % 6
    hue[green] = (b - r)[green] / delta[green] + 2
    hue[blue] = (r - g)[blue] / delta[blue] + 4
    return hue / 6, sat, top


def style_features(rgb: np.ndarray) -> dict[str, Any]:
    """Style descriptors of one frame: brightness, how much is vivid, which hues, how many colours.

    vivid = saturation > 0.35 and value > 0.25; hue_share is over 12 equal hue bins of vivid pixels.
    palette = 4-bit-per-channel colours that each cover at least 1% of the frame.
    """
    hue, sat, value = _hue_saturation(rgb)
    vivid = (sat > VIVID_SATURATION) & (value > VIVID_VALUE)
    # Bins are centred on their names (red = 345..15 degrees).
    bins = np.bincount(np.floor(hue[vivid] * HUE_BINS + 0.5).astype(int) % HUE_BINS, minlength=HUE_BINS)
    share = bins / max(1, int(vivid.sum()))
    quantized = (rgb // 16).astype(np.int32)
    keys = (quantized[..., 0] * 16 + quantized[..., 1]) * 16 + quantized[..., 2]
    counts = np.bincount(keys.ravel(), minlength=4096) / keys.size
    luma = _luma(rgb) / 255
    density = frame_density(rgb)
    return {"luma": float(luma.mean()), "vivid_share": float(vivid.mean()), "hue_share": share.tolist(),
            "palette": int((counts >= PALETTE_MIN_SHARE).sum()), "colourfulness": density["colourfulness"],
            "edge_density": density["edge_density"]}


def decoded_style(path: Path, *, width: int, height: int, every: float = STYLE_EVERY_S) -> dict[str, Any]:
    """style_features of decoded frames sampled every `every` s; medians, and the mean hue distribution."""
    scale = DENSITY_MAX_SIDE / max(width, height)
    size = (max(CELL_GRID[0], 2 * round(width * scale / 2)), max(CELL_GRID[1], 2 * round(height * scale / 2)))
    frames = [style_features(rgb) for rgb in _decoded_frames(path, size=size, max_fps=1 / every)]
    if not frames:
        raise ValueError(f"No decodable frames in {path}")
    result: dict[str, Any] = {"frames": len(frames), "every_s": every}
    for key in ("luma", "vivid_share", "palette", "colourfulness", "edge_density"):
        result[key] = round(float(np.median([f[key] for f in frames])), 4)
    hues = np.mean([f["hue_share"] for f in frames], axis=0)
    result["hue_share"] = [round(float(x), 4) for x in hues]
    result["dominant_hue"] = HUE_NAMES[int(np.argmax(hues))] if result["vivid_share"] >= MIN_VIVID_FOR_HUE else "neutral"
    return result


def style_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Distance between two decoded_style summaries (0 = same descriptors). A spread measure, not taste."""
    scalars = sum(((a[k] - b[k]) / scale) ** 2 for k, scale in STYLE_SCALES.items())
    weight_a, weight_b = min(1.0, a["vivid_share"] / MIN_VIVID_FOR_HUE), min(1.0, b["vivid_share"] / MIN_VIVID_FOR_HUE)
    hues = 0.5 * float(np.abs(np.array(a["hue_share"]) * weight_a - np.array(b["hue_share"]) * weight_b).sum())
    return round(math.sqrt(scalars + hues ** 2), 3)


def decoded_density(path: Path, *, width: int, height: int, every: float = DENSITY_EVERY_S) -> dict[str, Any]:
    """frame_density of decoded frames sampled every `every` seconds at up to DENSITY_MAX_SIDE px."""
    scale = DENSITY_MAX_SIDE / max(width, height)
    size = (max(CELL_GRID[0], 2 * round(width * scale / 2)), max(CELL_GRID[1], 2 * round(height * scale / 2)))
    frames = [frame_density(rgb) for rgb in _decoded_frames(path, size=size, max_fps=1 / every)]
    if not frames:
        raise ValueError(f"No decodable frames in {path}")
    result: dict[str, Any] = {"every_s": every, "analysis_size": list(size), "frames": len(frames)}
    for key in ("edge_density", "used_cells", "colourfulness"):
        values = np.array([f[key] for f in frames])
        result[key] = {"median": round(float(np.median(values)), 4), "p10": round(float(np.percentile(values, 10)), 4),
                       "p90": round(float(np.percentile(values, 90)), 4)}
    result["units"] = ("edge_density/used_cells are fractions 0..1; colourfulness is Hasler-Suesstrunk on 0..255 RGB; "
                       "detail proxies, not information or quality")
    return result


def _excluded(t: float, windows: list[list[float]]) -> bool:
    return any(a <= t < b for a, b in windows)


def check_windows(windows: Any) -> list[list[float]]:
    """Validate declared exclusion windows ([[start, end], ...]); malformed input is unmeasured."""
    if windows is None:
        return []
    if not isinstance(windows, list):
        raise ValueError("exclude must be a list of [start, end] windows")
    checked = []
    for w in windows:
        if (not isinstance(w, list) or len(w) != 2 or not all(isinstance(x, (int, float)) for x in w)
                or not all(math.isfinite(x) for x in w) or w[0] >= w[1]):
            raise ValueError("Each exclusion window must be [start, end] with start < end")
        checked.append([float(w[0]), float(w[1])])
    return checked


def longest_still_hold(diff: list[float], *, fps: float, still_delta: float = DEFAULT_STILL_DELTA,
                       exclude: list[list[float]] | None = None) -> tuple[float, float | None]:
    """Longest interval (s) in which consecutive decoded frames change less than still_delta."""
    windows = exclude or []
    best, run, start, best_start = 0, 0, None, None
    for i in range(1, len(diff)):
        t = i / fps
        if diff[i] < still_delta and not _excluded(t, windows):
            if run == 0:
                start = (i - 1) / fps
            run += 1
            if run > best:
                best, best_start = run, start
        else:
            run = 0
    return best / fps, best_start


def single_frame_pops(diff: list[float], bridge: list[float], *, fps: float, ratio: float = DEFAULT_POP_RATIO,
                      floor: float = DEFAULT_POP_FLOOR, exclude: list[list[float]] | None = None) -> list[float]:
    """Frames that differ from BOTH neighbours far more than the neighbours differ from each other.

    A hard cut changes once and stays changed (bridge stays large), so it is not a pop.
    Intentional one-frame flashes are pops by this definition; exclude them explicitly.
    """
    windows = exclude or []
    pops = []
    for i in range(1, len(diff) - 1):
        into, out_of, neighbours = diff[i], diff[i + 1], bridge[i + 1]
        smaller = min(into, out_of)
        if smaller >= floor and smaller > ratio * max(neighbours, 0.25) and not _excluded(i / fps, windows):
            pops.append(round(i / fps, 4))
    return pops


def loop_seam_ratio(motion: dict[str, Any], *, fps: float, still_delta: float = DEFAULT_STILL_DELTA) -> float:
    """Last→first decoded-frame change relative to typical frame steps near both ends."""
    diff = motion["diff"]
    k = max(1, int(round(SEAM_WINDOW_S * fps)))
    local = [d for d in diff[1:k + 1] + diff[-k:] if d >= still_delta]
    seam = motion["loop_seam"]
    if seam < still_delta:
        return 0.0
    return round(seam / max(float(np.median(local)) if local else 0.0, still_delta), 3)


def detect_cuts(diff: list[float], hist_jump: list[float], *, fps: float, min_gap_s: float = 0.2) -> list[float]:
    """Hard-cut proxy: colour-histogram jump or pixel jump that stands out from local motion."""
    cuts: list[int] = []
    n = len(diff)
    window = max(2, int(fps))
    for i in range(1, n):
        neighbourhood = diff[max(1, i - window):i] + diff[i + 1:min(n, i + window + 1)]
        local = float(np.median(neighbourhood)) if neighbourhood else 0.0
        strong_pixel = diff[i] > max(CUT_PIXEL_FLOOR, 4 * local + 6)
        strong_hist = hist_jump[i] > CUT_HIST_JUMP and diff[i] > 6
        if (strong_pixel or strong_hist) and (not cuts or (i - cuts[-1]) / fps >= min_gap_s):
            cuts.append(i)
    return [round(i / fps, 4) for i in cuts]


def visual_onsets(diff: list[float], *, fps: float) -> list[float]:
    """Moments where frame-to-frame change rises sharply above the recent past (entrances, hits, cuts)."""
    k = max(2, int(fps * 0.3))
    onsets: list[int] = []
    for i in range(1, len(diff)):
        recent = float(np.median(diff[max(1, i - k):i])) if i > 1 else 0.0
        if diff[i] >= max(VISUAL_ONSET_FLOOR, VISUAL_ONSET_RATIO * recent) and diff[i] > diff[i - 1]:
            if not onsets or (i - onsets[-1]) / fps >= VISUAL_ONSET_GAP_S:
                onsets.append(i)
    return [round(i / fps, 4) for i in onsets]


def light_dark_switches(luma: list[float], *, fps: float) -> list[float]:
    state, switches = None, []
    for i, value in enumerate(luma):
        new = "dark" if value < DARK_LUMA else "light" if value > LIGHT_LUMA else state
        if state and new != state:
            switches.append(round(i / fps, 3))
        state = new
    return switches


def decode_audio(path: Path, *, rate: int = ANALYSIS_SAMPLE_RATE) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"]
    out = subprocess.run(cmd, check=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT_S).stdout
    return np.frombuffer(out, dtype="<f4").astype(np.float64)


def _parse_ebur128(stderr: str) -> dict[str, float | None]:
    summary = stderr[stderr.rfind("Summary:"):]

    def grab(label: str) -> float | None:
        match = re.search(label + r":\s+(-?inf|-?[\d.]+)", summary)
        if not match or "inf" in match.group(1):
            return None
        return float(match.group(1))
    return {"integrated_lufs": grab("I"), "loudness_range_lu": grab("LRA"), "true_peak_dbtp": grab("Peak")}


def loudness_of_file(path: Path) -> dict[str, float | None]:
    """BS.1770 integrated loudness and 4x-oversampled true peak via FFmpeg's ebur128 filter."""
    cmd = ["ffmpeg", "-nostats", "-v", "info", "-i", str(path), "-vn", "-af", "ebur128=peak=true",
           "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_S).stderr
    return _parse_ebur128(err)


def loudness_of_samples(samples: np.ndarray, *, rate: int) -> dict[str, float | None]:
    """Same measurement for in-memory float samples (mono or [n, channels])."""
    channels = 1 if samples.ndim == 1 else samples.shape[1]
    cmd = ["ffmpeg", "-nostats", "-v", "info", "-f", "f32le", "-ar", str(rate), "-ac", str(channels),
           "-i", "-", "-af", "ebur128=peak=true", "-f", "null", "-"]
    err = subprocess.run(cmd, input=samples.astype("<f4").tobytes(), capture_output=True,
                         timeout=SUBPROCESS_TIMEOUT_S).stderr.decode(errors="replace")
    return _parse_ebur128(err)


def onset_envelope(signal: np.ndarray) -> np.ndarray:
    """Half-wave-rectified log-spectral flux, normalised to 0..1; one value per hop."""
    if len(signal) < ONSET_FFT:
        return np.zeros(0)
    window = np.hanning(ONSET_FFT)
    starts = np.arange(0, len(signal) - ONSET_FFT + 1, ONSET_HOP)
    flux = np.zeros(len(starts))
    previous = None
    for block in range(0, len(starts), ONSET_BLOCK_FRAMES):
        idx = starts[block:block + ONSET_BLOCK_FRAMES]
        frames = np.stack([signal[i:i + ONSET_FFT] for i in idx]) * window
        mag = np.log1p(100 * np.abs(np.fft.rfft(frames, axis=1)))
        stacked = mag if previous is None else np.vstack([previous, mag])
        rise = np.maximum(0, np.diff(stacked, axis=0)).sum(axis=1)
        if previous is None:
            rise = np.r_[0.0, rise]
        flux[block:block + len(idx)] = rise
        previous = mag[-1:]
    peak = flux.max()
    return flux / peak if peak > 0 else flux


def detect_onsets(signal: np.ndarray, *, rate: int = ANALYSIS_SAMPLE_RATE) -> list[dict[str, float]]:
    """Transient events: spectral-flux peaks refined to the local amplitude peak.

    The reported time is the measured transient peak, the same reference point
    used when cue sounds are placed "by their peak" on an event.
    """
    # Leading silence lets an attack at t=0 register as a rise like any other.
    pad = ONSET_FFT
    signal = np.concatenate([np.zeros(pad), signal])
    env = onset_envelope(signal)
    if not len(env):
        return []
    hop_s = ONSET_HOP / rate
    k = max(1, int(ONSET_MEDIAN_S / hop_s))
    candidates = []
    for i in range(1, len(env) - 1):
        lo, hi = max(0, i - k), min(len(env), i + k + 1)
        if env[i] >= env[i - 1] and env[i] > env[i + 1] and env[i] > np.median(env[lo:hi]) + ONSET_DELTA:
            candidates.append(i)
    events: list[dict[str, float]] = []
    for i in candidates:
        center = i * ONSET_HOP + ONSET_FFT // 2
        a = max(0, center + int(PEAK_SEARCH_S[0] * rate) - ONSET_FFT // 2)
        b = min(len(signal), center + int(PEAK_SEARCH_S[1] * rate))
        if b <= a:
            continue
        peak_at = a + int(np.argmax(np.abs(signal[a:b])))
        t = max(0, peak_at - pad) / rate
        if events and t - events[-1]["t"] < ONSET_MIN_GAP_S:
            if env[i] > events[-1]["strength"]:
                events[-1] = {"t": round(t, 4), "strength": round(float(env[i]), 4)}
            continue
        events.append({"t": round(t, 4), "strength": round(float(env[i]), 4)})
    return events


def estimate_tempo(signal: np.ndarray, *, rate: int = ANALYSIS_SAMPLE_RATE,
                   onsets: list[dict[str, float]] | None = None) -> dict[str, float] | None:
    """Autocorrelation tempo; beat offset = strength-weighted circular mean of onset peaks.

    Falls back to a comb over the onset envelope when no onsets are given. No
    downbeat or meter estimate.
    """
    env = onset_envelope(signal)
    env_rate = rate / ONSET_HOP
    if len(env) < env_rate * 4:
        return None
    x = env - env.mean()
    spectrum = np.fft.rfft(x, n=2 * len(x))
    ac = np.fft.irfft(spectrum * np.conj(spectrum))[:len(x)]
    if ac[0] <= 0:
        return None
    lags = np.arange(len(ac)) / env_rate
    mask = (lags >= 60 / TEMPO_RANGE_BPM[1]) & (lags <= 60 / TEMPO_RANGE_BPM[0])
    lag = int(np.argmax(np.where(mask, ac, -np.inf)))
    period = lag / env_rate
    if onsets:
        # Refine the period (±3%, no octave jumps) to the one that best phase-aligns the onsets.
        times = np.array([o["t"] for o in onsets])
        weights = np.array([o["strength"] for o in onsets])
        candidates = period * np.linspace(1 - TEMPO_REFINE, 1 + TEMPO_REFINE, TEMPO_REFINE_STEPS)
        coherence = [abs(np.sum(weights * np.exp(2j * np.pi * times / c))) for c in candidates]
        period = float(candidates[int(np.argmax(coherence))])
        resultant = np.sum(weights * np.exp(2j * np.pi * times / period))
        offset = float(np.angle(resultant)) / (2 * np.pi) * period
    else:
        scores = [env[p::lag].mean() for p in range(lag)]
        offset = (int(np.argmax(scores)) * ONSET_HOP + ONSET_FFT // 2) / rate
    return {"bpm": round(60 / period, 2), "beat_offset_s": round(offset % period, 4),
            "autocorrelation": round(float(ac[lag] / ac[0]), 3)}


def audio_analysis(path: Path) -> dict[str, Any]:
    signal = decode_audio(path)
    rms = float(np.sqrt(np.mean(signal ** 2))) if len(signal) else 0.0
    events = detect_onsets(signal)
    return {**loudness_of_file(path), "sample_rate": ANALYSIS_SAMPLE_RATE,
            "duration_s": round(len(signal) / ANALYSIS_SAMPLE_RATE, 4),
            "rms_dbfs": round(20 * math.log10(max(rms, 1e-12)), 2),
            "onsets": [e["t"] for e in events], "onset_strengths": [e["strength"] for e in events],
            "method": "ebur128 (BS.1770, 4x true peak) on encoded audio; onsets = log-spectral-flux "
                      "peaks refined to the local amplitude peak"}


def _seconds(line: str) -> float | None:
    try:
        value = float(line.strip().strip(","))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def frame_timing(path: Path, *, fps: float) -> dict[str, Any]:
    """Presentation timestamps of encoded video packets compared with an ideal constant-rate grid."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
                          "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True,
                         timeout=SUBPROCESS_TIMEOUT_S).stdout
    stamps = sorted(_seconds(line) for line in out.splitlines() if _seconds(line) is not None)
    if not stamps:
        raise ValueError("No video packet timestamps")
    first = stamps[0]
    jitter = max(abs(t - (first + i / fps)) for i, t in enumerate(stamps))
    return {"frames": len(stamps), "first_pts_s": round(first, 6), "max_jitter_ms": round(1000 * jitter, 3)}


def overlap_pairs(elements: list[dict[str, Any]], *, min_fraction: float = 0.25,
                  ignore: set[str] | None = None) -> list[tuple[str, str]]:
    """Pairs of distinct text elements whose boxes intersect by ≥ min_fraction of the smaller box."""
    ignore = ignore or set()
    texts = [e for e in elements if e.get("type") == "text" and e.get("id") not in ignore]
    pairs = []
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            if a["id"] == b["id"]:
                continue
            if _boxes_overlap(a.get("rects") or [a["bbox"]], b.get("rects") or [b["bbox"]], min_fraction):
                pairs.append((a["id"], b["id"]))
    return pairs


def _boxes_overlap(first: list[list[float]], second: list[list[float]], min_fraction: float) -> bool:
    for a in first:
        for b in second:
            w = min(a[2], b[2]) - max(a[0], b[0])
            h = min(a[3], b[3]) - max(a[1], b[1])
            if w <= 0 or h <= 0:
                continue
            smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
            if smaller > 0 and w * h >= min_fraction * smaller:
                return True
    return False


def sync_lift(events: list[float], onsets: list[float], *, duration: float, window: float = 0.05) -> dict[str, Any] | None:
    """Share of visual events within ±window of an audio onset, compared with random times."""
    if not events or not onsets or duration <= 0:
        return None
    arr = np.array(onsets)
    hits = sum(float(np.min(np.abs(arr - e))) <= window for e in events)
    grid = np.arange(0, duration, 0.01)
    chance = float(np.mean([np.min(np.abs(arr - g)) <= window for g in grid]))
    rate = hits / len(events)
    return {"window_s": window, "events": len(events), "near_onset": int(hits), "rate": round(rate, 3),
            "chance_rate": round(chance, 3), "lift": round(rate / chance, 2) if chance else None}
