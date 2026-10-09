# Authoring protocol

Nothing in this repository is a template. The example films show that the loop works; their look,
structure, motion and sound belong to them. Invent each film's own for its brief. This document
fixes only what makes a film correct and measurable: how a composition must behave so that its
frames and sounds can be checked.

## Input packet

Use `python -m vch packet <contract>` with any coding agent. Include the following brief fields (do
not let missing facts be invented):

- Goal, audience, distribution placement and call to action.
- Verified facts and prohibited/unconfirmed claims, with source URLs/dates.
- Target dimensions, duration, fps and platform-specific safe region.
- Tone and visual direction **for this project**, not a reference video's or an example's.
- Available real assets with rights, brand mark and fonts.
- Sound: silence, sound synthesized by the composition, or licensed music/voice/effects with rights.
- Hard acceptance checks, candidate proxies, human rubrics and reviewer.
- Resource/cost ceiling and maximum repair attempts.

## Authoring prompt

“Read AGENTS.md and this contract. Propose a short timing plan that maps every requirement ID to
visual/audio evidence. Implement only the composition/assets scope. Keep the requirements and
evaluator unchanged. Do not copy a reference's or an example's style or sound. Render representative
stills and preview the sound, inspect them, then run and evaluate the actual MP4. For each failure,
explain and patch the concrete cause, up to three iterations. Return artifact paths, real commands,
remaining failures and unmeasured items. Leave designated human reviews pending. Do not claim a
provider/model choice unless your runtime exposes it.”

## Compositions (`backend: "html"`)

A composition is a web page (HTML, CSS, SVG, Canvas or WebGL, with any library you vendor) that
draws any moment from `t`. See [OPUS_VIDEO_RESEARCH.md](OPUS_VIDEO_RESEARCH.md) for how public
code-rendered films are made this way. Declare:

```json
"backend": "html", "html": {"entry": "compositions/<name>/index.html"}
```

Scenes declare contiguous, frame-aligned windows. They drive sampling, beat-grid and storyboard
checks; they do not limit what the page draws.

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

**Sound protocol.** With `"audio": {"mode": "composition"}`, define
`window.__vch.audio = ({ sampleRate, duration, channels }) => [left, right]`. Return one or two
`Float32Array`s of exactly `round(sampleRate × duration)` samples. It is called once, after
`ready` and before any frame. Its output must depend only on the contract and a seed. The harness
then does four things:

- applies one linear gain toward `loudness_target` that never exceeds `peak_ceiling_dbfs`;
- rejects clipping;
- writes the WAV and fingerprints the samples into the evidence;
- measures the encoded AAC audio.

`timing.hits` is the cue sheet: times and names, plus an optional `kind` that is only the author's
own label. What sounds at a cue is the composition's decision. `compositions/_lib/sound.js` holds mechanics only: buffers, placing a sound by its peak,
panning, a one-pole low-pass, ducking and adding a bed. It has no instruments. The alternatives
are `mix`, which places declared, licensed files by start or measured peak, and `file`, a single
licensed track.

## Correctness rules

These come from failures that the checks caught. They constrain behaviour, not style.

- **No state carried between frames.** That includes timers, accumulators and DOM caches keyed on
  the previous frame. The forward/reverse/shuffled seek check compares pixels *and* telemetry.
- **Motion is closed-form in `t`.** For example, a spring is a sum of step responses, snapped to its
  target once settled. Never integrate from whichever frame was drawn before.
- **Set per-frame state before using it.** A clip once set `camera.up` *after* `lookAt`, so each
  frame used the previous frame's up vector.
- **Render inside `seek(t)`.** Never call `setAnimationLoop`. Build seeded geometry, textures and
  particles once in `ready`.
- **Elements whose opacity changes get their own compositor layer** (`will-change: opacity`;
  `show()` in `compositions/_lib/clip.js` does this). Otherwise Chromium may merge a just-shown
  element into a neighbour's layer, or keep it separate, depending on the previous frame. The same
  `t` then renders with 1-level differences depending on seek order. This was measured over a
  semi-transparent overlay.
- **Shader errors fail the run.** WebGL reports compile failures only to the console, so a broken
  material renders black without a page error. The backend treats `console.error` like a page error.
- **Package everything locally.** Fonts, images and libraries are declared assets or composition
  files. Any non-local request (for example a Google Fonts `@import`) blocks the render. Media inside
  the composition folder must be declared with source and licence. A folder asset is a path ending
  in `/`. `compositions/_vendor/three/` is declared that way, and an import map points at it.
