# Single-prompt production protocol

The user's one prompt starts an internal multi-step job. It does not mean one LLM
completion or that evaluation, editing and rendering disappear.

Return JSON with `contract`, optional `files` (scenes/*.py, or text files under
compositions/<name>/ for the html backend), and optional `author` (self-reported). Use all frozen requirements unchanged. Decide the script,
scene plan and appropriate original visual language from the user's prompt. Do
not reproduce a reference's branding, soundtrack or visual signature by default.

Three tested render backends:

- `html`: an agent-written composition under `compositions/<name>/` exposing a pure
  `window.__vch.seek(t)` (or `window.seek`, paused `window.__timelines`, CSS/Web Animations).
  Set `html.entry`; scene `module` is optional. Author files may be any text under
  `compositions/<name>/` (.html .js .css .json .svg .glsl); media must be declared assets with
  rights. Rules and the seek protocol are in AUTHORING.md ("HTML compositions"). Visible DOM/SVG
  text is measured automatically; mark semantic lines with `data-vch-id`.
- `pillow`: Python `render(ctx) -> Frame`, arbitrary reviewed scene code.
- `pdoom`: an original browser timeline that executes pinned pdoom FSPass shader
  primitives. No full upstream Engine/adaptive post stack. Set render.samples=1.
  Scene `module` can be `scenes/browser.py` (a marker; it is not executed).
  Available params.kind: hero, finale, network, depth, pipeline, wave, timeline,
  code, samples, comparison, meter, cards, list. Params include chapter, headline,
  labels (short strings), word (hero), code (code scene), theme (light/dark).
  Set style.font to assets/fonts/NotoSerifSC.ttf; declare that and Inter.ttf with
  their OFL provenance in assets. Keep body copy and headlines brief.

For Mandarin narration: each scene has `narration: [short phrase, ...]` and the
contract has `speech: {voice: "zf_001", speed: 1.1}`. Local Kokoro creates each
phrase; measured speech duration must fit its scene. Too-long speech fails before
video render. Do not silently cut, pad by inventing speech, or alter duration to
get past this check. The runtime supplies phrase-timed captions and a quiet
original percussive bed. Use multiple short phrases rather than a paragraph.

Narration and captions are not a semantic quality certificate. Inspect actual
rendered frames, listen to the mix and record any limits. Human review must remain
pending unless a real authorized reviewer supplies an artifact-bound decision.

Modes:

0. `python scripts/one_prompt.py --prompt-file ... --author-command '[...]'
   --out ... --trust-scene-code` extracts and logs proposed constraints from just
   the prompt, then freezes them and starts production. The model's extraction
   is not human-approved. A mandatory `PROMPT-FIDELITY` human criterion checks
   omissions and weakened interpretations against the original prompt.
1. `vch produce --prompt-file ... --constraints ... --out ...` creates an immutable
   author packet for the current coding agent. This is an agent workspace handoff.
2. Add `--author-command '["executable","arg"]' --trust-scene-code` for an
   unattended loop. The external adapter reads the complete request JSON on stdin
   and emits one response JSON on stdout. It owns authenticated model selection;
   the harness does not read API secrets or guess model names. A configured author
   can inspect the feedback paths. This command is trusted host-side executable
   code, not sandboxed by this harness. Run it in your approved isolated worker.
3. `--candidate-file response.json` rerenders a saved response. It is labelled
   **candidate-replay**, never fresh model generation. Use it to reproduce the
   benchmark, not to claim that an arbitrary new prompt was understood.

The automatic loop repairs machine failures, up to three immutable attempts. It
stops at `needs_review` when those checks pass; it cannot invent subjective
approval or automatically infer a film's quality from scene counts. Configuration,
render errors and changed frozen requirements remain blocked.
