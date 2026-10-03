# Reproduce the narrated browser benchmark

Python 3.11–3.12, Node.js compatible with the locked Vite build, FFmpeg/libx264,
and enough disk for an approximately 380 MB speech model/voice pack are required.
No paid API is used by this replay. Initial setup downloads dependencies/models;
video rendering itself uses local files and loopback transport only.

```sh
python scripts/prepare_fonts.py
python -m pip install -r requirements-production.txt
python -m playwright install --with-deps chromium
npm ci --prefix backends/pdoom
npm run build --prefix backends/pdoom
python scripts/download_speech_models.py --out models/kokoro
python -m vch produce \
  --prompt-file benchmarks/reference/prompt.txt \
  --constraints benchmarks/reference/constraints.json \
  --candidate-file benchmarks/reference/candidate.json \
  --speech-model-dir models/kokoro \
  --out runs/reference-replay-001 --trust-scene-code
```

Exit 3 means the encoded artifact passed the machine checks and still needs human
review. Exit 2 means blocked. The replay uses a stored author response; it is NOT
an independent live GPT/Opus experiment. Use a new directory for each run.

For new prompts, omit `--candidate-file` to prepare an author packet, or replace
it with `--author-command '["your-approved-model-adapter"]'`. The adapter reads
request JSON on stdin, writes response JSON on stdout, and handles its own model
configuration. See SINGLE_PROMPT.md. No authenticated hosted model adapter was
available in the cloud benchmark, so live unattended model generation remains
unverified. Subprocess fixture tests validate the repair loop, not model quality.

The stored candidate was authored by the current coding agent from the benchmark
prompt without further user creative input. The benchmark prompt operationalizes
the user's goal; it is not represented as a verbatim quote from the user.

Speech: Kokoro-82M-v1.1-zh, voice zf_001, local CPU inference, Apache-2.0 model.
https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh
ONNX runtime wrapper: https://github.com/thewh1teagle/kokoro-onnx (MIT).
Transitive speech/G2P dependencies retain their own licenses. Models are downloaded
explicitly and hash-checked; they are not bundled into the source repository.

Renderer: pinned pdoom-video FSPass primitives under MIT; original timeline,
compositions and export/evaluation adapter. This is not the entire upstream engine.
No upstream song, stock scenes, artwork, lyric file or fonts are redistributed.
