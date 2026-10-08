# Measuring requirements without inventing certainty

The unit of evaluation is a **requirement**, not a single overall quality score.
Every requirement has an ID, explanation, evidence class and acceptance rule.

| Class | Examples | What may be concluded |
|---|---|---|
| hard | Encoded dimensions, duration, frame rate, presence of audio | Objective property of this rendered file |
| proxy | Text bounds/contrast, beat-grid cuts, decoded-frame motion, OCR | Named limited measurement, not a substitute for the goal |
| human | Welcoming, exciting, trustworthy, understandable, brand fit | Explicit reviewer judgment with reasons and timestamp evidence |

All three classes can block acceptance. There is no averaging that allows a high
motion score to cancel an invented opening claim. Coverage is `measured / total`;
a failed check is measured but not satisfied. Unknown metric, missing telemetry,
missing OCR language, non-finite value or stale review stays unmeasured/blocked.

## Built-in metric semantics

| Metric | Evidence | Limits |
|---|---|---|
| duration_s / width_px / height_px / fps | ffprobe encoded video stream | Integer fps supported in contract v1; equality may need min/max requirements for other pipelines |
| audio_present | Encoded stream list | Presence does not mean useful/safe/appropriate sound |
| audio_peak_dbfs | Decoded floating-point PCM | Sample peak, not intersample true peak or integrated LUFS |
| determinism_mismatches | Raw frame + telemetry hashes after forward, reverse and shuffled seeks | Finite samples; not mathematical proof of every possible time |
| decode_mae | Encoded sample pixels against raw render pixels | Compression/color consistency, not aesthetics |
| text_present / text_absent | Every output frame's instrumented text trace | Occlusion/bitmap-embedded claims can evade trace; not an NLP fact checker |
| minimum_text_size_px | Font sizes in trace | Pixel size is not legibility; viewing distance and glyph choice matter |
| minimum_contrast | Foreground and declared background | Ignores complex backdrops and occlusion; not WCAG certification of video |
| safe_area_violations | Actual font rasterizer bounds for every frame | Text telemetry only; intentionally decorative offscreen shapes ignored |
| minimum_text_hold_s | Longest continuous identical text per element ID | No proof viewer understood/read it; must pair with normal-speed review |
| beat_cut_error_ms | Declared cuts and BPM/offset | Grid consistency, not detected alignment to an arbitrary soundtrack |
| black_fraction | Sampled decoded pixels below RGB threshold | Intentionally black shots count; no universal correct threshold |
| motion_fraction | Changed pixel fraction between sampled frames | Cuts count; not optical flow, smoothness or excitement |
| ocr_contains | Tesseract on decoded frames | Optional, sampled, language-dependent; can misrecognize text |
| integrated_loudness_lufs | FFmpeg `ebur128` (BS.1770) on the **encoded** AAC audio | Gated programme loudness; not mix quality or perceived balance |
| true_peak_dbtp | Same filter, 4× oversampled true peak | Player and platform resampling can differ; the corpus showed peaks rising after AAC encode |
| encoded_frame_count | ffprobe packet count | Catches duplicated or dropped end frames; not visual content |
| frame_timestamp_jitter_ms | Packet PTS vs an ideal constant-rate grid | A timing-grid check only |
| text_overlap_violations | Frame×pair count of distinct text boxes (line fragments when present) intersecting by ≥ `min_fraction` (default 25%) of the smaller box | Layered designs may intend overlap (`ignore_ids`); occlusion by non-text art not modelled |
| max_static_hold_s | Longest run of decoded frames whose mean luma change is < `still_delta` (0.5/255) | Slow drifts count as still; deliberate holds need explicit `exclude` windows frozen in the contract |
| single_frame_pops | Decoded frames that differ from **both** neighbours by ≥ `floor` (8/255) and > `ratio` (3×) the neighbours' mutual difference | Intentional flash frames count; cuts do not. Exclude deliberate flashes explicitly |
| loop_seam_ratio | Last→first decoded-frame change relative to neighbouring frame steps (0 = identical) | Meaningful only for loops; not perceived loop smoothness |
| audio_hit_sync_ms | Max distance from each declared `timing.hits` time to a detected transient peak in the encoded audio | Onsets are not attributed to sources (a bed hit can satisfy a cue); soft sounds may be missed and then fail |

## Turning a vague requirement into a defensible contract

Example: “Make it exciting but trustworthy.”

- Keep “exciting” as a human/audience outcome. Define the audience and rubric.
- Possible candidate proxies: no unintentionally dead interval, timing around
  narrative emphasis, varied shot scale. State why each might help, and its failure
  modes. Do **not** name them “excitement = 0.95”.
