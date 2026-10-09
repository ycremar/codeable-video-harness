# Codeable Video Harness

A small, runnable **brief → contract → code → render → measure → inspect → revise**
system for Opus, GPT or any coding agent. Original implementation; inspired by the
production method explained in the user's recording, not its visual style.

**Important:** any requirement can be *represented* and traced, but not every
requirement can be objectively automated. Unknown metrics are `unmeasured`, not
success. Subjective craft needs an explicit, artifact-bound review.

## Renderer attribution and implementation status

The reference film credits **[pdoom-video](https://github.com/mexicat/pdoom-video)**
as its rendering engine. That project uses TypeScript/Three.js, a browser runtime
and FFmpeg export. Opus/GPT authors code; it is not the pixel-rendering engine.

| Layer | In the reference / upstream | In this repository |
|---|---|---|
| Code author | The film claims Opus; exact model provenance unverified | Any coding agent through the authoring packet |
| Render engine | pdoom-video | Python/Pillow; browser adapter executing pdoom FSPass primitives; HTML composition backend (Chromium) |
| Encode | FFmpeg | FFmpeg |
| Evaluation | Visual iteration described on screen | Requirement contracts, evidence, tests and review gates |

This repository implements production/evaluation orchestration and three render
backends. The browser adapter vendors a small, pinned MIT subset of pdoom-video;
it does **not** use the complete upstream Engine or its film assets. See
[pdoom engine notes](docs/PDOOM_ENGINE.md) for the precise boundary.

## One prompt: current status

The original v0.1 CLI did not accept prompts and could not make a reference-scale
narrated film. The new production path accepts a brief, freezes requirements,
invokes a configured author, synthesizes Mandarin narration locally, renders and
measures the encoded output, then feeds failures back for bounded repairs.
`scripts/one_prompt.py` accepts just the free-form creative prompt plus runtime
configuration, proposes and freezes a contract, and retains human prompt-fidelity
review. Optional GPT/Opus API adapters are included; their live model path is
unverified here.

- [Single-prompt protocol](docs/SINGLE_PROMPT.md)
- [Installation and benchmark replay](docs/PRODUCTION_SETUP.md)
- [Fixed benchmark prompt](benchmarks/reference/prompt.txt) and
  [frozen requirements](benchmarks/reference/constraints.json)
- [Benchmark result and limitations](benchmarks/reference/RESULTS.md)

A saved candidate replay is **not** fresh LLM generation. The recorded benchmark
was authored in the current coding-agent session without further user creative
input. A standalone live GPT/Opus run still needs an authenticated author command;
that model path was unavailable in this cloud environment. Human craft, speech
quality and reference-parity judgments remain separate from machine checks.

The completed benchmark is **192 seconds at 720p/30 fps**, with Mandarin speech
and captions. All 17 machine requirements pass; three human criteria remain
pending. All 52 local tests pass, including browser integration. The first full
render caught an order-dependent canvas bug; its failed report and the passing
rerender evidence are retained. This is progress toward the reference's ambition,
not a claim of equal creative quality.

## HTML compositions: how most public "Opus 5.5" videos are made

A [study of 475 public code-rendered videos](docs/OPUS_VIDEO_RESEARCH.md) found the
same core recipe across HyperFrames, Remotion and single-file builds:

- An agent writes a web page that exposes a pure `seek(t)`.
- Headless Chromium captures it frame by frame, sometimes with blended sub-frames.
- FFmpeg encodes the result.
- Sounds are placed by their measured transient peak.
- Stills or one frame per beat are checked before the full render.

The study also covers the requested [@mattworkman](https://skillry.dev/ai-videos/opus-5-5/mattworkman-309357)
video: a fal-generated hero clip wrapped in a Three.js explainer that reuses the
generated image as data.

The `html` backend runs that medium inside this harness's evidence model. Visible
text is measured from the DOM, and seeks are checked forward/reverse/shuffled on
pixels and telemetry. Network access is limited to loopback, and the harness measures
the encoded MP4 rather than the browser preview.

```sh
python -m pip install -r requirements.txt playwright==1.51.0
python -m playwright install chromium
python -m vch storyboard examples/html.json
python -m vch stills examples/html.json --beats --out runs/stills-001 --trust-scene-code
python -m vch run examples/html.json --out runs/code-to-frames-001 --trust-scene-code
python -m vch profile runs/code-to-frames-001/video.mp4 --out runs/profile-001
```

Two original HTML examples:

- **`examples/how-code-becomes-video.json`**: `compositions/how-code-becomes-video/`, a 48-second
  1080p explainer of how these videos are made, built the same way.
  - One continuous camera over one world: a 475-tile wall, five stations a card travels through,
    and dots for 38 measured files.
  - Every number on screen is read at load time from the contract, the composition's own source,
    or `corpus.json`.
  - Its 74 cues also time the picture. A chord bed is ducked under each cue.
  - It passes all 22 machine requirements: loudness −16.7 LUFS after encode, worst cue 9 ms from
    its detected peak, 24 px minimum text, 4.8:1 minimum contrast, longest still hold 1.17 s.
  - Two human reviews stay pending: craft, and whether every number traces to its source.
  - It renders in about 6 minutes.

  ```sh
  python -m vch stills examples/how-code-becomes-video.json --times 9.9,21.9,40.5 --motion --out runs/hc-stills-001 --trust-scene-code
  python -m vch run examples/how-code-becomes-video.json --out runs/hc-001 --trust-scene-code
  python -m vch profile runs/hc-001/video.mp4 --out runs/hc-001-profile
  python -m vch profile-compare reference-profile/profile.json runs/hc-001-profile/profile.json
  ```

  The same film takes style packs: `--style styles/paper-swiss.json` or
  `--style styles/phosphor-terminal.json`. `vch diversity` measures how far apart the variants are.

- **`examples/three-*.json`**: six 8-second three.js clips with real lighting, materials and lens
  effects: prism, studio, city, orbit, pulse and paper. Each passes the same machine checks, and
  `vch diversity` puts them as far apart as typical corpus films. Three.js is vendored under
  `compositions/_vendor/` and declared as one folder asset.

  ```sh
  python -m vch run examples/three-prism.json --out runs/three-prism-001 --trust-scene-code
  ```

- **`examples/html.json`**: `compositions/code-to-frames/index.html`, a 12-second minimal film used
  by the browser tests:

- Cue sounds are synthesized on 19 declared hits.
- Its contract passes 20 machine requirements: duration, frame count, timestamps,
  loudness and true peak after AAC encoding, seek determinism, hit sync, copy, size,
  contrast, safe area, text overlap, dead time and single-frame pops.
- The run exits 3 because the human craft review stays pending.

Its first full render failed the seek check on a cached-DOM bug, and exposed
Chromium partial-raster nondeterminism. Both were fixed without changing the
thresholds.

`vch profile` measures any video or audio file, such as a licensed reference, a
song or your candidate. It reports cuts, visual events, holds, pops, loudness,
onsets, tempo and phase, plus detail proxies: edge density, grid coverage and
colourfulness. `vch profile-compare` puts two profiles side by side. Profiles
describe pacing and density; they are not quality scores or a licence to copy style.

Claude Code users get the `codeable-video` skill (`.claude/skills/`) and
`CLAUDE.md` → `AGENTS.md`.

## Run the lightweight backend

Python 3.11+, FFmpeg/ffprobe with libx264. Runtime is offline and model-free.

```sh
python scripts/prepare_fonts.py
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m vch validate examples/explainer.json
python -m vch packet examples/explainer.json
python -m vch run examples/explainer.json --out runs/explainer-001 --trust-scene-code
python -m vch run examples/atl.json --out runs/atl-001 --trust-scene-code
python -m vch run examples/broken.json --out runs/broken-001 --trust-scene-code
```

The full CJK font is stored losslessly as `NotoSerifSC.ttf.xz` to keep each upload
below the connector's request limit. `prepare_fonts.py` restores the original
25,125,512-byte font offline and verifies SHA-256; it does not subset or modify
glyphs. Run it once after cloning. CI and the Docker recipe include this step.

Exit **3 is intentional** when all machine tests pass but human review remains.
Exit 2 = blocked/invalid. Exit 0 = accepted under the written contract. Never
interpret 'an MP4 was produced' as 'every requirement passed'. Existing run folders
are not overwritten. Use a fresh suffix per revision.

The broken example intentionally returns exit 2: it has tiny, low-contrast,
out-of-bounds text, a forbidden booking claim and an undefined `shock_score`.
It is a negative control, not a suggested design. A failed human review also
blocks acceptance; pending review and rejection are different states.

For a frame before the full render:

```sh
python -m vch still examples/explainer.json --time 2.1 --out runs/check.png --trust-scene-code
```

Inspect `video.mp4`, `contact-sheet.jpg`, `frames/`, `report.md`, `report.json`,
`trace.jsonl`, `evidence.json`, `manifest.json`, `render.log` and
`review.template.json`. The contact sheet comes from the **encoded MP4**.

Copy the review template to a separate filename, record real decisions with
timestamp/frame evidence, then:

```sh
python -m vch evaluate runs/explainer-001 --review runs/explainer-001/review.json
python -m vch audit runs/explainer-001 --project-root .
python -m vch compare runs/explainer-001 runs/explainer-002
```

The comparison refuses changed requirement sets. Review bindings include contract,
source inventory, encoded video, trace and evidence. A changed render invalidates
the old review. Integrity is hash-based, not tamper-proof authenticated approval.

## Using Opus/GPT

Open this repository with your coding agent. Give it the brief, a contract, and
the output of `python -m vch packet <contract>`. Ask it to follow AGENTS.md. It
writes/repairs scene modules, executes rendering and inspects evidence using its
normal tools. No proprietary SDK/model name is hardcoded. `vch produce --author-command` can
call an approved external model adapter and run a repair loop. The subprocess
protocol was exercised with deliberate-failure fixtures; no paid model API call
or independently authenticated hosted model generation was performed.

## What is implemented

- Strict structural validation: frames, timeline, rights records and trust opt-in.
- Pluggable Python frame renderer with shared `Frame(image, elements)` interface.
- Pure-time seeded animation; random-order seek tests; fixed sub-frame blur in
  linear light. Color-tagged H.264 output, optional original synthesized percussion
  or licensed audio input; complete-duration checks for supplied audio.
- Hard technical checks, labeled instrumentation/pixel proxies and review gates.
- Actual encoded-frame QA, contract/source hashes, immutable render directories.
- CLI for authoring packets, stills (single, per-beat or listed times), storyboards,
  media profiles, render, evaluate, audit and comparison.
- HTML composition backend with a virtual clock, seeded randomness, seek adapters
  (`__vch.seek`, `window.seek`, paused `__timelines`, CSS/Web Animations), DOM/SVG
  text telemetry with pixel-backed contrast, loopback-only networking and optional
  sub-frame motion blur.
- Declared `timing.hits` with original synthesized cues; `mix` audio placing
  licensed layers by measured peak; linear loudness targeting with a peak ceiling.
- Decoded-evidence metrics: BS.1770 loudness and true peak after encoding, frame
  count and timestamp jitter, text overlap, dead time, single-frame pops, loop seam
  and hit sync.
- Landscape explanation + portrait Chinese ATL example; intentional broken scene.
- Unit/integration tests including unknown metrics, bad typography, tampering,
  stale reviews and stateful/non-deterministic rendering.

## Scope boundaries

The Pillow backend and pdoom primitive browser adapter are implemented. The
browser path renders native-resolution text/diagrams and a half-resolution soft
shader backdrop, reported in its manifest. It does not implement upstream adaptive
sampling, full post-processing, arbitrary native pdoom scene loading, or Blender.
The full upstream engine still has a richer visual range.

Local Mandarin TTS and phrase-timed captions are implemented. There is no ASR,
semantic fact checker, audience study, universal aesthetics metric, full flash
safety certification, platform publishing or hosted scheduler.
OCR is optional and requires Tesseract plus the requested language pack. Voice
assets can also enter as licensed audio. Captions for local TTS use actual
phrase durations; automatic word-level forced alignment is not implemented. `beat_cut_error_ms` uses
the declared beat grid; `audio_hit_sync_ms` compares declared hits with transient peaks detected in
the encoded audio; `vch profile` estimates tempo and phase from audio but not downbeats or meter.

The HTML backend does not run HyperFrames or Remotion runtimes. It does not
interpret `data-start` clip attributes or manage `<video>` seeking, and it calls
no image, video, music or TTS generation APIs. Loudness targeting is one linear
gain: there is no limiter, so a peak ceiling can stop a target from being reached,
and that is reported. Blind audio/visual sync on published files measured at
chance level, which is why hit sync is checked only against declared hits.

Scene code is trusted executable Python. `--trust-scene-code` is an acknowledgement,
not a sandbox. Use a disposable container/VM with no secrets and no network for
agent-written code. HTML compositions run inside Chromium with its sandbox on
(`VCH_CHROMIUM_NO_SANDBOX=1` only where a container requires it), but that is
defence in depth, not an OS boundary for untrusted code. Sampled checks cannot prove all possible times or every visual
claim. A malicious scene can lie in telemetry; inspect decoded frames independently.

## Repository map

| Path | Purpose |
|---|---|
| `vch/` | Contract, production loop, narration, renderers, evaluator, CLI |
| `vch/html_backend.py`, `vch/html_runtime.js` | HTML composition renderer and injected seek/telemetry runtime |
| `vch/signals.py`, `vch/audio.py`, `vch/tools.py` | Decoded-media signals, cue/mix audio, stills/storyboard/profile tools |
| `compositions/` | Agent-editable HTML compositions (`how-code-becomes-video`, `code-to-frames`) |
| `styles/` | Style packs (design tokens by role) that compositions read from `contract.style` |
| `backends/pdoom/` | Original browser scene system + pinned MIT pdoom primitives |
| `benchmarks/reference/` | Prompt, fixed contract, saved response and execution results |
| `scenes/` | Agent-editable pure-time scene modules |
| `examples/` | Requirements + style + timing, not hardwired visual templates |
| `docs/REVERSE_ENGINEERING.md` | Recording evidence vs verified engine vs additions |
| `docs/OPUS_VIDEO_RESEARCH.md` | Corpus study of public Opus 5.5 code-rendered videos and what changed here |
| `.claude/skills/codeable-video/` | Claude Code skill for the production loop |
| `docs/PDOOM_ENGINE.md` | pdoom-video attribution, native workflow and integration limits |
| `docs/MEASUREMENT.md` | Metric meanings, coverage and anti-Goodhart rules |
| `docs/AUTHORING.md` | Brief-to-code and repair protocol |
| `assets/fonts/` | Original OFL fonts and notices |
| `tests/` | Positive and deliberate failure tests |

Repository code: MIT; vendored pdoom primitives retain their own MIT notice.
Fonts: included SIL OFL notices. Optional speech models/dependencies retain their
own licenses; see PRODUCTION_SETUP.md. FFmpeg, Pillow and
NumPy retain their own licenses. Source recording, original film, music, voices,
lyrics and screenshots are **not** licensed by this repo and are not redistributed.
