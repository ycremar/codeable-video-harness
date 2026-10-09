"""Preview and inspection tools: still sheets before a full render, storyboards, media profiles.

`stills` is the cheap loop used before paying for a full render (render chosen times
or one frame per beat, look at them, fix, repeat). `profile` measures an existing
video or audio file — a licensed reference or your own candidate — with the same
decoded-media signals the evaluator uses. A profile describes pacing and sound; it
is not a quality score and is not a licence to copy a reference's style.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from . import signals
from .audio import render_audio
from .backends import create_renderer
from .core import digest, finite, normalized_hits
from .pipeline import contact_sheet, probe

STILL_SHEET_THUMB = 320
SMALL_TEXT_PX = 18
PROFILE_SHEET_COLS = 6
TIMELINE_SIZE = (1600, 260)
VISUAL_SYNC_WINDOW_S = 0.1
SOUND_SYNC_WARN_MS = 20.0
CUT_SYNC_WINDOW_S = 0.05
# Pairwise style_distance among the 511 awesome-opus5-5-videos posters measured on 2026-10-08.
CORPUS_STYLE_DISTANCE = {"p10": 0.82, "median": 1.34, "p90": 2.02}
COMPARE_ROWS = (
    ("duration (s)", ("video", "duration_s")),
    ("hard cuts per 10 s", ("video", "cuts_per_10s")),
    ("visual events per 10 s", ("video", "visual_events_per_10s")),
    ("median gap between visual events (s)", ("video", "visual_gap_s", "median")),
    ("longest still hold (s)", ("video", "longest_still_hold_s")),
    ("edge density, median", ("video", "density", "edge_density", "median")),
    ("edge density, p10", ("video", "density", "edge_density", "p10")),
    ("grid cells in use, median", ("video", "density", "used_cells", "median")),
    ("colourfulness, median", ("video", "density", "colourfulness", "median")),
    ("integrated loudness (LUFS)", ("audio", "integrated_lufs")),
    ("true peak (dBTP)", ("audio", "true_peak_dbtp")),
    ("audio onsets per s", ("audio", "onsets_per_s")),
)


def still_times(spec: dict[str, Any], *, times: list[float] | None = None, beats: bool = False) -> list[float]:
    """Frame-aligned preview times: explicit list, one per beat, or scene starts and midpoints."""
    fps, duration = spec["video"]["fps"], spec["video"]["duration"]
    if times:
        if not all(finite(t) and 0 <= t < duration for t in times):
            raise ValueError("Still times must be finite and inside [0, duration)")
        chosen = times
    elif beats:
        bpm = spec.get("timing", {}).get("bpm")
        if not bpm:
            raise ValueError("--beats needs timing.bpm in the contract")
        offset = spec["timing"].get("beat_offset", 0)
        chosen = [t for t in np.arange(offset % (60 / bpm), duration, 60 / bpm)]
    else:
        chosen = [x for s in spec["scenes"] for x in (s["start"], (s["start"] + s["end"]) / 2)]
        chosen.append((round(duration * fps) - 1) / fps)
    return sorted({min(round(t * fps), round(duration * fps) - 1) / fps for t in chosen})


def _scene_at(spec: dict[str, Any], t: float) -> str:
    return next(s["id"] for s in spec["scenes"] if s["start"] <= t < s["end"])


def frame_change(first: Image.Image, second: Image.Image) -> float:
    """Mean |luma change| between two frames at the analysis size `max_static_hold_s` uses (0..255)."""
    size = signals.analysis_size(*first.size)
    a, b = (signals._luma(np.asarray(im.convert("RGB").resize(size, Image.Resampling.BOX))) for im in (first, second))
    return round(float(np.mean(np.abs(b - a))), 3)


def render_stills(spec: dict[str, Any], root: Path, out: Path, *, times: list[float], trust_code: bool,
                  motion: bool = False) -> dict[str, Any]:
    """Render raw (pre-encode) frames, a labelled sheet and per-still text checks.

    motion=True also renders each still's next frame and reports their change at the dead-time
    analysis size, so a hold can be checked before a full render (raw frames, so decoded values differ slightly).
    """
    out = Path(out)
    if out.exists():
        raise FileExistsError("Refuse to overwrite an existing stills folder")
    out.mkdir(parents=True)
    renderer = create_renderer(spec, root, trust_code)
    stills = []
    try:
        for i, t in enumerate(times):
            frame = renderer.sampled(t)
            path = out / f"{i:03d}_{t:07.3f}s.png"
            frame.image.save(path)
            text = [e for e in frame.elements if e.get("type") == "text"]
            stills.append({
                "t": t, "scene": _scene_at(spec, t), "file": path.name, "sha256": digest(path),
                "text": [e["text"] for e in text],
                "overlaps": [list(p) for p in signals.overlap_pairs(frame.elements)],
                "smallest_text_px": min((e["size"] for e in text), default=None),
            })
            following = t + 1 / spec["video"]["fps"]
            if motion and following < spec["video"]["duration"]:
                stills[-1]["frame_change"] = frame_change(frame.image, renderer.sampled(following).image)
    finally:
        if hasattr(renderer, "close"):
            renderer.close()
    v = spec["video"]
    contact_sheet([(out / s["file"], f"t={s['t']:.3f}s {s['scene']}") for s in stills], out / "sheet.jpg",
                  v["width"], v["height"], cols=4, thumb_width=STILL_SHEET_THUMB)
    summary = {"stills": stills, "sheet": "sheet.jpg",
               "note": "raw renderer frames before encoding; look at them, then run the full render for decoded evidence",
               "warnings": [f"t={s['t']:.3f}s overlapping text {s['overlaps']}" for s in stills if s["overlaps"]]
               + [f"t={s['t']:.3f}s text below {SMALL_TEXT_PX}px" for s in stills
                  if s["smallest_text_px"] is not None and s["smallest_text_px"] < SMALL_TEXT_PX]
               + [f"t={s['t']:.3f}s next-frame change {s['frame_change']} < {signals.DEFAULT_STILL_DELTA} (still for max_static_hold_s)"
                  for s in stills if s.get("frame_change") is not None and s["frame_change"] < signals.DEFAULT_STILL_DELTA]}
    (out / "stills.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def preview_sound(spec: dict[str, Any], root: Path, out: Path, *, trust_code: bool) -> dict[str, Any]:
    """Render only the audio and check loudness and cue sync before paying for a full render.

    Measures the WAV before encoding; `vch run` measures the AAC encode, which can differ slightly.
    """
    out = Path(out)
    if out.exists():
        raise FileExistsError("Refuse to overwrite an existing sound preview")
    out.mkdir(parents=True)
    renderer = create_renderer(spec, root, trust_code)
    try:
        path, info = render_audio(spec, root, out, renderer)
    finally:
        renderer.close()
    if path is None:
        raise ValueError("audio.mode is 'none': nothing to preview")
    loudness = signals.loudness_of_file(path)
    onsets = np.array([e["t"] for e in signals.detect_onsets(signals.decode_audio(path))])
    hits = []
    for hit in normalized_hits(spec.get("timing", {})):
        error = float(np.min(np.abs(onsets - hit["t"]))) * 1000 if len(onsets) else None
        hits.append({"t": hit["t"], "cue": hit["cue"], "error_ms": None if error is None else round(error, 1)})
    known = [h["error_ms"] for h in hits if h["error_ms"] is not None]
    summary = {"audio": path.name, **loudness, "mastering": info.get("mastering"), "onsets": len(onsets),
               "worst_hit_ms": max(known) if known else None,
               "missed": [h for h in hits if h["error_ms"] is None or h["error_ms"] > SOUND_SYNC_WARN_MS], "hits": hits,
               "note": "pre-encode WAV; the full run measures the encoded AAC audio"}
    (out / "sound.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def _scene_summary(scene: dict[str, Any]) -> str:
    params = scene.get("params", {})
    parts = []
    for key in ("kind", "visual", "beat", "chapter"):
        if params.get(key):
            parts.append(f"{key}: {params[key]}")
    headline = params.get("headline")
    if headline:
        parts.append("“" + " / ".join(headline if isinstance(headline, list) else [headline]) + "”")
    return "; ".join(parts).replace("|", "/") or "—"


def storyboard_markdown(spec: dict[str, Any]) -> str:
    """Timestamped storyboard table derived from the contract (scene windows, beats, hits)."""
    v, timing = spec["video"], spec.get("timing", {})
    bpm = timing.get("bpm")
    hits = normalized_hits(timing)
    lines = [f"# Storyboard: {spec.get('title', 'untitled')}", "",
             f"{v['width']}×{v['height']} · {v['fps']} fps · {v['duration']} s · backend `{spec.get('backend')}`"
             f" · audio `{spec.get('audio', {'mode': 'none'})['mode']}`" + (f" · {bpm} BPM" if bpm else ""), "",
             "| # | Scene | Window (s) | Beats | Hits | Content |", "|---|---|---|---|---|---|"]
    for i, scene in enumerate(spec["scenes"], 1):
        a, b = scene["start"], scene["end"]
        beats = f"{(b - a) * bpm / 60:g}" if bpm else "—"
        inside = [h for h in hits if a <= h["t"] < b]
        hit_text = ", ".join(f"{h['t']:g} {h['cue'] or h['kind'] or 'hit'}" for h in inside) or "—"
        lines.append(f"| {i} | {scene['id']} | {a:g}–{b:g} | {beats} | {hit_text} | {_scene_summary(scene)} |")
    kinds = [r["kind"] for r in spec["requirements"]]
    lines += ["", f"Requirements: {kinds.count('hard')} hard, {kinds.count('proxy')} proxy, {kinds.count('human')} human."]
    lines += [f"- Human `{r['id']}`: {r['rubric']}" for r in spec["requirements"] if r["kind"] == "human"]
    return "\n".join(lines) + "\n"


def _timeline_image(motion: dict[str, Any], *, fps: float, cuts: list[float], events: list[float],
                    onsets: list[float], path: Path) -> None:
    w, h = TIMELINE_SIZE
    duration = max(motion["frames"] / fps, 1e-6)
    sx = w / duration
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    for i, value in enumerate(motion["luma"]):
        shade = int(255 * value)
        draw.line([(i / fps * sx, 100), (i / fps * sx, 100 - value * 90)], fill=(shade, shade, shade))
    peak = max(max(motion["diff"]), 1)
    for i, value in enumerate(motion["diff"]):
        draw.line([(i / fps * sx, 200), (i / fps * sx, 200 - value / peak * 90)], fill="#3366cc")
    for t in events:
        draw.line([(t * sx, 105), (t * sx, 205)], fill="#ff9f1c")
    for t in cuts:
        draw.line([(t * sx, 0), (t * sx, 205)], fill="#d62728", width=2)
    for t in onsets:
        draw.line([(t * sx, 210), (t * sx, 248)], fill="#2ca02c")
    for s in range(int(duration) + 1):
        draw.text((s * sx + 2, 248), str(s), fill="black")
    img.save(path)


def _stats(values: list[float]) -> dict[str, float]:
    return {"median": round(float(np.median(values)), 3), "p10": round(float(np.percentile(values, 10)), 3),
            "p90": round(float(np.percentile(values, 90)), 3), "max": round(float(np.max(values)), 3)}


def _video_profile(path: Path, stream: dict[str, Any], out: Path, *, every: float, max_fps: float) -> dict[str, Any]:
    num, den = map(int, stream["avg_frame_rate"].split("/"))
    source_fps = num / den if den else 0
    fps = min(source_fps, max_fps) if source_fps else max_fps
    step = max(1, int(round(every * fps)))
    motion = signals.decoded_motion(path, width=stream["width"], height=stream["height"],
                                    max_fps=fps if fps < source_fps else None, thumbnail_stride=step)
    thumbs = motion.pop("thumbnails")
    duration = motion["frames"] / fps
    cuts = signals.detect_cuts(motion["diff"], motion["hist_jump"], fps=fps)
    events = signals.visual_onsets(motion["diff"], fps=fps)
    hold, hold_start = signals.longest_still_hold(motion["diff"], fps=fps)
    pops = signals.single_frame_pops(motion["diff"], motion["bridge"], fps=fps)
    sheet_items = []
    for i, rgb in sorted(thumbs.items()):
        file = out / f"frame_{i:05d}.png"
        Image.fromarray(rgb).resize((rgb.shape[1] * 2, rgb.shape[0] * 2)).save(file)
        sheet_items.append((file, f"{i / fps:.2f}s"))
    first = next(iter(thumbs.values()))
    contact_sheet(sheet_items, out / "contact.jpg", stream["width"], stream["height"], cols=PROFILE_SHEET_COLS,
                  thumb_width=first.shape[1] * 2)
    for file, _ in sheet_items:
        file.unlink()
    stills = np.diff([0.0] + cuts + [duration])
    gaps = np.diff([0.0] + events + [duration])
    return {
        "width": stream["width"], "height": stream["height"], "source_fps": round(source_fps, 3),
        "analysis_fps": fps, "duration_s": round(duration, 3),
        "hard_cuts": len(cuts), "cut_times_s": cuts, "cuts_per_10s": round(10 * len(cuts) / duration, 2),
        "shot_s": _stats(list(stills)), "visual_events": len(events), "visual_event_times_s": events,
        "visual_events_per_10s": round(10 * len(events) / duration, 2), "visual_gap_s": _stats(list(gaps)),
        "longest_still_hold_s": round(hold, 3), "longest_still_hold_start_s": hold_start,
        "still_frame_fraction": round(float(np.mean(np.array(motion["diff"][1:]) < signals.DEFAULT_STILL_DELTA)), 3)
        if motion["frames"] > 1 else None,
        "single_frame_pops": pops, "light_dark_switches": signals.light_dark_switches(motion["luma"], fps=fps),
        "mean_luma": round(float(np.mean(motion["luma"])), 3), "loop_seam_ratio": signals.loop_seam_ratio(motion, fps=fps),
        "density": signals.decoded_density(path, width=stream["width"], height=stream["height"]),
        "_motion": motion, "_events": events, "_cuts": cuts,
    }


def profile_media(path: Path, out: Path, *, every: float = 1.0, max_fps: float = 30.0) -> dict[str, Any]:
    """Pacing, cuts, holds, pops, loudness, onsets and tempo of an existing media file."""
    path, out = Path(path), Path(out)
    if out.exists():
        raise FileExistsError("Refuse to overwrite an existing profile folder")
    if not finite(every) or every <= 0 or not finite(max_fps) or max_fps <= 0:
        raise ValueError("--every and --max-fps must be positive")
    streams = probe(path)["streams"]
    video = next((s for s in streams if s["codec_type"] == "video" and s.get("avg_frame_rate", "0/0") != "0/0"), None)
    has_audio = any(s["codec_type"] == "audio" for s in streams)
    if not video and not has_audio:
        raise ValueError("No decodable audio or video stream")
    out.mkdir(parents=True)
    profile: dict[str, Any] = {"input": path.name, "sha256": digest(path)}
    if video:
        profile["video"] = _video_profile(path, video, out, every=every, max_fps=max_fps)
    if has_audio:
        audio = signals.audio_analysis(path)
        measured = [{"t": t, "strength": w} for t, w in zip(audio["onsets"], audio["onset_strengths"])]
        audio["tempo"] = signals.estimate_tempo(signals.decode_audio(path), onsets=measured)
        audio["onsets_per_s"] = round(len(audio["onsets"]) / max(audio["duration_s"], 1e-6), 3)
        profile["audio"] = audio
    if video:
        v = profile["video"]
        motion, events, cuts = v.pop("_motion"), v.pop("_events"), v.pop("_cuts")
        onsets = profile.get("audio", {}).get("onsets", [])
        if onsets:
            # Eased motion peaks a few frames after its sound, so visual events get a wider window than cuts.
            profile["sync"] = {"visual_events_vs_onsets": signals.sync_lift(events, onsets, duration=v["duration_s"],
                                                                            window=VISUAL_SYNC_WINDOW_S),
                               "cuts_vs_onsets": signals.sync_lift(cuts, onsets, duration=v["duration_s"],
                                                                   window=CUT_SYNC_WINDOW_S)}
        _timeline_image(motion, fps=v["analysis_fps"], cuts=cuts, events=events, onsets=onsets, path=out / "timeline.png")
    profile["notes"] = [
        "Decoded-media proxies (analysis ≤{:g} fps, ≤{}px): cuts, visual events, holds and pops describe "
        "change in pixels, not ideas or quality.".format(max_fps, signals.ANALYSIS_MAX_SIDE),
        "Onsets are measured transient peaks; tempo is an autocorrelation estimate without downbeats.",
        "Use a profile to propose explicit, owner-approved requirements; never to copy a reference's style.",
    ]
    (out / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=1))
    return profile


def summary_line(profile: dict[str, Any]) -> dict[str, Any]:
    """Compact console summary of a profile."""
    v, a = profile.get("video", {}), profile.get("audio", {})
    return {k: x for k, x in {
        "duration_s": v.get("duration_s") or a.get("duration_s"), "cuts_per_10s": v.get("cuts_per_10s"),
        "median_shot_s": v.get("shot_s", {}).get("median"), "visual_events_per_10s": v.get("visual_events_per_10s"),
        "longest_still_hold_s": v.get("longest_still_hold_s"), "single_frame_pops": len(v.get("single_frame_pops", [])) if v else None,
        "edge_density": v.get("density", {}).get("edge_density", {}).get("median"),
        "used_cells": v.get("density", {}).get("used_cells", {}).get("median"),
        "integrated_lufs": a.get("integrated_lufs"), "true_peak_dbtp": a.get("true_peak_dbtp"),
        "tempo": a.get("tempo"), "onsets": len(a.get("onsets", [])) if a else None,
    }.items() if x is not None and not (isinstance(x, float) and math.isnan(x))}


def _media_path(item: str | Path) -> Path:
    path = Path(item)
    return path / "video.mp4" if path.is_dir() else path


def style_profile(item: str | Path) -> dict[str, Any]:
    """Decoded style descriptors of a video file or a run folder (its video.mp4)."""
    path = _media_path(item)
    stream = signals.probe_video(path)
    return {"input": str(item), **signals.decoded_style(path, width=stream["width"], height=stream["height"])}


def diversity_markdown(items: list[str | Path]) -> str:
    """Style descriptors per video and their pairwise style distances (a spread measure, not taste)."""
    if len(items) < 2:
        raise ValueError("Diversity needs at least two videos")
    styles = [style_profile(item) for item in items]
    names = [Path(str(s["input"])).name or str(s["input"]) for s in styles]
    lines = ["| video | luma | vivid share | dominant hue | colourfulness | palette | edge density |", "|---|---|---|---|---|---|---|"]
    for name, st in zip(names, styles):
        lines.append(f"| {name} | {st['luma']:.3f} | {st['vivid_share']:.3f} | {st['dominant_hue']} | {st['colourfulness']:.1f} | "
                     f"{st['palette']:.0f} | {st['edge_density']:.3f} |")
    lines += ["", "| style distance | " + " | ".join(names) + " |", "|---" * (len(names) + 1) + "|"]
    for name, a in zip(names, styles):
        lines.append(f"| {name} | " + " | ".join(f"{signals.style_distance(a, b):.2f}" for b in styles) + " |")
    lines += ["", "Distances combine brightness, vividness, colourfulness, detail and palette size (each scaled by its "
              "p10-p90 spread across 511 corpus posters) with the hue distribution. 0 = same descriptors. Two random "
              f"corpus posters are {CORPUS_STYLE_DISTANCE['median']} apart at the median ({CORPUS_STYLE_DISTANCE['p10']} "
              f"at p10). This measures spread, not quality or taste."]
    return "\n".join(lines) + "\n"


def _lookup(profile: dict[str, Any], keys: tuple[str, ...]) -> Any:
    value: Any = profile
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def compare_profiles(first: dict[str, Any], second: dict[str, Any]) -> str:
    """Markdown table of the same proxies for two profiles (e.g. a licensed reference and a candidate)."""
    lines = [f"| proxy | {first.get('input', 'first')} | {second.get('input', 'second')} | second / first |",
             "|---|---|---|---|"]
    for label, keys in COMPARE_ROWS:
        a, b = _lookup(first, keys), _lookup(second, keys)
        ratio = f"{b / a:.2f}" if finite(a) and finite(b) and a and label not in (
            "integrated loudness (LUFS)", "true peak (dBTP)") else ""
        lines.append(f"| {label} | {'' if a is None else a} | {'' if b is None else b} | {ratio} |")
    lines.append("")
    lines.append("Decoded-pixel and sample proxies only. Detail is not information, and pace is not quality; "
                 "a deliberately minimal film scores low on purpose. Use differences to ask questions, not to grade.")
    return "\n".join(lines) + "\n"
