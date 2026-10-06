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

## Concrete GPT/Opus API adapter (optional, live use unverified here)

`adapters/model_api.py` implements OpenAI Responses and Anthropic Messages requests
without requiring their SDKs. The exact model ID is mandatory. Configure credentials
through your environment/secret manager; never put keys in a prompt or repository.
The adapter rejects calls unless `--allow-paid-api` is explicitly supplied. No paid
call was made in the benchmark. Each invocation makes one request with no hidden
retry; the production loop caps attempts at three (at most three author plus three
inspection requests). Token caps limit output size, not total dollar cost.

After separately authorizing your API budget and configuring the appropriate key:

```sh
python scripts/one_prompt.py --prompt-file your-brief.txt \
  --author-command '["python","adapters/model_api.py","--provider","openai","--model","YOUR_MODEL_ID","--allow-paid-api"]' \
  --speech-model-dir models/kokoro --out runs/new-brief-001 --trust-scene-code
```

Use `--provider anthropic` and your explicit Opus model ID for Anthropic. Select a
model that accepts image input for the inspection phase. The wrapper extracts an
initial contract from the one free-form prompt, logs it, and freezes it before
rendering or repairs. It adds a mandatory human `PROMPT-FIDELITY` requirement:
model-proposed constraints are not user-approved truth. The first planning call
also supplies the first candidate, so the total cap remains six API requests.
Fixture coverage exercises this whole extraction/render/inspection path; live
model behavior remains unverified.

If you already have independently reviewed constraints, use `python -m vch produce`
with `--constraints your-constraints.json` instead. The reference constraint file
requires a 192-second Mandarin browser film; it is not a universal contract.

The adapter sends the actual decoded contact-sheet image for visual inspection.
It preserves the explicit limitation that static images cannot certify motion or
speech quality. Returned API model/response IDs and usage are retained separately
from self-reported model claims. Fixture tests cover payloads, incomplete responses,
missing credentials, no-spend defaults and review limitations; they are not live
API integration tests.

Official schema sources checked 2026-10-03:

- https://developers.openai.com/api/docs/guides/images-vision
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://platform.claude.com/docs/en/api/messages/create