- “Trustworthy” needs claim provenance and human fact review. A banned-word list
  only catches the listed strings. It cannot detect every misleading implication.
- Collect blind A/B audience judgments if the question is commercial effectiveness.
  That study is not implemented here and should not be replaced by an LLM rating.
- Freeze thresholds before comparing candidates; keep output requirements invariant.

## Extending measurements

Add a documented evaluator in `vch/evaluate.py`, register its evidence class in
`METRIC_TYPES`, add tests with a true pass and a deliberate failure, and document
units/sampling/missing-data behavior. The spec's `metric` field is an identifier,
not arbitrary Python or an expression passed to `eval`. Unknown identifiers fail
closed. Changes to evaluators require owner review, not the candidate-author agent.

To integrate another engine, produce the same video, trace, samples and manifest
contract, then supply a frame adapter for determinism tests. Do not assume its
telemetry is trustworthy merely because it matches this JSON shape. The pdoom primitive adapter now produces this evidence through the same
pipeline; it does not claim full upstream Engine integration.

## Preventing evaluation gaming

Keep reviewer/evaluator permissions separate from author permissions. Preserve
contracts and run directories. Use encoded output rather than just previews. Bind
reviews to source+artifact hashes; don't accept old approvals on new renders. Do
not automatically populate human pass decisions. The current hashes detect
accidental changes, not an attacker with write access to the entire evidence set.

This harness does not assert accessibility or flash safety; `single_frame_pops` is a continuity check, not a photosensitive-epilepsy (flash/red-flash) test. High-intensity motion,
full-screen flashes, complex photos and dense typography need specialized checks
and human review before distribution.

## Decoded-media evidence and HTML telemetry

At render time the harness decodes its own MP4 again. It records per-frame luma change at an
analysis size of at most 160 px (`decoded_motion`), packet timestamps (`frame_timing`), and BS.1770
loudness plus transient peaks (`audio_analysis`). All of this goes into `evidence.json`, which the
review binding hashes. Runs made before this version lack these keys, so the new metrics stay
**unmeasured** for them, never pass. `vch profile` applies the same signal code to any input file,
analysed at no more than 30 fps, so measurements of a reference and of a candidate are comparable.

HTML telemetry comes from the live DOM. Observations are text nodes, plus `text-group`s for
`data-vch-id` elements whose words sit in separate nodes. Policies:

- **Visible:** effective opacity is at least 0.05, visibility is `visible`, and at least 15% of the
  line box survives overflow and `clip-path` masks (inset, circle and polygon bounds).
- **Size:** line-box height divided by the font's content-area ratio. That captures CSS transforms
  and SVG scaling. Within ±4% of the CSS size, the CSS size is reported, because line boxes are
  pixel-snapped.
- **Contrast:** the rendered text colour (alpha × inherited opacity) against the median non-text
  pixel inside its box on the captured frame. `minimum_contrast` ignores fade transitions:
  observations below 95% (`settled_fraction`) of that element's own peak opacity. Unknown fills
  such as gradient or transparent text keep the metric unmeasured unless `allow_unknown` is frozen
  into the contract.
- `text_present` / `text_absent` search text and text-group observations. Geometry metrics use
  only text nodes.

## Reference comparison (`vch profile`, `vch profile-compare`)

`vch profile` also samples decoded frames every 0.5 s at up to 480 px and reports three detail
proxies. They are not contract metrics.

| Proxy | Definition | Limits |
|---|---|---|
| edge density | Share of pixels whose Sobel luma step exceeds 24/255 | Text, linework and texture all count; noise and film grain inflate it |
| grid cells in use | Share of a 12×6 grid whose cells contain at least 2% edge pixels | A single small element in an otherwise empty frame scores low by design |
| colourfulness | Hasler & Süsstrunk (2003) opponent-colour statistic | Says nothing about palette quality or brand fit |

`vch profile-compare a/profile.json b/profile.json` prints these next to pacing and loudness for two
files. The table gives ratios, except for loudness, where a ratio of decibel values would mislead.
Use it to ask why a candidate is sparser than a reference; it cannot say which is better. In the
study, a deliberately minimal corpus film scored 0.018 edge density against the requested
explainer's 0.088.

## Production evidence additions

All of these are explicitly proxies: `planned_scene_count` counts declared windows;
`planned_visual_kinds` counts declared mechanisms (not perceived variety);
`narration_seconds` sums independently synthesized phrase placements (not ASR);
`caption_timing_error_ms` compares captions with those placements (not pronunciation
or word alignment). Missing evidence remains unmeasured. Counts cannot establish
reference similarity. The source manifest also binds executing harness/adapter code
when candidate projects live in separate production-session directories.
