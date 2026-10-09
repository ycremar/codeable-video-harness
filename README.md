# Codeable Video Harness

A small, runnable **brief → contract → code → render → measure → inspect → revise**
system for Opus, GPT or any coding agent. The agent writes a web page that draws any
moment from `t` and synthesizes its own sound. Headless Chromium photographs every
frame and FFmpeg encodes them. The harness then measures the encoded file against
requirements frozen before the render.

**Important:** any requirement can be *represented* and traced, but not every
requirement can be objectively automated. Unknown metrics are `unmeasured`, not
success. Subjective craft needs an explicit, artifact-bound review.

**Nothing here is a template.** The example films are evidence that the loop works,
not a look, structure, motion grammar or sound palette to reuse. The harness ships no
sound presets and no scene library. Each film invents its own look, motion and sound
for its brief; the harness only checks that the result is correct, measurable and
honest.

## How it works

A [study of 475 public code-rendered videos](docs/OPUS_VIDEO_RESEARCH.md) found the same core
recipe across HyperFrames, Remotion and single-file builds. This harness runs it inside an evidence
model:

1. **Contract.** Requirements are hard checks, named proxies or human rubrics, frozen before
   rendering. `timing.hits` is the film's cue sheet.
2. **Composition.** A page in `compositions/<name>/` exposes a pure `window.__vch.seek(t)`, and with
   `audio.mode: "composition"` a `window.__vch.audio(...)` that returns the film's own synthesized
   samples. Licensed files can be used instead (`mix`, `file`).
3. **Capture.** Chromium has a virtual clock, seeded randomness, loopback-only networking and DOM
   text telemetry. FFmpeg encodes H.264 + AAC.
4. **Measure.** The harness decodes its own MP4. It measures:
   - frames, timestamps, motion and pops;
   - loudness, true peak and cue sync on the encoded audio;
   - text size, contrast, safe area and overlap from telemetry.
   Seeks are checked forward, reverse and shuffled on pixels and telemetry.
5. **Review.** Human requirements stay pending until a reviewer decides on the bound artifact.

## Setup

Python 3.11+, FFmpeg/ffprobe with libx264, and Chromium through Playwright. Rendering is offline
and calls no model.

```sh
python -m pip install -r requirements.txt playwright==1.51.0
python -m playwright install chromium
python -m unittest discover -s tests -v                      # browser tests: VCH_TEST_BROWSER=1
```

## Commands

```sh
python -m vch validate examples/how-code-becomes-video.json
python -m vch packet examples/how-code-becomes-video.json     # authoring packet for a coding agent
python -m vch storyboard examples/how-code-becomes-video.json # timestamped plan from the contract
python -m vch stills examples/how-code-becomes-video.json --times 9.9,21.9,40.5 --motion --out runs/hc-stills-001 --trust-scene-code
python -m vch sound examples/how-code-becomes-video.json --out runs/hc-sound-001 --trust-scene-code
python -m vch run examples/how-code-becomes-video.json --out runs/hc-001 --trust-scene-code
python -m vch evaluate runs/hc-001 --review runs/hc-001/review.json
python -m vch audit runs/hc-001 --project-root .
python -m vch compare runs/hc-001 runs/hc-002
python -m vch profile runs/hc-001/video.mp4 --out runs/hc-001-profile
python -m vch profile-compare reference-profile/profile.json runs/hc-001-profile/profile.json
python -m vch diversity runs/hc-001 runs/three-prism-001
```

- `stills` renders chosen times, or one frame per beat, before paying for a full render.
- `sound` renders only the audio and reports loudness, true peak and every cue's sync error.
- `profile` measures any video or audio file, such as a licensed reference, a song or a
  candidate. It reports cuts, visual events, holds, pops, loudness, onsets, tempo and phase,
  plus detail proxies: edge density, grid coverage and colourfulness.
- `profile-compare` puts two profiles side by side.
- `diversity` measures how far apart films' colour and detail are.

None of these are quality scores or a licence to copy style.

**Exit codes.** Exit **3 is intentional** when all machine checks pass but human review remains.
Exit 2 means blocked or invalid, and exit 0 means accepted under the written contract. Never read
"an MP4 was produced" as "every requirement passed".

**Run folders.** Existing run folders are never overwritten; use a fresh suffix per revision. Do not
edit project files while `vch run` renders, because the source check then invalidates the run.

**What to inspect.** Each run folder holds `video.mp4`, `contact-sheet.jpg` (from the **encoded
MP4**), `frames/`, `report.md`, `report.json`, `trace.jsonl`, `evidence.json`, `manifest.json`,
`render.log` and `review.template.json`, plus `audio.wav` when the run synthesizes or mixes sound.

**Reviews.** Copy the review template to a separate filename and record real decisions with
timestamp or frame evidence. Review bindings include the contract, source inventory, encoded video,
trace and evidence, so a changed render invalidates the old review. Integrity is hash-based, not
tamper-proof authenticated approval. The comparison refuses changed requirement sets.

## Example films

Seven original films. Each has its own picture and its own synthesized sound, and none of them is
a starting point for the next film.

