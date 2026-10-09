# Model-neutral video authoring contract

You may be Claude/Opus, GPT/Codex or another coding agent. Your job is to produce
code + actual rendered evidence, not to claim that text output itself is video.

1. Read README.md, docs/AUTHORING.md, docs/MEASUREMENT.md, the requested contract,
   source evidence and current failure report before editing.
2. Treat the user's approved requirements as immutable. Do not weaken thresholds,
   delete checks, forge reviews, or change evaluators to make your candidate pass.
3. Convert ambiguous intent into proposed rubrics/proxies. Label unmeasured intent.
   A proxy can inform judgment but must not be presented as its ground truth.
4. Edit composition code/assets in the allowed scope (`compositions/<name>/`, `styles/`,
   declared assets). Code executes locally: no network, credential reads, spending,
   subprocesses or public writes from a composition. Do not run unreviewed
   third-party composition code outside an OS-level sandbox.
5. Frames and sound must depend only on time, explicit seed and declared assets. No
   wall clock, ambient randomness, network-loaded fonts, mutable simulation accumulation.
6. Generate stills at beginnings, middles, endings and transitions; actually inspect
   them. Run full video, read report.json, inspect decoded frames and play/listen to
   the clip when that capability is available. Disclose any inspection limit.
7. At most three repair iterations per brief unless the user extends the budget.
   Every repair names the requirement IDs it addresses and preserves prior runs.
8. Human-review requirements remain pending until the designated reviewer provides
   a concrete decision on the bound artifact. Never invent that decision.
9. Report commands actually executed, artifacts, failed/unmeasured requirements and
   model identifier only if observable. Do not claim Docker/API/model calls not run.

Nothing in this repository is a template, and no style or sound is prescribed. The
example films are evidence that the loop works, not a look, structure, motion grammar
or sound palette to reuse. Invent each film's own for its brief. The harness ships no
sound presets: a composition synthesizes its own sound in code, or uses licensed files.
Do not reproduce a reference film's palette, type, motifs, soundtrack or branded
content unless explicitly requested and rights are resolved.