- **Text drawn into Canvas/WebGL is pixels, not telemetry.** Report it in `window.__vch.elements`
  if a requirement depends on it.
- **Mark semantic text blocks with `data-vch-id`.** This gives stable IDs for hold checks, and
  `text-group` observations, so a line split into word spans still matches copy checks.
- **Bind on-screen numbers to their sources at load time** (`/contract.json`, the page's own source,
  a data file), so a count cannot drift from the thing it counts.
- **Footage:** pre-extract image sequences, or encode all-intra, and swap frames inside `seek(t)`.
  `<video>` seeking is not managed for you.
- **Post-processing tone-maps the whole frame.** With three.js `EffectComposer` and `OutputPass`, a
  material's `toneMapped: false` does not exempt it. Author colours that must stay true in linear
  light.

## What the checks see

Knowing how a proxy measures avoids designing toward it by accident:

- **Overlap.** Text that is 15% or more visible counts as visible. Outgoing and incoming text in
  the same space at the same time count as overlapping.
- **Contrast** is measured on settled observations: at least 95% of the element's own peak opacity.
  It compares the text with the median non-text pixel inside its box.
  - A label that is still fading in when its container leaves never settles.
  - Artwork that passes behind text becomes its backing.
  - A label whose colour switches before its backing changes is measured against the old backing.
- **Safe area** counts every frame, so an entrance that overshoots a margin counts.
- **Dead time:** a decoded frame whose mean luma change is below 0.5/255 counts as still. Slow
  drifts over smooth, softly lit scenes measured 0.1–0.3/255. Animated grain changes every pixel and
  would fake motion; do not use it to pass. What changes on screen is the film's decision.
- **Pops:** a one-frame flash or flood counts. Deliberate flashes need an `exclude` window frozen in
  the contract.

## Sound the cue check can hear

`audio_hit_sync_ms` works in three steps:

1. It mixes the encoded audio to mono at 24 kHz and computes log-spectral flux (1024-sample FFT,
   128-sample hop).
2. It keeps flux peaks that exceed their ±0.25 s median by 0.07 of the film's maximum flux. Each
   peak is reported at the loudest sample from 10 ms before its flux frame to 60 ms after the
   frame's centre. Peaks less than 50 ms apart merge, keeping the stronger.
3. Each cue's error is its distance to the nearest reported peak.

These constraints, learned building the current films, follow from that method. They say nothing
about what a film should sound like:

- **The loudest sample near a cue must be the cue's own attack.** A body that swells, overlapping
  partials that sum later, or a bed's low-frequency swing within 60 ms moves the measured time.
  Place each sound by its peak (`align: "peak"`, or `place()` in `sound.js`), not by its first
  sample.
- **Pure tones carry little flux.** A tonal onset can go undetected next to noisy ones. A few ms of
  broadband contact at the attack makes it detectable.
- **Content above 12 kHz is gone** in the 24 kHz analysis. An attack made only of it is invisible.
- **Steps and swells mask cues.**
  - A bed that steps in at t = 0 sets the film's maximum flux and hides later cues; fade it in.
  - A noise swell that crescendos into its cue leaves no flux rise at the cue; end it shortly before.
- **Beds compete with cues.** Duck a bed under cue times, or keep its peaks below the attacks. Low
  notes cost peak level but add little K-weighted loudness, so a bass-heavy bed pulls the loudness
  target and the peak ceiling against each other. There is no limiter.

`vch sound` measures all of this on the WAV in seconds, before a full render.

## Preview loop before the full render

```sh
python -m vch storyboard <contract>                       # timestamped plan from the contract
python -m vch stills <contract> --beats --out runs/<name>-stills-001 --trust-scene-code
python -m vch stills <contract> --times 0,2.5,6.2 --motion --out runs/<name>-stills-002 --trust-scene-code
python -m vch sound <contract> --out runs/<name>-sound-001 --trust-scene-code
```

- `--motion` also renders each still's next frame and reports their change at the size
  `max_static_hold_s` analyses. Values under 0.5/255 count as still.
- Look at `sheet.jpg`. `stills.json` lists the text, overlaps and smallest size for each still.
- `sound.json` gives loudness, true peak, the error for every cue, and cues missed by more than
  20 ms.