- **`examples/how-code-becomes-video.json`**: a 48-second 1080p explainer of how these videos are
  made, built the same way.
  - One continuous camera travels over one world.
  - Every number on screen is read at load time from the contract, the composition's own source, or
    `corpus.json`.
  - Its 74 cues time the picture and its own four sound families. The SOUND station draws the cue
    sheet and the waveform of the landing sound heard at that moment.
  - It takes style packs: `--style styles/paper-swiss.json` or `--style styles/phosphor-terminal.json`.
- **`examples/three-*.json`**: six 8-second three.js clips with real lighting, materials and lens
  effects: prism, studio, city, orbit, pulse and paper.
  - Each synthesizes its own sound for its subject: light and glass, studio gear, urban dusk, deep
    space, a drum machine, paper and wood.
  - Three.js is vendored under `compositions/_vendor/` and declared as one folder asset.

```sh
python -m vch run examples/three-prism.json --out runs/three-prism-001 --trust-scene-code
```

## Using a coding agent

Open this repository with your coding agent. Give it the brief, a contract, and the output of
`python -m vch packet <contract>`, and ask it to follow `AGENTS.md`. It writes and repairs
compositions, runs the render and inspects evidence with its normal tools. No proprietary SDK or
model name is hardcoded, and the CLI never calls a model.

Claude Code users get the `codeable-video` skill (`.claude/skills/`) and `CLAUDE.md` → `AGENTS.md`.

## What is implemented

- Strict structural validation: frames, timeline, cue sheet, rights records and trust opt-in.
- An HTML composition renderer:
  - virtual clock and seeded randomness;
  - seek adapters (`__vch.seek`, `window.seek`, paused `__timelines`, CSS/Web Animations);
  - DOM/SVG text telemetry with pixel-backed contrast;
  - loopback-only networking and declared folder assets for vendored libraries;
  - optional sub-frame motion blur in linear light;
  - `console.error` treated as a failure.
- Composition-authored audio (`window.__vch.audio`), `mix` audio placing licensed layers by
  measured peak, and linear loudness targeting under a peak ceiling.
- Hard technical checks, labelled telemetry and pixel proxies, and review gates.
- Decoded-evidence metrics:
  - BS.1770 loudness and true peak after encoding;
  - frame count and timestamp jitter;
  - text overlap, dead time, single-frame pops and loop seam;
  - cue sync.
- Encoded-frame QA, contract and source hashes, immutable run directories.
- Previews (`stills`, `sound`), storyboards, media profiles, style packs and diversity
  descriptors.
- Unit and integration tests, including unknown metrics, bad typography, tampering, stale reviews,
  state carried between frames, and composition audio.

## Scope boundaries

- **Runtimes and media.** The renderer does not run HyperFrames or Remotion runtimes. It does not
  interpret `data-start` clip attributes or manage `<video>` seeking.
- **No generation.** It calls no image, video, music or speech generation API.
- **Loudness.** Targeting is one linear gain with no limiter, so a peak ceiling can stop a target
  from being reached; that is reported, not hidden.
- **Cue sync.** It is checked only against declared hits, because blind audio/visual sync on
  published files measured at chance level. `beat_cut_error_ms` uses the declared beat grid.
  `vch profile` estimates tempo and phase but not downbeats or meter.
- **Not measured.** There is no ASR, semantic fact checker, audience study, universal aesthetics
  metric, full flash-safety certification, platform publishing or hosted scheduler.
- **OCR** is optional and requires Tesseract plus the requested language pack.

Composition code is trusted executable code. `--trust-scene-code` is an acknowledgement, not a
sandbox. Chromium runs with its sandbox on (`VCH_CHROMIUM_NO_SANDBOX=1` only where a container
requires it), but that is defence in depth, not an OS boundary: use a disposable container or VM
with no secrets and no network for agent-written code. Sampled checks cannot prove all possible
times or every visual claim. A malicious composition can lie in telemetry, so inspect decoded
frames independently.

## Repository map

| Path | Purpose |
|---|---|
| `vch/` | Contract validation, renderer, audio mastering, evaluator, CLI |
| `vch/html_backend.py`, `vch/html_runtime.js` | Chromium capture and the injected seek/audio/telemetry runtime |
| `vch/signals.py`, `vch/audio.py`, `vch/tools.py` | Decoded-media signals, mastering, stills/sound/storyboard/profile tools |
| `compositions/` | Agent-written films; `_lib/` (pure-time and sound mechanics) and `_vendor/` (three.js) are read-only for authors |
| `styles/` | Style packs (design tokens by role) that compositions can read from `contract.style` |
| `examples/` | Contracts: requirements, timing and style inputs, not visual or sonic templates |
| `docs/AUTHORING.md` | Seek and sound protocols, correctness rules, what the checks see |
| `docs/MEASUREMENT.md` | Metric meanings, coverage and anti-Goodhart rules |
| `docs/OPUS_VIDEO_RESEARCH.md` | Corpus study of public code-rendered videos |
| `.claude/skills/codeable-video/` | Claude Code skill for the production loop |
| `assets/fonts/` | OFL fonts and notices |
| `tests/` | Positive and deliberate-failure tests |

Repository code: MIT. Vendored three.js keeps its MIT notice. Fonts: included SIL OFL notices.
FFmpeg, Chromium, Playwright, Pillow and NumPy keep their own licences. Reference recordings and
films are **not** licensed by this repo and are not redistributed.
