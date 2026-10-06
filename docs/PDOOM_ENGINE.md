# pdoom-video integration: implemented subset

The reference uses [mexicat/pdoom-video](https://github.com/mexicat/pdoom-video).
The earlier harness only documented it. This version executes its `FSPass` shader
primitive inside an original Three.js/Canvas2D timeline, then sends actual frames
to FFmpeg and the common evaluator.

Pinned upstream commit: `a048746d25fa0333ca884fb79fe4482b9c89250d`.
Unmodified MIT files: gl.ts, glsl/common.ts, palette.ts, scale.ts, util.ts, scene.ts.
See `backends/pdoom/PROVENANCE.md` and `vendor/LICENSE`. These contain renderer
utilities, not copied film scenes, music, lyrics, voices or fonts.

| Capability | Current adapter |
|---|---|
| Actual upstream shader primitive execution | Implemented via FSPass |
| Pure-time, out-of-order seek checks | Implemented on raw browser output |
| Native-resolution text and diagrams | Implemented with font-rasterizer telemetry |
| Soft shader background | Half output resolution, declared in manifest |
| Mandarin narration and captions | Local Kokoro; phrase timing, not forced word alignment |
| Actual encoded MP4 inspection | Shared evaluator and decoded contact sheets |
| Full upstream Engine, HUD, native scenes | Not integrated |
| Adaptive temporal supersampling / full post stack | Not integrated; adapter requires samples=1 |

The model authors the script and scene description; the browser renderer produces
pixels; FFmpeg encodes; the harness gathers evidence. Using pdoom utilities does
not establish aesthetic parity with the supplied film. The manifest records the
engine subset, upstream commit, browser version and rendering scales.

Upstream engine documentation: https://github.com/mexicat/pdoom-video/blob/main/docs/ENGINE.md
Upstream code license: https://github.com/mexicat/pdoom-video/blob/main/LICENSE

Build and run through docs/PRODUCTION_SETUP.md. The adapter loads only declared
local assets and blocks outbound browser requests while rendering. Author commands
and Python plugins remain trusted executable code; use an appropriate isolated
worker. The harness itself is not an OS sandbox.
