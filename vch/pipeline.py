"""Render -> decode -> measure. No model API calls or network at runtime."""
from __future__ import annotations
import hashlib
import json
import math
import platform
import subprocess
import sys
import wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from .core import SceneRenderer, canonical, digest, source_manifest, contained


def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, timeout=180, **kwargs)


def probe(path):
    return json.loads(command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]).stdout)


def make_audio(spec, root, out):
    config = spec.get('audio', {'mode': 'none'})
    if config['mode'] == 'none':
        return None
    if config['mode'] == 'file':
        path = contained(root, config['path'])
        if float(probe(path)['format']['duration']) + 1e-3 < spec['video']['duration']:
            raise ValueError('Provided audio is shorter than the video; no silent auto-padding')
        return path
    # Original deterministic percussive bed; no copyrighted song or voice clone.
    sr, seconds = 48000, spec['video']['duration']
    signal = np.zeros(round(sr*seconds), dtype=np.float64)
    bpm = spec.get('timing', {}).get('bpm', 120)
    offset = spec.get('timing', {}).get('beat_offset', 0)
    beats = np.arange(offset, seconds, 60/bpm)
    for i, start in enumerate(beats):
        if start < 0:
            continue
        t = np.arange(int(sr*.22))/sr
        hit = np.sin(2*np.pi*(70*t + 14*(1-np.exp(-32*t))))*np.exp(-28*t)
        if i % 2:
            hit += .25*np.sin(2*np.pi*720*t)*np.exp(-60*t)
        a = round(start*sr); b = min(a+len(hit), len(signal))
        signal[a:b] += hit[:b-a]
    peak = max(1, float(np.max(np.abs(signal))))
    signal = signal/peak*config['gain']
    path = out/'audio.wav'
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes(np.rint(signal*32767).astype('<i2').tobytes())
    return path


def sample_times(spec):
    fps, duration = spec['video']['fps'], spec['video']['duration']
    # Boundaries + immediately neighboring frames + scene midpoints + regular probes.
    times = {0., (round(duration*fps)-1)/fps}
    for scene in spec['scenes']:
        for t in [scene['start'], scene['start']+1/fps, (scene['start']+scene['end'])/2,
                  scene['end']-1/fps, scene['end']]:
            if 0 <= t < duration:
                times.add(round(t*fps)/fps)
    for t in np.arange(0, duration, spec.get('qa', {}).get('sample_every', 1.)):
        times.add(round(t*fps)/fps)
    return sorted(t for t in times if t < duration)


def decode_frame(path, t, target):
    command(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(path), '-frames:v', '1', '-y', str(target)])
    if not target.is_file():
        raise ValueError(f'Failed to decode t={t}')


