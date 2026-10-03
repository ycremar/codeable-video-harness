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
| Render engine | pdoom-video | Tested Python/Pillow backend; pdoom adapter not implemented |
| Encode | FFmpeg | FFmpeg |
| Evaluation | Visual iteration described on screen | Requirement contracts, evidence, tests and review gates |

This repository implements the production/evaluation harness and a lightweight
reference backend. It is **not a fork or reimplementation of pdoom-video's GPU
engine**. See [pdoom engine notes](docs/PDOOM_ENGINE.md) for the upstream entry
points and the integration boundary. The current demos are Python renders.

## Run it

Python 3.11+, FFmpeg/ffprobe with libx264. Runtime is offline and model-free.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m vch validate examples/explainer.json
python -m vch packet examples/explainer.json
python -m vch run examples/explainer.json --out runs/explainer-001 --trust-scene-code
python -m vch run examples/atl.json --out runs/atl-001 --trust-scene-code
python -m vch run examples/broken.json --out runs/broken-001 --trust-scene-code
```

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
normal tools. No proprietary SDK/model name is hardcoded. This is an executable
agent workbench, **not an autonomous hosted model service**. No paid API call or
provider model selection was performed to test this repository.

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

Only the Pillow/CPU backend is implemented and tested. The artifact/evaluation
boundary permits other engines, but there is **no tested Three.js/Remotion/Blender
adapter here**. The upstream pdoom engine supports richer GPU scenes and adaptive
sampling; this repository neither vendors it nor claims equivalent visual range.

No automatic TTS/ASR, semantic fact checker, audience study, universal aesthetics
metric, full flash-safety certification, platform publishing or hosted scheduler.
OCR is optional and requires Tesseract plus the requested language pack. Voice
assets can enter as licensed audio with externally produced timing; automatic
forced alignment is not implemented. Beat checks use the declared beat grid, not
detected onsets from arbitrary music.

Scene code is trusted executable Python. `--trust-scene-code` is an acknowledgement,
not a sandbox. Use a disposable container/VM with no secrets and no network for
agent-written code. Sampled checks cannot prove all possible times or every visual
claim. A malicious scene can lie in telemetry; inspect decoded frames independently.

## Repository map

| Path | Purpose |
|---|---|
| `vch/` | Contract, renderer, evidence pipeline, evaluator, CLI |
| `scenes/` | Agent-editable pure-time scene modules |
| `examples/` | Requirements + style + timing, not hardwired visual templates |
| `docs/REVERSE_ENGINEERING.md` | Recording evidence vs verified engine vs additions |
| `docs/PDOOM_ENGINE.md` | pdoom-video attribution, native workflow and integration limits |
| `docs/MEASUREMENT.md` | Metric meanings, coverage and anti-Goodhart rules |
| `docs/AUTHORING.md` | Brief-to-code and repair protocol |
| `assets/fonts/` | Original OFL fonts and notices |
| `tests/` | Positive and deliberate failure tests |

Repository code: MIT. Fonts: their included SIL OFL notices. FFmpeg, Pillow and
NumPy retain their own licenses. Source recording, original film, music, voices,
lyrics and screenshots are **not** licensed by this repo and are not redistributed.
