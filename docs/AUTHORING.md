# Opus/GPT authoring protocol

## Input packet

Use `python -m vch packet examples/explainer.json` with either coding agent.
Include the following brief fields (do not let missing facts be invented):

- Goal, audience, distribution placement and call to action.
- Verified facts and prohibited/unconfirmed claims, with source URLs/dates.
- Target dimensions, duration, fps and platform-specific safe region.
- Tone and visual direction **for this project**, not the reference video.
- Available real assets with rights, brand mark and fonts.
- Narration script/music rights or explicit silence/procedural-audio choice.
- Hard acceptance checks, candidate proxies, human rubrics and reviewer.
- Resource/cost ceiling and maximum repair attempts.

## Authoring prompt

“Read AGENTS.md and this contract. Propose a short scene/timing plan that maps every
requirement ID to visual/audio evidence. Implement only the scene/assets scope.
Keep the requirements and evaluator unchanged. Do not copy the reference's style.
Render representative stills, inspect them, then run and evaluate the actual MP4.
For each failure, explain and patch the concrete cause, up to three iterations.
Return artifact paths, real commands, remaining failures and unmeasured items.
Leave designated human reviews pending. Do not claim a provider/model choice
unless your runtime exposes it.”

## Scene contract

`render(ctx) -> Frame(image, elements)`; `ctx` includes global/local time, scene
progress, explicit seed, scene parameters, project root and full contract.

Use `Canvas.text` for instrumented typography. Other artwork may use arbitrary
Pillow geometry or a separately reviewed engine returning an RGB PIL image.
`elements` is a trace, not a rendering command list: keep it honest and complete.
The renderer does not require any particular composition or palette.

Seeded variation uses `noise(seed, key)`. All motion is computed from time. A
particle trajectory should be analytically evaluated or deterministically rebuilt,
not advanced from whichever frame happened to be rendered previously.

Scene windows are frame-aligned, ordered and contiguous in v1. Overlapping
transitions must be authored inside a scene; arbitrary cross-scene overlap is
rejected. Full frame pixels are returned, never drawn incrementally onto old frames.

Fixed subframe samples average in linear light. Sample times are clipped to the
scene boundary to avoid bleeding across cuts. More samples cost more compute;
adaptive GPU sampling and general stateful simulations are not implemented.

## HTML compositions (`backend: "html"`)

This is the medium most code-rendered launch films use: HTML, CSS, SVG, Canvas or WebGL (GSAP
and Three.js are common) that exposes a pure `seek(t)`. See
[OPUS_VIDEO_RESEARCH.md](OPUS_VIDEO_RESEARCH.md). Declare:

```json
"backend": "html", "html": {"entry": "compositions/<name>/index.html"}
```

Scenes still declare contiguous windows; `module` is optional. Windows drive sampling,
beat-grid and storyboard checks. Example: `examples/html.json` →
`compositions/code-to-frames/index.html`.

**Seek protocol.** Define `window.__vch.seek = (t) => { … }`, or `window.seek`. It may be async,
and must set every visual property from `t`. Optionally:

- Set `window.__vch.ready` to a promise; it is awaited before frames are drawn.
- Register paused GSAP-like timelines on `window.__timelines`; they are seeked to `t`.
- CSS and Web Animations are paused at `t`. CSS transitions are finished.

**Provided before your scripts run:**

- `__vch.harness`, `seed`, `fps`, `width`, `height`, `duration`, and `noise(key)` (stateless
  seeded randomness).
- Virtual clocks: `performance.now`, `Date` and rAF timestamps all equal composition time.
- A seeded `Math.random` per page load.

**Rules.** Most come from failures recorded in the corpus or caught by this harness.

- **No state carried between frames.** That includes timers, accumulators and DOM caches keyed on
  the previous frame. The forward/reverse/shuffled seek check compares pixels *and* telemetry. The
  example's first full render failed it on a cached headline.
- **Closed-form springs.** Sum one step response per target change. Snap settled springs to their
  target.
- **Outgoing text leaves before incoming text occupies its space** (`text_overlap_violations`).
  Masked reveals should start fully hidden (≥120% translate). Text that is 15% or more visible
  counts as visible.
- **Wipes and floods take at least ~0.3 s.** Never switch a label's colour before its backing has
  actually changed. Fade labels across the wipe instead.
