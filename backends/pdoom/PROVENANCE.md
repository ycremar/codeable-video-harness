# pdoom primitive adapter

`vendor/` contains unmodified MIT-licensed `gl.ts`, `glsl/common.ts`, `palette.ts`,
`scale.ts`, `util.ts`, and `scene.ts` from mexicat/pdoom-video commit
`a048746d25fa0333ca884fb79fe4482b9c89250d`. The license is in `vendor/LICENSE`.

This adapter actually imports and executes upstream `FSPass` for shader rendering.
It supplies an original declarative timeline, shader, typography, caption layer,
Python frame transport and evidence integration. It does not run upstream's full
`Engine`, adaptive sampler, stock scenes, HUD, music, lyrics or voice assets.
The inherited palette constants compile with the upstream shader helpers but are
not used by our scene palette. These boundaries are reported in the manifest.
