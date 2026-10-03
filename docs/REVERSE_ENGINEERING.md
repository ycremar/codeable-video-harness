# What the recording teaches — and what this harness adds

Analysis date: 2026-10-03 UTC. User file:
`ScreenRecording_10-02-2026 21-31-33_1.mp4`.

## Inspection scope

The supplied screen recording is 190.5s, 1112×512, 30fps, with AAC audio. The film
inside it shows a longer ~202s/60fps authored timeline. These are different clocks.
The first captured frames include player UI; the recording ends before the
separately supplied closing screenshot (~199.6s authored time). Do not infer that
the recording itself contains the entire 202-second film.

I inspected five-second-spaced full-video contact sheets and the closing image.
The explanatory on-screen text is sufficient for the points below. Audio was
extracted for inspection, but **no speech transcription or complete audio listening
was performed**; this is not a verbatim transcript. Timestamps below refer to the
uploaded recording and are approximate observation anchors, not exact cut times.

Reference SHA-256 (inputs are not bundled):

- Recording: `7593da845bece498bcab56b9dd1de39c321bfb574a1ac1fe182e1bd73a5d8c27`
- Closing still: `2d191524751efc462790d78346057e04ae614435b673364549245ddc7ac5c30c`

## Observed in the recording

| Recording time | Visible explanation | Reusable method |
|---|---|---|
| 0–25s | Model writes code; prompt requests an impressive video longer than 185s; duration is measurable while “impressive” is vague | Separate concrete requirements from subjective goals |
| 25–40s | A “shock” number is introduced | Treat an invented scalar as a narrative device, not validated evaluation |
| 45–55s | One accent color and prohibited visual clichés | Write a project-specific style/constraint contract; don't make this palette universal |
| 60–70s | Drum hits represented in code, 120 BPM, visible beat timeline | Audio, scene cuts and motion events share one timebase |
| 80–95s | Frame = f(t), arbitrary seek, same time produces identical frame | Deterministic, seekable rendering independent of playback history |
| 100–110s | Compare 1, 4 and 108 sub-frames; more continuous fast motion | Temporal supersampling for motion blur; quality/cost tradeoff |
| 115–125s | Rendered contact sheet; text overflow and beat-timing repair; repeated review rounds | Inspect actual output and repair concrete defects iteratively |
| 130–150s | Invoice-like claims: no camera/actors/AI-generated stills; synthetic voice; code line count | Distinguish model authoring from rendering and audio synthesis; film's claims are not independently audited |
| 155–185s | “Shock” score escalates beyond its scale, reaches absurd magnitudes and NaN | The video itself demonstrates why an uncalibrated metric cannot stand in for human judgment |
| Separate final still | Credits identify pdoom-video as MIT; voice synthesis; viewer decides impact | Verify engine/license and preserve human evaluation |

The “7 rounds” and “14,692 lines” shown on screen are claims **inside the film**.
They are not independently verified execution logs. Nor does a displayed “Opus
5.5” prove which model produced the original. This harness doesn't reproduce those
numbers or use them as quality evidence.

## Verified against the named engine's official repository

[mexicat/pdoom-video](https://github.com/mexicat/pdoom-video) documents a
TypeScript/Three.js renderer with browser preview, offline headless export and
separate audio/timing data. Its [engine guide](https://github.com/mexicat/pdoom-video/blob/main/docs/ENGINE.md)
describes scene modules, pure-time seeded rendering, explicit stateful-scene
exceptions, isolated still/contact-sheet/clip rendering and sub-frame sampling.
This corroborates the mechanism, not the provenance of this particular Chinese
film. Its [license](https://github.com/mexicat/pdoom-video/blob/main/LICENSE) covers
code under MIT; the project's fonts, music and lyrics have separate rights.

No upstream code, song, lyric file or artwork was copied into this harness. The
recording explains an approach; it does not expose the exact prompt history or
the complete code of the Chinese film. There is no defensible claim of exact
source reconstruction.

## General architecture extracted

1. Evidence-backed brief and asset rights.
2. Requirement contract: technical constraints, content, timing, style and review.
3. Narrative/scene plan and audio/timing plan.
4. Model writes code; a renderer evaluates `frame(t, seed, assets)`.
5. Export actual pixels and audio using a shared timebase.
6. Inspect boundaries, stills, contact sheets, decoded clips and sound.
7. Measure explicit checks; repair failing requirement IDs; preserve revisions.
8. Approve only the artifact actually reviewed.

## Original harness additions, not claimed features of the recording

Typed evidence classes, fail-closed unknown metrics, coverage reporting,
artifact-bound reviews, source and asset hashes, immutable run directories,
anti-threshold-weakening comparisons, intentional-failure tests, and a
provider-neutral coding-agent packet. These additions make the approach testable
and reusable across briefs. The optional synthesized drum bed demonstrates code
audio; it is not a copy of the reference soundtrack. TTS and automatic alignment
remain external integrations, not silently simulated capabilities.
