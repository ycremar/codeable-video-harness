# Codex goal handoff: reference-quality video from one prompt

Prepared 2026-10-03. This file is a handoff, not an activated Codex Goal.

## Activate in Codex

Open `ycremar/codeable-video-harness`, check out
`improve/single-prompt-production` (PR #1), attach the original reference video,
and enter:

```text
/goal Follow docs/CODEX_GOAL_HANDOFF.md. Improve and verify this harness until one fresh prompt produces an original video comparable to the attached reference in visual storytelling, motion, narration and pacing. Use actual rendered evidence to drive repairs; passing technical checks alone is not completion. Work within the configured goal budget and AGENTS.md limits. Stop only on verified completion, an exhausted budget, or a concrete blocker with the evidence and exact next action recorded.
```

The application owns Goal activation, continuation and budget. A repository file
or an assistant saying "goal mode" does not activate that state.
Official guidance: https://learn.chatgpt.com/docs/long-running-work

## Resume from this state

- Repository: https://github.com/ycremar/codeable-video-harness
- PR: https://github.com/ycremar/codeable-video-harness/pull/1
- Prior handoff commit: `4173c0bdc304c815119e547c3a618a3075210aec`.
- Read `AGENTS.md`, `README.md`, `docs/AUTHORING.md`, `docs/MEASUREMENT.md`,
  `docs/SINGLE_PROMPT.md`, `docs/PRODUCTION_SETUP.md`, and
  `benchmarks/reference/RESULTS.md` before implementation.
- The completed candidate is 192 seconds, 1280×720 at 30 fps, with Mandarin
  narration and phrase captions. Its 17 machine requirements pass; 52 local tests
  passed. CRAFT, VOICE and COMPREHENSION remain pending.
- This was a saved-candidate replay authored by the previous coding agent. It
  does not establish fresh unattended generation or broad prompt generalization.
- The browser adapter executes pinned MIT pdoom-video FSPass primitives. It does
  not implement the complete upstream Engine, scene system or post stack.
- Narration overflow and cross-scene canvas determinism were repaired. Preserve
  their regression coverage and the failed-run evidence in the repository.

## Inputs and portability

The actual reference is `ScreenRecording_10-02-2026 21-31-33_1.mp4`, provided by
the user. Attach it in the new Codex thread; it is not committed to Git. Do not
substitute the generated benchmark for the reference.

The prior candidate was delivered as `single-prompt-benchmark.mp4`, SHA-256
`1049f48032404f3f072f5d11253d73209e1ebf83d8f1697a16646d6ef043704d`.
Reproduce it with the documented setup/replay command if its bytes are absent.
Speech weights and installed dependencies are also outside Git; setup is in
`docs/PRODUCTION_SETUP.md`.

Old `/workspace/scratch/...` paths are temporary and do not identify files on a
new machine. The reported `04-ATL_Logo.jpeg` error is unrelated to this generic
reference benchmark; no ATL logo is required to continue it. If an ATL-specific
brief later requires that asset, use the actual supplied attachment and record
its new local path instead of assuming the old scratch path exists.

## Next work

1. Inspect the original reference and current candidate. Record concrete,
   timestamped gaps in staging, changing visual hierarchy, transitions, camera
   movement, motion serving the explanation, narration and pacing. Previous
   decoded-frame inspection found repeated header/body layouts, graph spheres
   and cards; the result reads more like an animated presentation.
2. Improve reusable rendering/authoring capabilities that address those gaps.
   Keep the reference's ambition while using an original visual language. Do not
   replace missing craft with inflated scene counts or an invented quality score.
3. Use the active Codex agent to author and revise scene code directly. Optional
   OpenAI/Anthropic API adapters are not a prerequisite for improving the harness
   or making a new film. Do not treat absent API keys as a blanket blocker. Use
   only actually available, authorized model access; do not claim a separate
   independent model run unless one occurred.
4. Freeze a fresh prompt and requirements before generation. Log the authoring
   path, assumptions, interventions and attempts. A run conditioned on prior
   candidates is assisted iteration; use a fresh isolated session for a genuinely
   independent one-prompt test when the environment supports it.
5. Test short representative scenes and transitions before each expensive full
   render. Then render the entire film, inspect encoded frames, and play/listen
   when supported. Preserve failures and repair named deficiencies without
   weakening requirements. Follow the existing per-brief repair cap and the
   user-configured Goal budget; checkpoints do not reset either limit.
6. Commit reusable improvements and evidence to the working branch. Deliver the
   final MP4, reproducible command, exact revision, tests, comparison and remaining
   limits. Keep user-supplied reference media and credentials out of Git.

## Completion and honest stopping

Completion requires a documented fresh one-prompt authoring run, an entire
encoded film satisfying the frozen technical contract, and a timestamped review
of the creative and audiovisual criteria against the reference. Subjective
human requirements need the actual designated reviewer; the agent cannot approve
them on the reviewer's behalf. Static contact sheets cannot establish full-motion
quality, pronunciation or comprehension.

If the runtime cannot access the reference, play/listen, run an independent
session, obtain a required review, or continue within its configured budget,
finish the useful authorized work and record the exact blocked claim and next
action. Do not mark the overall goal complete because an MP4 exists or the
technical test suite is green.