- **Package everything locally.** Fonts, images and libraries are declared assets or composition
  files. Any non-local request (for example a Google Fonts `@import`) blocks the render. Media inside
  the composition folder must be declared assets with source and licence.
- **Text drawn into Canvas/WebGL is pixels, not telemetry.** Report it in `window.__vch.elements`
  if a requirement depends on it.
- **Mark semantic text blocks with `data-vch-id`.** This gives stable IDs for hold checks, and
  `text-group` observations, so a line split into word spans still matches copy checks.
- **Footage:** pre-extract image sequences, or encode all-intra, and swap frames inside `seek(t)`.
  `<video>` seeking is not managed for you.

**Preview** without the harness: serve the repository root (`python -m http.server`) and open the
composition. The example loops on the wall clock when `__vch.harness` is absent.

**Capture details:**

- Chromium runs headless with its sandbox on. Set `VCH_CHROMIUM_NO_SANDBOX=1` only in containers
  that require it.
- WebGL uses software SwiftShader.
- Partial re-raster is disabled because it made clip-edge pixels depend on the previous frame.
- 2D canvas is rasterised on the CPU. On the GPU, a page's first draw of a path could differ from
  later draws of the same path (3 pixels, ±7 levels), which makes frames depend on seek history.
- Frames are captured as lossless PNG with Chromium's fast compression setting: identical pixels,
  about 2.5x faster than Playwright's screenshot call.
- `render.samples` (1..16) blends sub-frames in linear light for motion blur.

## Dense explainers

`examples/how-code-becomes-video.json` (48 s, 1080p) was built to match the information density
of a reference explainer. Measure the reference and your candidate with the same proxies before
judging by eye:

```sh
python -m vch profile reference.mp4 --out runs/ref-profile
python -m vch profile runs/<name>-NNN/video.mp4 --out runs/<name>-NNN-profile
python -m vch profile-compare runs/ref-profile/profile.json runs/<name>-NNN-profile/profile.json
```

Edge density and grid coverage are detail proxies, not information. What added information in that
film:

- **One world, one camera, no hard cuts.** Stations sit along a line, and a card travels between
  them. Panels float above the line and move with it, so every transition comes from the previous
  state.
- **A persistent HUD.** A live `t`/frame readout and a station rail say where the viewer is.
- **Each station has a kicker, a headline, a one-line description and a mechanism.** The mechanism
  shows the process working with real data. Examples: this film's own requirements sorted into
  bins, its own `seek(t)` source and a seek preview, its own cue sheet with a playhead, and
  measured corpus files as dots.
- **Numbers are bound to their sources at load time.** The film reads `/contract.json`, its own
  source and a data file, so a count on screen cannot drift from the thing it counts.
- **Self-render miniatures** (`drawWorld(ctx, t)` into a small canvas) show the film's own frames
  in previews, filmstrips and a closing contact sheet. They are pure, so caching them is safe.

Timing rules learned from its failed checks:

- **Give every label at least ~1 s fully visible before the camera leaves.** A label that is still
  fading in when its panel fades out never settles. The contrast check then measures it
  half-transparent.
- **Flying artwork must not pass behind text.** Its colour becomes the text's backing.
- **Entrances that start at a safe-area margin must not overshoot.** Use ease-out there, not an
  underdamped spring.
- **Composite a panel as a unit** (draw it into its own canvas, then place it once with the panel's
  alpha). Otherwise an inner `globalAlpha = 1` pops its contents ahead of the fade.
- **A closing hold still needs motion.** The finale's slow drift failed `max_static_hold_s`. A
  moving highlight over the contact sheet fixed it, without excluding the window.

**Finishing without fake motion.** Flat vector art reads as lit when bright parts bleed light.
That film thresholds its canvas by contrast, blurs it at quarter size and adds it back. Panels get
a glass gradient, a rim highlight and a soft shadow on the main canvas, and lit gates cast pools
of light. The grain texture is fixed. Animated grain changes every pixel on every frame, which the
dead-time proxy would read as motion. Generative enhancement of stills (for example Magnific) is a
paid, generative step outside this harness. If you use one, declare it, keep its inputs and
outputs, and leave a human review of what it changed.

## Audio cues and bed

