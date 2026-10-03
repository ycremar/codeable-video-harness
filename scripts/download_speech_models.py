"""Explicit one-time setup. Does not run during video rendering."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

URLS={
 'kokoro-v1.1-zh.onnx':'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.1-zh.onnx',
 'voices-v1.1-zh.bin':'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.1-zh.bin',
 'config.json':'https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/raw/main/config.json',
 'MODEL_CARD.md':'https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/raw/main/README.md'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='models/kokoro');args=p.parse_args()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 expected=json.loads((Path(__file__).resolve().parents[1]/'benchmarks/reference/speech-model-lock.json').read_text())
 for name,url in URLS.items():
  target=out/name
  if not target.exists():
   print('Downloading',name,flush=True);temporary=out/(name+'.part')
   urllib.request.urlretrieve(url,temporary);temporary.rename(target)
  actual=hashlib.sha256(target.read_bytes()).hexdigest()
  if name in expected and expected[name]!=actual:raise ValueError(f'Hash mismatch: {name}; do not use unreviewed model bytes')
  print(name,actual)
if __name__=='__main__':main()
