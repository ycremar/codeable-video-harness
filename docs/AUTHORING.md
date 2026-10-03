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