- **Hit kinds:** `tick`, `impact`, `chime` and `whoosh`. A whoosh is a 0.42 s tonal riser that
  lands on an impact, so placing it by its peak puts the swell before the cue. It is tonal because
  broadband noise raises spectral flux on every hop and hid the landing from onset detection.
- **`audio.pad`** (0..2, relative to cue level) adds an original sustained chord bed. The bed dips
  by 70% from 50 ms before each cue, so each cue's own peak stays the loudest sample, which is what
  `audio_hit_sync_ms` measures. It recovers over 0.5 s so the bed's return does not read as a new
  transient.
- With `pad: 1.4` and a −2 dBFS ceiling, a 74-cue mix reaches about −16 LUFS without a limiter.

## Preview loop before the full render

```sh
python -m vch storyboard examples/html.json                 # timestamped plan from the contract
python -m vch stills examples/html.json --beats --out runs/stills-001 --trust-scene-code
python -m vch stills examples/html.json --times 0,2.5,6.2 --out runs/stills-002 --trust-scene-code
python -m vch stills examples/html.json --times 3.1,7.4 --motion --out runs/stills-003 --trust-scene-code
```

`--motion` also renders each still's next frame and reports their change at the size
`max_static_hold_s` analyses. Values under 0.5/255 count as still. Check a long hold this way
before paying for a full render.

Look at `sheet.jpg`. `stills.json` lists the text, overlaps and smallest size for each still.
These are raw frames from before encoding. Only `vch run` produces decoded evidence.

## Brief sections → contract evidence

Effective corpus briefs share a shape. Map each section to something checkable, or keep it human:

| Brief section | Contract / evidence |
|---|---|
| Format, safe zone ("keep text clear of the TikTok UI") | `video`; `safe_area_violations` margins |
| Timestamped storyboard or beat-grid state list | scene windows, `timing.bpm`, `timing.hits`; `vch storyboard` |
| "A new idea every 1.5–2 s", "no dead time" | `max_static_hold_s` (exclude deliberate holds explicitly) |
| "Labels never overlap during a morph" | `text_overlap_violations` |
| Readable copy at pace | `minimum_text_size_px`, `minimum_text_hold_s`, `minimum_contrast`; human review at normal speed |
| "A sound on every hit", SFX on events | `timing.hits` (+ `audio.mode: "mix"` with `align: "peak"`); `audio_hit_sync_ms` |
| "−14 LUFS, −1 dBTP after encode" | `integrated_loudness_lufs`, `true_peak_dbtp` |
| "Last frame = first frame" | `loop_seam_ratio` |
| "No single-frame pops" | `single_frame_pops` |
| Real product only, no invented numbers | `text_present` / `text_absent` plus a human truth review |
| Transitions that "come from" the previous scene, taste, brand fit | human rubric with timestamps; no proxy stands in |
| "Show me the storyboard / beat map before code" | `vch storyboard` / `vch stills`; record approval as a human requirement |

## Review ladder

1. Validate contract, rights and module paths.
2. Inspect a few stills before paying for full render time.
3. Render actual MP4 and all-frame text trace.
4. Run objective checks and proxies; inspect failures and decoded frames.
5. Watch full motion and listen to sound; static contact sheets cannot replace this.
6. Record review decisions against the manifest binding, citing timestamps.
7. Re-render to a new directory after a change. Compare only matching contracts.

If the agent cannot listen/watch in its current environment, it must say so and
leave those review criteria pending. “The encoder exited 0” is not perceptual QA.

## Cloud / security

No local desktop or signed-in browser is required for this implementation. It runs
as a finite CPU job. Persist outputs after the job. The Docker recipe is provided
for portability; a successful direct Python run does not prove the Docker image
was built or tested.

Do not put secrets in the project. Run untrusted generated code in a separate
disposable VM/container. A project-path check cannot contain arbitrary Python
imports or side effects. CPU/memory/time budgets should be enforced by the job
runner. No external LLM generation loop is automatically invoked by the CLI.

## Single-prompt production

See SINGLE_PROMPT.md for the author command/replay protocol. The production loop
freezes requirements, records the initial prompt and every response, rejects
unauthorized writes, renders immutable attempts, and requests an artifact-bound
agent inspection before finishing a live-author run. This inspection is a
self-attestation and cannot satisfy a human-review gate. The browser backend uses
declarative scene descriptions; its supported visual mechanisms are a vocabulary,
not evidence that a new subject has been understood.
