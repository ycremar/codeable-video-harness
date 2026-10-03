# pdoom-video is the reference renderer

The uploaded closing frame explicitly credits `pdoom-video`. The upstream
[repository](https://github.com/mexicat/pdoom-video),
[engine guide](https://github.com/mexicat/pdoom-video/blob/main/docs/ENGINE.md) and
[license](https://github.com/mexicat/pdoom-video/blob/main/LICENSE) were checked
on 2026-10-03 UTC. This corroborates the engine mechanism; it does not establish
the exact fork or commit used by the Chinese film.

Inspected upstream head: [`a048746d25fa0333ca884fb79fe4482b9c89250d`](https://github.com/mexicat/pdoom-video/commit/a048746d25fa0333ca884fb79fe4482b9c89250d).

## Keep the layers separate

- **Author:** Opus/GPT produces scene code, narrative and edits.
- **Renderer:** pdoom-video evaluates TypeScript/Three.js scenes in a browser.
- **Exporter:** its offline script sends frames to FFmpeg.
- **Harness:** requirements, orchestration, evidence collection and acceptance.

The current `vch run` invokes our Python/Pillow backend. It does not invoke
pdoom-video. A pdoom integration must keep the same requirement IDs and evidence
semantics; using a richer engine does not itself prove quality.

## Native upstream workflow

These are upstream entry points, **not commands executed in our demo runs**:

```sh
# In an independently reviewed upstream checkout:
cd app
bun install
bun scripts/render.ts stills --t 12.5 --only open --out ../out/wip/open
bun scripts/render.ts sheet --from 1.5 --to 9 --n 16 --cols 4 --only open --out ../out/wip/open/sheet.png
bun scripts/render.ts video --from 20 --to 25 --only hook --samples 4 --out ../out/wip/hook.mp4
```

Its scene authoring surface is `app/src/scenes/`; the edit lives in
`app/src/timeline.ts`; export is `app/scripts/render.ts`. Its documentation covers
seekable rendering, shared audio timing, sub-frame sampling and isolated previews.
Use its documentation for installation, Chrome requirements and version-specific
flags. Treat upstream code as executable and review it before running.

## What an actual adapter still needs

1. Pin and record the chosen upstream commit and any local engine changes.
2. Map the approved storyboard/assets into native scene modules and timeline.
3. Capture native render commands, environment and actual encoded output.
4. Produce honest evidence for each check. Encoded dimensions/duration can be
   inspected directly. Native text bounds, declared contrast and repeatable raw
   seeks require instrumentation; absent evidence must remain unmeasured.
5. Preserve separate artifact-bound human judgment for semantics and craft.

The current Python evaluator is coupled to its run-evidence format; simply
renaming a pdoom MP4 to `video.mp4` is not an adapter. No pdoom render or integration
test is claimed here. The backend is intentionally an explicit remaining task.

## Rights

pdoom-video's code is MIT. Its song, lyrics and fonts have separate rights; the
code license does not make the source film's media reusable. This repository
does not redistribute its music, lyrics, screenshots or engine source. Our demo
percussion is original procedural audio; our font files retain their OFL notices.