These are measurements from before encoding. Only `vch run` produces decoded evidence. Do not edit
project files while `vch run` renders: the source check invalidates the run.

## Comparing with a reference

When a brief points at a reference ("as rich as this"), measure both with the same proxies before
judging by eye:

```sh
python -m vch profile reference.mp4 --out runs/ref-profile
python -m vch profile runs/<name>-NNN/video.mp4 --out runs/<name>-NNN-profile
python -m vch profile-compare runs/ref-profile/profile.json runs/<name>-NNN-profile/profile.json
```

Edge density and grid coverage are detail proxies, not information, and a profile is not a licence
to copy the reference's style.

## three.js

- With SwiftShader, an 8-second 720p clip renders and is fully checked in 50–140 s. That includes
  4× MSAA, bloom, depth of field and soft shadows.
- The vendored copy is unmodified three r186. Authors cannot write `_`-prefixed folders.

## Style packs

Style can be an input instead of something baked into a composition. A contract may carry
`style`: an object, or a project-relative path to a JSON pack in `styles/`. The pack is inlined when
the contract loads, so the run's `contract.json` records the exact tokens it used. Override it per
run without editing the contract:

```sh
python -m vch run <contract> --style styles/<pack>.json --out runs/<name>-<pack>-001 --trust-scene-code
python -m vch diversity runs/<name>-001 runs/<name>-<pack>-001
```

- The harness validates `mode` (`dark` or `light`) and `#RRGGBB` values. Everything else is between a
  composition and its packs.
- `compositions/how-code-becomes-video` reads colour roles, families and finish from
  `contract.style`.
- A pack changes the surface, not the structure. Layout, camera, motion and sound are authored per
  composition.
- Every pack must pass the same checks. A colour that passes as a fill may fail as text, and a wider
  font can push a label past the safe area.

## Brief sections → contract evidence

Effective corpus briefs share a shape. Map each section to something checkable, or keep it human:

| Brief section | Contract / evidence |
|---|---|
| Format, safe zone ("keep text clear of the TikTok UI") | `video`; `safe_area_violations` margins |
| Timestamped storyboard or beat-grid state list | scene windows, `timing.bpm`, `timing.hits`; `vch storyboard` |
| "A new idea every 1.5–2 s", "no dead time" | `max_static_hold_s` (exclude deliberate holds explicitly) |
| "Labels never overlap during a morph" | `text_overlap_violations` |
| Readable copy at pace | `minimum_text_size_px`, `minimum_text_hold_s`, `minimum_contrast`; human review at normal speed |
| "A sound on every hit", SFX on events | `timing.hits` plus composition sound or `mix` layers placed by peak; `audio_hit_sync_ms` |
| "−14 LUFS, −1 dBTP after encode" | `integrated_loudness_lufs`, `true_peak_dbtp` |
| "Last frame = first frame" | `loop_seam_ratio` |
| "No single-frame pops" | `single_frame_pops` |
| Real product only, no invented numbers | `text_present` / `text_absent` plus a human truth review |
| Transitions that "come from" the previous scene, taste, brand fit, how it sounds | human rubric with timestamps; no proxy stands in |
| "Show me the storyboard / beat map before code" | `vch storyboard` / `vch stills`; record approval as a human requirement |

## Review ladder

1. Validate the contract, rights and the composition entry.
2. Inspect a few stills and preview the sound before paying for full render time.
3. Render the actual MP4 and the all-frame text trace.
4. Run objective checks and proxies; inspect failures and decoded frames.
5. Watch full motion and listen to sound; static contact sheets cannot replace this.
6. Record review decisions against the manifest binding, citing timestamps.
7. Re-render to a new directory after a change. Compare only matching contracts.

If the agent cannot listen/watch in its current environment, it must say so and
leave those review criteria pending. “The encoder exited 0” is not perceptual QA.

## Cloud / security

No local desktop or signed-in browser is required. A render is a finite CPU job: headless Chromium
with its sandbox on (`VCH_CHROMIUM_NO_SANDBOX=1` only where a container requires it), loopback-only
networking, then FFmpeg. Persist outputs after the job. The Docker recipe is provided for
portability; a successful direct Python run does not prove the Docker image was built or tested.

Do not put secrets in the project. `--trust-scene-code` is an acknowledgement, not a sandbox: run
untrusted generated compositions in a separate disposable VM/container. CPU/memory/time budgets
should be enforced by the job runner. The CLI calls no model and no generation API.
