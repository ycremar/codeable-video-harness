---
name: codeable-video
description: Make, render or repair a code-rendered video in this repository (launch film, explainer, motion graphic, loop) with evidence. Use for any request to create, animate, render, retime or fix a video here; walks brief → contract → storyboard → stills → sound → render → evaluate → repair.
---

# Codeable video production loop

Rules live in `AGENTS.md`; follow them exactly. Details: `docs/AUTHORING.md` (seek and sound
protocols, correctness rules, what the checks see, brief → evidence table), `docs/MEASUREMENT.md`
(what each metric can and cannot show), `docs/OPUS_VIDEO_RESEARCH.md` (how public code-rendered
videos are made).

Nothing in this repository is a template. The example films are evidence that the loop works.
Do not reuse their look, structure, motion or sound: invent each film's own for its brief.

1. **Brief → contract.** Write `examples/<name>.json` for the brief. An example contract shows the
   format and the requirement list, not a design. Turn each brief section into a hard check, a named
   proxy or a human rubric (table in AUTHORING.md). Freeze thresholds before rendering. Ask the user
   only for missing facts, rights and assets; never invent product claims or numbers.
2. **Plan.** `python -m vch storyboard <contract>`. Put scene cuts on `timing.bpm`, and add a named
   `timing.hits` cue for every moment that needs a sound. For a licensed song:
   `python -m vch profile song.wav --out runs/song-profile`, then read tempo, phase and onsets from
   `profile.json`.
3. **Style is an input.** Put tokens in `styles/<pack>.json` (roles, not hues) and reference them as
   `contract.style`, or pass `--style` to `vch run` / `vch stills`. For variants, render each pack and
   check `vch diversity` (corpus median pair distance 1.34). Every pack must pass the same checks.
4. **Build** `compositions/<name>/index.html`:
   - `window.__vch.seek(t)` sets every property from `t`; nothing carries over between frames.
   - Motion is closed-form in `t`.
   - Fonts, libraries and media stay local and are declared with rights.
   - Elements whose opacity changes get their own layer (`will-change: opacity`).
   - Mark semantic lines with `data-vch-id`.
   - Vendored three.js and the pure-time helpers in `compositions/_lib/clip.js` are available. They
     are tools, not a starting design.
5. **Sound.** With `audio.mode: "composition"`, `window.__vch.audio({ sampleRate, duration })`
   returns the film's own synthesized samples. `compositions/_lib/sound.js` has mechanics only.
   Design the sounds for this film; there is no preset palette. Each cue's attack must be its
   loudest nearby sample and carry broadband energy under 12 kHz; AUTHORING.md explains why.
   - Preview: `python -m vch sound <contract> --out runs/<name>-sound-NNN --trust-scene-code`.
     `sound.json` lists every cue's error and the misses over 20 ms.
   - Listen to `audio.wav` if you can; otherwise say you could not.
6. **Preview pictures cheaply.**
   `python -m vch stills <contract> --beats --out runs/<name>-stills-NNN --trust-scene-code`.
   - Open `sheet.jpg` and actually look. Fix the warnings in `stills.json` before rendering.
   - Add `--motion` to check that holds keep moving (next-frame change ≥ 0.5).
   - If the brief points at a reference ("as rich as this"), profile both:
     `vch profile <file> --out <dir>`, then `vch profile-compare a/profile.json b/profile.json`.
   - Don't edit project files while `vch run` renders. The source check invalidates the run.
7. **Render + measure.** `python -m vch run <contract> --out runs/<name>-NNN --trust-scene-code`.
   - Read `report.md`.
   - Inspect `contact-sheet.jpg` and `frames/` (decoded from the MP4).
   - Watch and listen if you can; otherwise say you could not.
   - Exit 3 means machine checks passed and human review is pending.
8. **Repair** named failures only, up to 3 attempts, each into a new run folder. Never edit
   thresholds, `vch/evaluate.py` or tests to make a candidate pass.

| Failure | Usual cause → fix |
|---|---|
| SEEK mismatches | State carried between frames (cached DOM, counters, timers) → derive from `t` |
| SEEK: 1-level differences on text only | A fading element's layering depends on the previous frame → `will-change: opacity` on it |
| 3D clip fails SEEK | Per-frame state set after it is used (e.g. `camera.up` after `lookAt`), or an animation loop instead of `seek(t)` |
| OVERLAP | Outgoing and incoming text share space at the same time → separate them in time or space |
| CONTRAST on a label that looked fine | It never settled (still fading when its container left), artwork passed behind it, or its colour switched before its backing did |
| SAFE during an entrance | Motion overshot the margin |
| POPS | A one-frame flood or flash → spread it over several frames, or `exclude` a deliberate flash |
| DEAD-TIME | Mean change under 0.5/255 per frame → make something the brief cares about change; never animated grain |
| HITS: a cue missed or late | Something louder within 60 ms after the attack (a swelling body, a bed's swing) → duck or lower it, or make the attack the peak; place by `peak` |
| HITS: a tonal cue not detected | Pure tones carry little flux → a few ms of broadband contact at the attack |
| HITS: a cue lost under a rise or bed | The swell or a t = 0 step masks the flux → fade beds in; end rises shortly before the cue |
| Loudness | The ceiling limits the one linear gain → raise the bed relative to the attacks (mid-range counts more than bass); loudness requirements change only with the user's approval |
| "non-local resources" | CDN font or library → vendor it under `compositions/_vendor/<lib>/` and declare the folder (path ending `/`) with its licence |
| `console.error` blocks the run | Usually a WebGL shader compile error; the frame would have rendered black |
| A pack fails CONTRAST/SAFE the default passed | Fill colour reused as text, or a wider font → darker text role, wrap widths |

9. **Report** the commands actually run, artifact paths, the failing and unmeasured requirement
   IDs, and that human reviews stay pending until the named reviewer decides. Never approve a human
   criterion yourself.