def render(spec, root, out, trust_code=False):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError('Use a new run directory: immutable runs are never overwritten')
    before = source_manifest(root, spec)
    renderer = SceneRenderer(spec, root, trust_code)
    out.mkdir(parents=True)
    (out/'contract.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2))
    audio = make_audio(spec, root, out)
    v = spec['video']; fps = v['fps']; n = round(v['duration']*fps)
    args = ['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f"{v['width']}x{v['height']}",'-r',str(fps),'-i','-']
    if audio:
        args += ['-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:a','aac','-b:a','192k']
    else:
        args += ['-an']
    args += ['-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
             '-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709',
             '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
             '-t',str(v['duration']),'-movflags','+faststart',str(out/'video.mp4')]
    with (out/'render.log').open('wb') as log, (out/'trace.jsonl').open('w') as trace:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=log)
        try:
            for i in range(n):
                t = i/fps
                frame = renderer.sampled(t)
                trace.write(canonical({'frame': i, 't': t, 'elements': frame.elements})+'\n')
                proc.stdin.write(frame.image.tobytes())
            proc.stdin.close()
            if proc.wait(timeout=180):
                raise RuntimeError('Encoder failed; inspect render.log')
        except BaseException:
            proc.kill(); proc.wait(); raise
    after = source_manifest(root, spec)
    if before != after:
        raise RuntimeError('Project changed during render; run is invalid, render from a stable checkout')
    probes = sample_times(spec)
    (out/'frames').mkdir()
    samples = []
    # Exercise forward -> reverse -> shuffled seek ordering; compare raw pixels AND telemetry.
    reference = {}
    for t in probes:
        frame = renderer.sampled(t)
        reference[t] = hashlib.sha256(frame.image.tobytes()+canonical(frame.elements).encode()).hexdigest()
    differences = []
    for t in list(reversed(probes)) + probes[::2] + probes[1::2]:
        frame = renderer.sampled(t)
        h = hashlib.sha256(frame.image.tobytes()+canonical(frame.elements).encode()).hexdigest()
        if h != reference[t]:
            differences.append(t)
    for i, t in enumerate(probes):
        rel = f'frames/{i:04d}.png'
        decode_frame(out/'video.mp4', t, out/rel)
        im = Image.open(out/rel)
        pixels = np.asarray(im)
        expected = np.asarray(renderer.sampled(t).image)
        samples.append({'t': t, 'file': rel, 'sha256': digest(out/rel),
                        'raw_sha256': reference[t],
                        'decode_mae': float(np.mean(np.abs(pixels.astype(float)-expected))),
                        'black_fraction': float(np.mean(np.max(pixels,axis=2)<12))})
    cols = 4; tw = 240; th = round(tw*v['height']/v['width']); ch = th+26
    sheet = Image.new('RGB',(cols*tw, math.ceil(len(samples)/cols)*ch),'#dddddd')
    draw = ImageDraw.Draw(sheet)
    for i, sample in enumerate(samples):
        im = Image.open(out/sample['file']); im.thumbnail((tw,th))
        x,y = (i%cols)*tw,(i//cols)*ch
        sheet.paste(im,(x,y)); draw.text((x+5,y+th+3),f"t={sample['t']:.3f}s",fill='black')
    sheet.save(out/'contact-sheet.jpg',quality=90)
    evidence = {'samples': samples, 'determinism_mismatches': differences, 'sampling': 'boundaries + midpoint + periodic; not exhaustive perception',
                'probe': probe(out/'video.mp4')}
    (out/'evidence.json').write_text(json.dumps(evidence,indent=2))
    manifest = {'source': before, 'video_sha256': digest(out/'video.mp4'),
                'trace_sha256': digest(out/'trace.jsonl'), 'evidence_sha256': digest(out/'evidence.json'),
                'contract_sha256': digest(out/'contract.json'),
                'runtime': {'python': sys.version, 'platform': platform.platform(),
                            'ffmpeg': command(['ffmpeg','-version']).stdout.decode().splitlines()[0]},
                'model': {'provider':'unverified/not invoked','model_id':None},
                'audio': spec.get('audio',{'mode':'none'})}
    binding = {k:manifest[k] for k in ('source','video_sha256','trace_sha256','evidence_sha256','contract_sha256')}
    manifest['review_binding'] = hashlib.sha256(canonical(binding).encode()).hexdigest()
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return out


def audit(out, root=None):
    out = Path(out)
    m = json.loads((out/'manifest.json').read_text())
    for path,key in [('video.mp4','video_sha256'),('trace.jsonl','trace_sha256'),('evidence.json','evidence_sha256'),('contract.json','contract_sha256')]:
        if digest(out/path) != m[key]:
            raise ValueError(f'Stale/tampered evidence: {path}')
    evidence = json.loads((out/'evidence.json').read_text())
    for sample in evidence['samples']:
        if digest(contained(out,sample['file'])) != sample['sha256']:
            raise ValueError('Decoded QA frame changed after measurement')
    binding = {k:m[k] for k in ('source','video_sha256','trace_sha256','evidence_sha256','contract_sha256')}
    if m['review_binding'] != hashlib.sha256(canonical(binding).encode()).hexdigest():
        raise ValueError('Invalid review binding')
    if root:
        s = json.loads((out/'contract.json').read_text())
        if source_manifest(root,s) != m['source']:
            raise ValueError('Source changed since render; produce a fresh run')
    return m
