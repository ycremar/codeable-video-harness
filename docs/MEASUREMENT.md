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

This harness does not assert accessibility or flash safety. High-intensity motion,
full-screen flashes, complex photos and dense typography need specialized checks
and human review before distribution.

## Production evidence additions

All of these are explicitly proxies: `planned_scene_count` counts declared windows;
`planned_visual_kinds` counts declared mechanisms (not perceived variety);
`narration_seconds` sums independently synthesized phrase placements (not ASR);
`caption_timing_error_ms` compares captions with those placements (not pronunciation
or word alignment). Missing evidence remains unmeasured. Counts cannot establish
reference similarity. The source manifest also binds executing harness/adapter code
when candidate projects live in separate production-session directories.
