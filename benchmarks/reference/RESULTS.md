# Reference-capability benchmark

Baseline: commit `80d9b93` rejected `vch produce --prompt ...`; its CLI only accepted
hand-authored contracts and its demonstrations had no narration or browser backend.
It could not demonstrate the requested one-prompt reference-scale production.

This branch adds a bounded author/render/repair protocol, a real browser adapter
executing MIT pdoom primitives, local Mandarin TTS, phrase captions, immutable
attempts and checks that do not manufacture an aesthetic score.

The candidate in this folder was authored in the current coding-agent session.
Replaying it is not a fresh live model call. The cloud environment had no
configured GPT/Opus API credentials or authenticated standalone author CLI. Thus
unattended model generation and broad prompt generalization remain unverified.

The fixed benchmark is 192 seconds, 1280×720, 30 fps, 16 scenes and at least eight
visual mechanisms. Those counts are only proxies. Local verification now passes
52 tests, including real browser encoding and exact-pixel seek checks across all
16 scene windows. The replacement full render (session 004) passes all 17 machine
requirements and remains `needs_review` for the three human criteria. The CLI
returned its documented exit code 3. Artifact integrity audit also passed.

## Final encoded result — 2026-10-03

| Measurement | Observed result |
|---|---|
| MP4 | 192.000 seconds, 1280×720, 30 fps, H.264 video + AAC audio |
| Encoded frames | 5,760 |
| Seek determinism | 0 mismatches across 64 sampled timestamps, forward/reverse/shuffled |
| Safe-area telemetry | 0 text violations over all frames |
| Minimum text size / declared contrast | 22 px / 6.2625 |
| Sampled decoded-frame MAE | 1.6980 on a 0–255 scale; target ≤8 |
| Speech placements | 160.599 seconds |
| Caption placement error | 0 ms against synthesized phrase schedule; not word alignment |
| Decoded sample peak | −2.916 dBFS; not true-peak or loudness certification |
| Scene windows / declared kinds | 16 / 13; breadth proxies only |
| Human criteria | CRAFT, VOICE, COMPREHENSION all pending |

Final video SHA-256:
`1049f48032404f3f072f5d11253d73209e1ebf83d8f1697a16646d6ef043704d`

The 14,741,764-byte MP4 is delivered with the task, rather than committed to Git.
[Machine report](evidence/report.json) and [source/runtime manifest](evidence/manifest.json)
bind the recorded result to that exact artifact. Replays may differ across runtime
versions/platforms; exact seek determinism is checked within each run.
The executing code matches commit
[`d79cf1d`](https://github.com/ycremar/codeable-video-harness/commit/d79cf1d0c096d0120cfef40abe0e595a4ba57246).
Both [core CI](https://github.com/ycremar/codeable-video-harness/actions/runs/37159893279)
and [browser CI](https://github.com/ycremar/codeable-video-harness/actions/runs/37159893346)
passed for that commit. The final follow-up commit contains documentation and
recorded evidence only.

## Failures found and repaired

Speech preflight caught narration exceeding two 12-second scene windows. The
script was shortened; the frozen duration and requirements were not changed.
Sessions 001 and 002 record the same remaining overflow and are retained.

The first completed MP4 (session 003) passed 16 of 17 machine checks but failed
exact-pixel seek determinism at 12 sampled visits. Reproduction localized the
differences to raster pixels; text metadata matched. Explicitly resetting the
Canvas2D context for each frame and selecting a readback-oriented context removed
all differences across the same 64 timestamps in forward/reverse/shuffled orders.
The new regression test covers the full visual vocabulary; the earlier one-scene
smoke test had missed this. No mismatch tolerance or requirement was weakened.
The failed report and source manifest are retained under [evidence](evidence/).

## What the test establishes

| Question | Evidence / remaining limitation |
|---|---|
| Can the old CLI accept one prompt? | No: baseline `vch produce --prompt ...` was rejected. |
| Is there a one-prompt path now? | Yes: `scripts/one_prompt.py` extracts proposed constraints, freezes them, and runs production/repair. End-to-end fixture coverage passes. |
| Is live GPT/Opus generation proven? | No. Concrete OpenAI Responses/Anthropic Messages adapters are included and fixture-tested, but no authenticated live call was available or made. |
| Is the benchmark independent fresh model generation? | No: it replays a candidate authored by this coding agent from the fixed prompt. |
| Does this use pdoom-video? | It executes pinned MIT FSPass primitives with original compositions, not the complete upstream Engine/post stack. |
| Does it equal the reference's craft? | Not demonstrated. Actual decoded frame inspection shows readable compositions, but much more repeated header/body structure and less cinematic variety. |
| Was audio listened to? | No. The available inspection interface did not support audio input. Sample-peak, duration and phrase placement measurements do not establish voice quality. |

The agent inspected decoded midpoint frames for every scene, plus full-size
frames at 42s and 150s. The reference has stronger visual hierarchy changes and
more varied staged objects. The candidate repeats graph spheres and card layouts;
13 declared kinds therefore must not be read as 13 distinct creative mechanisms.
Static frame inspection also cannot certify motion quality or normal-speed
comprehension. Human craft, voice quality and comprehension criteria remain
pending. This is not a claim of creative parity with the reference.

For the next independent test, configure a model with image input and run the
one-prompt command in [PRODUCTION_SETUP.md](../../docs/PRODUCTION_SETUP.md). Use an
explicitly authorized API budget and an isolated worker. Preserve the original
prompt, frozen contract, failures, model-returned identity/usage and actual MP4.
Broader prompts and full-motion/audio review are required before generalizing
this benchmark to “one prompt reliably makes reference-quality films.”
