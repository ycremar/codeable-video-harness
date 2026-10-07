# How the "Opus 5.5" code-rendered videos are made — corpus study

Study date: 2026-10-06. Sources: the [skillry Opus 5.5 collection](https://skillry.dev/ai-videos/opus-5-5/)
and the requested entry [@mattworkman](https://skillry.dev/ai-videos/opus-5-5/mattworkman-309357).
This complements [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md), which covers the original
screen recording that motivated the harness.

## Scope, method and evidence labels

- **Listing:** 475 entries, read from the collection page's embedded data: creator post or prompt
  text, category, skillry's technique tags, dimensions, duration and media links. For the 74 entries
  whose text was truncated, the full text came from the detail pages.
- **Requested video:** original and skillry's remake, decoded frame by frame, plus `vch profile`.
- **Measured sample:** 38 originals, stratified by the toolchain each post names: 8 HyperFrames,
  7 Remotion, 7 that mention a single HTML file / `seek(t)` / Playwright, and 16 that name no
  framework. Every number in the tables below comes from `vch profile` (this repository) run on
  those files. The [appendix](#appendix-measured-sample) lists them.
- **Framework documentation:** the [HyperFrames README](https://github.com/heygen-com/hyperframes)
  and its `hyperframes-core` skill (Apache-2.0, read 2026-10-06).

Each claim below carries one of three labels:

- **Observed:** we decoded, measured or looked at it ourselves.
- **Stated:** a creator's post or prompt says so. We did not verify it.
- **Inferred:** our interpretation of what we observed.

Limits:

- We have no creator code, session logs or exact model settings.
- The files are X re-encodes (at most 1280 px, AAC audio). Resolution, frame rate and loudness
  describe the platform copy, not the master.
- "Zero-shot", time and cost figures are self-reported.
- skillry's tags are skillry's labels.
- Keyword counts are lower bounds: only 137 entries include a prompt longer than 300 characters.
- No media, frames or full prompts are redistributed here. Short quotes are attributed.

## The requested video: @mattworkman, "HyperFrames staging, edit"

Post text (**Stated**): "messing around with Opus 5.5 – HyperFrames staging, edit – JavaScript,
ThreeJS – fal GPT Image 2.5 and Seedance 2.5 … very blah text design, I need a fal design
skill/guideline ideally."

| Property (**Observed**) | Value |
|---|---|
| File | 30.06 s, 1280×720, 30 fps H.264, AAC 48 kHz stereo (X copy) |
| Cuts and pacing | 0 hard cuts; 9 visual events (about 3 per 10 s); longest still hold 1.1 s |
| Sound | 40 measured transients, no stable beat (weak tempo estimate); −15.9 LUFS; true peak 0.0 dBTP, so it clips after X's encode |
| skillry remake | 30.2 s, **no audio track**, full-range `yuvj420p` (typical of screenshot capture); same storyboard, layout and timing as the original |

| Time (s) | On screen (**Observed**) |
|---|---|
| 0–1.2 | Photoreal hero image (a corgi surfing at sunset) with the kicker "TEXT-TO-VIDEO, EXPLAINED" and the line "This started as 5 words." |
| 1.2–4 | Dark 3D stage with a perspective floor grid. "5 words in. A video out." A prompt chip, and pipeline "stations" laid out in depth as the camera dollies past |
| 4–5.5 | Establishing shot: "Here's everything in between." All stations in one row |
| 6–8 | "How text becomes video": the prompt types into a field |
| 8–12.5 | "STEP 01 Prompt expansion": an LLM orb (wireframe sphere with glow), an expanded prompt typing into a card, and a counter "5 → 10 … words" |
| 13–15.5 | "STEP 02 Text encoding": tokens flow into encoder planes; "14 tokens → 14 vectors" |
| 16–22.5 | "STEP 03 Denoising": a cloud of coloured cubes assembles into the hero image; "STEP 24/30" and a noise bar |
| 23–25.5 | "STEP 04 Decoding": a strip of frames; "16×9 → 1280×720" |
| 26–30 | "Text → video." The generated clip on a card, with a credit line naming GPT Image 2.5 → Seedance 2.5 on fal |
| Throughout | A five-station progress rail (PROMPT / EXPAND / ENCODE / DENOISE / DECODE) fills in orange; uppercase mono labels; grotesk headlines |

How it was most likely built (**Inferred**, from the evidence above):

1. **Generated hero asset.** The still and clip come from image and video models through fal.
   The end card credits them.
2. **Code for everything explanatory.** One Three.js world holds every station, and camera moves
   between them replace cuts ("staging"). HTML text sits on top. Counters are bound to the
   story's numbers.
3. **The generated image reused as data.** The "denoising" cubes take their colours from the hero
   image's pixels as they converge, so the explanation stays visually tied to the output.
4. **Sound-effect-led audio.** Whooshes and ticks sit on transitions rather than on a music grid.
   The master was not peak-safe after X's encode.
5. **The creator's own bottleneck is design guidance.** They name typography and a design guideline
   as the gap, not rendering. This matches a corpus-wide pattern: the effort goes into the brief and
   the skill, not the renderer.

## Corpus findings

### Formats (**Observed** in listing data)

| | Count |
|---|---|
| Entries | 475 (skillry categories: motion 288, interactive 70, explainer 62, 3D 55) |
| Duration | median 30 s; 155 entries at 10–20 s, 144 at 20–35 s, 117 at 35–60 s, 51 longer |
| Aspect | 378 landscape, 74 portrait, 23 square |
| skillry technique tags | canvas 336, svg 193, three.js 141, shader 100, gsap 81, css 61, audio 36, particles 26 |

### What creators say they used (**Stated**; keyword matches in post or prompt text)

| Mentioned | Entries |
|---|---|
| The viral prompt "…like it's your showreel for a résumé. go all out" | **79** (17%) |
| Remotion (React) | 62 |
| HyperFrames (HTML + GSAP; agent skills) | 31 |
| A single HTML file, `seek(t)` or Playwright capture | 30 |
| Three.js | 27 |
| "Skill(s)" | 27 |
| The real product, repo or site as source of truth | 26 |
| A beat grid or BPM | 25 |
| TTS or voice-over / ElevenLabs | 21 / 9 |
| Rendering stills or a contact sheet before the full render | 20 |
| Sub-frames or motion blur | 17 |
| Seamless loops ("last frame = first frame", "loopable") | 16 |
| Sound effects placed by their *measured* peak | 12 |
| The structured `<inputs>/<direction>/<structure>/<build>/<gotchas>/<start>` template | 12 |
| Image or video generation (fal, Seedance, Kling, …) | 11 |
| numpy audio analysis | 11 |

The structured template is the clearest view into the engineering, and is quoted here for that
reason (**Stated**, e.g.
[@twoclipping](https://skillry.dev/ai-videos/opus-5-5/twoclipping-402193)):

- "Every style is computed from time inside seek(t): no CSS transitions, no timers, no state
  carried between frames."
- "Springs are closed-form step responses. A value that changes target many times is the sum of
  one spring per change."
- "Analyze the song with numpy for the beat grid … Place every UI sound by its measured peak."
- "Render with Playwright: 4 subframes per frame, blended with ffmpeg tmix."
- "Render one frame per beat before the full render."
- In variants: "scan for single-frame pops (frame-difference spikes 3x their neighbours)", and
  "Loudnorm to -14 LUFS".
- "Gotchas" record failures the agent hit, for example text overlapping during a morph, or a loop
  that stutters because the last frame does not match the first.
- "Start" gates the work: "show me the state list on the beat grid before you write any code."

Longer free-form briefs follow the same shape:

- A role and quality bar.
- Repo, design-token and screenshot sources of truth.
- A format and safe zone.
- A story arc and a timestamped storyboard.
- Transition rules ("of course the next scene came from that"; no crossfades).
- Easing curves and a sound language.
- A ban list.
- A mandatory loop: render chosen timestamps, *inspect them*, render the full film, inspect
  decoded frames, iterate.
- A deliverables list (storyboard, source, MP4, poster, contact sheet, reproduce commands).

Multi-agent variants are **Stated** too:

- A planner at high effort finds the moments, a builder at medium effort makes each animation, and
  a judge reviews once. Only "egregiously bad" items get rebuilt.
- Two reviewers rank issues P0/P1/P2, and a third agent fixes them each round.

### Measured pacing and sound (**Observed**, `vch profile`, 38 files)

| Median per file | All | HTML/seek | HyperFrames | Remotion | Unspecified |
|---|---|---|---|---|---|
| Duration (s) | 30.0 | 23.1 | 35.3 | 34.0 | 26.8 |
| Hard cuts per 10 s | 1.6 | 2.5 | 0.7 | 2.6 | 1.6 |
| Files with zero hard cuts | 8/38 | 1/7 | 3/8 | 0/7 | 4/16 |
| Median shot (s) | 2.8 | 2.9 | 10.1 | 2.8 | 2.1 |
| Visual events per 10 s | 4.6 | 9.1 | 3.6 | 5.3 | 3.9 |
| Median gap between visual events (s) | 1.8 | 0.9 | 2.3 | 2.0 | 2.4 |
| Longest still hold (s) | 1.9 | 1.2 | 3.0 | 2.6 | 1.2 |
| Seamless loop seam (≤1.5) | 8/38 | 4/7 | 2/8 | 1/7 | 1/16 |
| Integrated loudness (LUFS, audible tracks) | −14.2 | −14.1 | −16.2 | −14.3 | −14.0 |
| True peak > −1 / > 0 dBTP | 14 / 4 of 28 | 3 / 0 | 1 / 0 | 5 / 2 | 5 / 2 |
| Visual-event sync to sound (±100 ms): observed vs chance | 0.72 vs 0.69 | 0.90 vs 0.86 | 0.61 vs 0.60 | 0.72 vs 0.68 | 0.56 vs 0.61 |

What the measurements show:

- **Pacing matches the briefs.** The median gap between visual events is 1.8 s, in line with the
  briefs' "a new idea every 1.5–2 s". HTML-seek entries change about every 0.9 s ("something
  happens on every beat" at 120 BPM). HyperFrames entries more often run as long continuous takes.
  The requested video has no hard cuts.
- **Loudness clusters at the social-platform norm** (median −14.2 LUFS). Half the audible tracks
  have a true peak above −1 dBTP after X's AAC encode, and 4 exceed 0 dBTP. Masters therefore need
  measuring *after* encoding, as one brief says: "re-measured after AAC encode".
- **Audio/visual sync is not verifiable from the published files.** Blind detection finds visual
  events near sound onsets at chance rate. Claims that "every hit lands" cannot be confirmed this
  way. Dense sound design, eased motion that peaks after its sound, and platform re-encodes all
  blur the measurement. Sync needs *declared* hits, measured on the encode the harness itself made.
- **Single-frame events are rare.** 3 of 38 files have them. At a lower threshold, a manual check
  of flagged frames found deliberate flash frames, glitch frames, one apparent positional jitter,
  and false alarms from ticking counters. That is why the harness default threshold is conservative
  and intentional flashes must be excluded explicitly.
- **Tempo estimates have octave ambiguity.** Seven HTML-seek tracks estimate at 118.6, 96.4,
  120.5, 59.4, 60.7, 120.3 and 59.9 BPM. The ~60 BPM values are likely half of a 120 BPM grid.

## The production stack, reverse-engineered

| Layer | What creators do | Evidence |
|---|---|---|
| Brief | A spec-like prompt: role, sources of truth, format, arc, timestamped storyboard or beat-grid state list, motion and sound rules, bans, a verification loop, deliverables, and a "show me X before code" gate | Stated (prompts) |
| Knowledge pack | Agent skills: HyperFrames' router plus 21 skills, Remotion skills, or custom ones (design guidelines, scoring) | Stated; HyperFrames docs |
| Grounding | The agent reads the repo, CSS tokens and logo (traced to SVG), records simulator screens, and queries real data | Stated |
| Assets | Optional generated stills and clips (fal, Seedance, Kling); TTS from ElevenLabs, Gemini, OpenAI or a local model; music from Suno, Lyria or ElevenLabs; licensed SFX (Mixkit); or everything synthesized in code | Stated; observed in the requested video's credit |
| Composition | HTML/CSS/SVG/Canvas/WebGL, often GSAP or Three.js, or React (Remotion). A pure `seek(t)` or a paused timeline; closed-form springs; seeded randomness; footage as image sequences | Stated; HyperFrames determinism rules |
| Timing | numpy beat grid from the song; cue lists; sounds aligned by measured transient peak; captions measured in the real font and fitted to safe zones | Stated |
| Capture | Headless Chrome (Playwright or Puppeteer) screenshot per sub-frame; sub-frames blended; FFmpeg H.264 yuv420p; loudness normalisation | Stated; remake pixel format observed |
| Verification | Stills at fixed timestamps or one per beat, tiled into a contact sheet; decoded-frame review; frame-difference spike scan; numeric audio checks; reviewer/judge agents with bounded fix rounds | Stated |
| Human | Direction, rights, and "saying what felt wrong" | Stated |

The model writes and repairs code and plans timing. A browser produces the pixels and FFmpeg
encodes them. The model "hears" and "sees" only through numbers and images it asks for. This is
the same separation this harness was built around. What this corpus adds is the browser medium,
cue-level audio placement, and much more explicit verification habits.

## What this repository now implements in response

| Corpus practice | Harness feature | Evidence class |
|---|---|---|
| Single HTML file with a pure `seek(t)`, captured in Chromium | `backend: "html"` (`vch/html_backend.py`) with a virtual clock and seeded `Math.random`, adapters for `window.__vch.seek`, `window.seek`, `window.__timelines` and CSS/Web Animations, a loopback-only network, `--disable-partial-raster`, and optional sub-frame blur | — |
| Text telemetry for HTML | Visible DOM/SVG text with rendered size, clip/mask awareness, opacity, colour, pixel-backed contrast and `text-group`s | proxy |
| "Render one frame per beat first" | `vch stills --beats`, `--times`; sheet plus overlap and size warnings | preview only |
| Storyboard before code | `vch storyboard` | planning aid |
| "A sound on every hit" | `timing.hits` plus original synthesized cues, placed by measured peak | — |
| SFX "placed by measured peak, not file start" | `audio.mode: "mix"` layers with `align: "peak"`; linear `loudness_target` with a peak ceiling (no limiter) | — |
| "Loudnorm −14 LUFS, re-measured after encode" | `integrated_loudness_lufs`, `true_peak_dbtp` on the encoded file | hard |
| "Verify evenly spaced timestamps; no duplicated end frame" | `frame_timestamp_jitter_ms`, `encoded_frame_count` | hard |
| "Labels never overlap during a morph" | `text_overlap_violations` | proxy |
| "No dead time" / "holds ≤ 1 s" | `max_static_hold_s` (with explicit exclusions) | proxy |
| "Scan for single-frame pops" | `single_frame_pops` | proxy |
| "Last frame = first frame" | `loop_seam_ratio` | proxy |
| Hit sync | `audio_hit_sync_ms` (declared hits vs detected transient peaks) | proxy |
| Analyse a song or reference | `vch profile` (pacing, cuts, holds, pops, loudness, onsets, tempo and phase) | measurement of an input |
| Skills as the knowledge layer | `.claude/skills/codeable-video/SKILL.md` | — |

Two determinism defects surfaced while building the example (`examples/html.json`). Both were
caught by the existing forward/reverse/shuffled seek check:

1. **The composition cached its headline DOM between frames.** In some seek orders, frames
   rendered without a headline. Telemetry exposed this even at times where the pixels happened to
   match.
2. **Chromium's partial re-raster.** It made antialiasing at a fractional clip edge depend on the
   previously drawn frame: 2 pixels, ±16 levels. The backend now launches Chromium with
   `--disable-partial-raster`.

Neither was fixed by loosening a threshold.

Not implemented:

- Remotion or HyperFrames runtimes, and HyperFrames `data-start` clip semantics.
- Generative image, video, music or TTS APIs, beyond the existing local Kokoro narration.
- A limiter or compressor.
- Multi-format variants from one source.
- Seeking helpers for media elements.
- An automated vision-model critique loop. The production loop's author inspection already
  exists, and remains a self-attestation.

Human craft review stays human.

## Appendix: measured sample

The skillry slugs below were profiled with `python -m vch profile <original.mp4> --out <dir>`.
Analysis runs at no more than 30 fps on frames scaled to at most 160 px, and the medians above were
aggregated per toolchain. To reproduce, obtain the files from the linked pages.

- HyperFrames (8): mattworkman-309357, vince-builds-355650, thayto-dev-739735,
  itsahmedharoon-544194, javi-llofriu-059888, theviableedge-869918, miguel07code-091611,
  jake11moran-414633
- Remotion (7): l3d1c-632524, djadkison-394122, fr-sorrentino-871017, als-link-301108,
  tequilafunks-127728, iamshankhadeep-506266, localjulius-625706
- HTML / `seek(t)` / Playwright (7): curieuxexplorer-272483, dreyk0o0-165270, twoclipping-402193,
  twoclipping-000267, morse-369333, twoclipping-496100, annacher-433425
- Unspecified (16): chudry223-081860, acoramaa-053577, kgonia7-746268, jarvis11x-544635,
  wzarok-283635, friskyggg-054427, aayush4soni-644283, happycapyai-634965, janeloic-905802,
  anduraio-570761, himanshutwtxs-882858, ror-fly-880547, 0xscoffie-779830, eyishazyer-129686,
  redpersongpt-284430, rneayan-406275

Sample selection: a fixed random seed within the 8–70 s range, stratified by named toolchain, with
the requested video always included. The per-file profiles are not committed because they contain
thumbnails of third-party frames.
