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
| Render engine | pdoom-video | Python/Pillow plus tested browser adapter executing pdoom FSPass primitives |
| Encode | FFmpeg | FFmpeg |
| Evaluation | Visual iteration described on screen | Requirement contracts, evidence, tests and review gates |

This repository implements production/evaluation orchestration and two render
backends. The browser adapter vendors a small, pinned MIT subset of pdoom-video;
it does **not** use the complete upstream Engine or its film assets. See
[pdoom engine notes](docs/PDOOM_ENGINE.md) for the precise boundary.

## One prompt: current status

The original v0.1 CLI did not accept prompts and could not make a reference-scale
narrated film. The new production path accepts a brief, freezes requirements,
invokes a configured author, synthesizes Mandarin narration locally, renders and
measures the encoded output, then feeds failures back for bounded repairs.

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
- CLI for authoring packets, stills, render, evaluate, audit and comparison.
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
phrase durations; automatic word-level forced alignment is not implemented. Beat checks use the declared beat grid, not
detected onsets from arbitrary music.

Scene code is trusted executable Python. `--trust-scene-code` is an acknowledgement,
not a sandbox. Use a disposable container/VM with no secrets and no network for
agent-written code. Sampled checks cannot prove all possible times or every visual
claim. A malicious scene can lie in telemetry; inspect decoded frames independently.

## Repository map

| Path | Purpose |
|---|---|
| `vch/` | Contract, production loop, narration, renderers, evaluator, CLI |
| `backends/pdoom/` | Original browser scene system + pinned MIT pdoom primitives |
| `benchmarks/reference/` | Prompt, fixed contract, saved response and execution results |
| `scenes/` | Agent-editable pure-time scene modules |
| `examples/` | Requirements + style + timing, not hardwired visual templates |
| `docs/REVERSE_ENGINEERING.md` | Recording evidence vs verified engine vs additions |
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
