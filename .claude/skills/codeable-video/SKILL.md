---
name: codeable-video
description: Make, render or repair a code-rendered video in this repository (launch film, explainer, motion graphic, loop) with evidence. Use for any request to create, animate, render, retime or fix a video here; walks brief → contract → storyboard → stills → render → evaluate → repair.
---

# Codeable video production loop

Rules live in `AGENTS.md`; follow them exactly. Details: `docs/AUTHORING.md` (backends, HTML
seek protocol, brief → evidence table), `docs/MEASUREMENT.md` (what each metric can and cannot
show), `docs/OPUS_VIDEO_RESEARCH.md` (how public code-rendered videos are made).

1. **Brief → contract.** Copy an example (`examples/html.json` for HTML/CSS/SVG/WebGL motion,
   `examples/explainer.json` for Python scenes). Turn each brief section into a hard check, a named
   proxy or a human rubric (table in AUTHORING.md). Freeze thresholds before rendering. Ask the
   user only for missing facts, rights and assets; never invent product claims or numbers.
2. **Plan.** `python -m vch storyboard <contract>`. Put scene cuts on `timing.bpm`, and add
   `timing.hits` for every moment that needs a sound. For a licensed song:
   `python -m vch profile song.wav --out runs/song-profile`, then read tempo, phase and onsets from
   `profile.json`.
3. **Style is an input.** Put tokens in `styles/<pack>.json` (roles, not hues) and reference them as
   `contract.style`, or pass `--style` to `vch run` / `vch stills`. For variants, render each pack and
   check `vch diversity` (corpus median pair distance 1.34). Every pack must pass the same checks.
4. **Build** `compositions/<name>/index.html` (or `scenes/*.py`):
   - `window.__vch.seek(t)` sets every property from `t`; nothing carries over between frames.
   - Use closed-form springs, and snap them when settled.
   - Outgoing text leaves before incoming text arrives. Masks start fully hidden.
   - Wipes take ≥0.3 s; labels fade across them.
   - Fonts and media stay local and are declared with rights.
   - For real 3D, start from a `compositions/three-*` clip: three.js is vendored, and
     `compositions/_lib/clip.js` has the pure-time helpers.
   - Mark semantic lines with `data-vch-id`.
5. **Preview cheaply.** `python -m vch stills <contract> --beats --out runs/<name>-stills-NNN --trust-scene-code`.
   Open `sheet.jpg` and actually look. Fix the warnings in `stills.json` before rendering. Add
   `--motion` to check that holds keep moving (next-frame change ≥ 0.5).
   - If the brief points at a reference ("as rich as this"), profile both:
     `vch profile <file> --out <dir>`, then `vch profile-compare a/profile.json b/profile.json`.
   - Don't edit project files while `vch run` renders. The source check invalidates the run.
6. **Render + measure.** `python -m vch run <contract> --out runs/<name>-NNN --trust-scene-code`.
   - Read `report.md`.
   - Inspect `contact-sheet.jpg` and `frames/` (decoded from the MP4).
   - Watch and listen if you can; otherwise say you could not.
   - Exit 3 means machine checks passed and human review is pending.
7. **Repair** named failures only, up to 3 attempts, each into a new run folder. Never edit
   thresholds, `vch/evaluate.py` or tests to make a candidate pass.

| Failure | Usual cause → fix |
|---|---|
| SEEK mismatches | State carried between frames (cached DOM, counters, timers) → derive from `t` |
| OVERLAP | Enter/exit share a window → give outgoing text its own exit before entry |
| CONTRAST low | Label colour switches before a wipe covers it → fade it across the wipe |
| POPS | One-frame flood or flash → spread it over ≥0.3 s, or `exclude` a deliberate flash |
| DEAD-TIME | A settled layout holds too long → add motion or a beat, or exclude a deliberate end hold |
| HITS | A cue without a sound, or a sound placed by its file start → declared hits; align layers by `peak` |
| Loudness | Transient-only audio cannot reach the target under the ceiling → lower the target or supply a mastered, licensed bed |
| "non-local resources" | CDN font or library → vendor it under `compositions/_vendor/<lib>/` and declare the folder (path ending `/`) with its licence |
| `console.error` blocks the run | Usually a WebGL shader compile error; the frame would have rendered black |
| 3D clip fails SEEK | Per-frame state set after it is used (e.g. `camera.up` after `lookAt`), or an animation loop instead of `seek(t)` |
| CONTRAST on a label that looked fine | The label never settled: it appeared within ~1 s of its panel leaving, or artwork flew behind it → give it time, re-route the artwork |
| SAFE during an entrance | An underdamped spring overshot the margin → ease-out for entrances that start at a margin |
| DEAD-TIME inside a busy-looking station | Small labels change only ~0.1/255 of the frame → camera push-ins on cues, or bigger moving elements; never animated grain |
| A pack fails CONTRAST/SAFE the default passed | Fill colour reused as text, or a wider font → darker text role, wrap widths |
| Sparse next to a reference | Fewer edges / grid cells in `profile-compare` → kicker + headline + description + a working mechanism per beat, persistent HUD, real data |

8. **Report** the commands actually run, artifact paths, the failing and unmeasured requirement
   IDs, and that human reviews stay pending until the named reviewer decides. Never approve a human
   criterion yourself.
