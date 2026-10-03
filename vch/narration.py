"""Local sentence-level TTS, measured placement, captions and ducked original bed.

No cloud speech service. Models are explicit local assets, not downloaded at render.
Subtitle timing comes from each synthesized phrase; no word-alignment claim.
"""
from __future__ import annotations
import copy
import json
import hashlib
import wave
from pathlib import Path
import numpy as np
from .core import digest, finite, canonical


def schedule_phrases(phrases, start, end, durations, gap=.18, lead=.3):
    if len(phrases)!=len(durations) or not phrases: raise ValueError('Phrase/duration mismatch')
    if not all(isinstance(p,str) and p.strip() for p in phrases): raise ValueError('Empty phrase')
    if not all(finite(d) and d>0 for d in durations): raise ValueError('Invalid speech duration')
    needed=sum(durations)+gap*(len(durations)-1)+2*lead
    if needed>end-start+1e-6:
        raise ValueError(f'Narration overflow: needs {needed:.2f}s in {end-start:.2f}s slot; shorten script or explicitly retime')
    # Distribute available breathing room, never truncate/stretch speech silently.
    extra=(end-start-needed)/max(1,len(phrases)-1)
    at=start+lead; cues=[]
    for i,(text,duration) in enumerate(zip(phrases,durations)):
        cues.append({'text':text,'start':round(at,6),'end':round(at+duration,6)})
        at+=duration+gap+extra
    return cues


def synthesize(spec, root, model_dir, voice='zf_001', speed=1.1):
    from kokoro_onnx import Kokoro
    from misaki import zh
    import onnxruntime as ort
    root=Path(root);model_dir=Path(model_dir)
    paths=[model_dir/n for n in ('kokoro-v1.1-zh.onnx','voices-v1.1-zh.bin','config.json')]
    for p in paths:
        if not p.is_file():raise ValueError(f'Missing explicit local speech asset: {p.name}')
    if not finite(speed) or not .75<=speed<=1.4:raise ValueError('Speech speed must be 0.75..1.4')
    opts=ort.SessionOptions();opts.intra_op_num_threads=4
    session=ort.InferenceSession(str(paths[0]),sess_options=opts,providers=['CPUExecutionProvider'])
    k=Kokoro.from_session(session,str(paths[1]),vocab_config=str(paths[2]))
    g=zh.ZHG2P(version='1.1')
    out=root/'assets/narration';out.mkdir(parents=True,exist_ok=False)
    result=copy.deepcopy(spec);sr=24000
    mix=np.zeros(round(sr*spec['video']['duration']),dtype=np.float32);cues=[];records=[];errors=[]
    model_hashes={p.name:digest(p) for p in paths}
    cache=model_dir/'phrase-cache';cache.mkdir(exist_ok=True)
    for scene in spec['scenes']:
        phrases=scene.get('narration',[])
        if not phrases:raise ValueError(f'Missing narration in {scene["id"]}')
        arrays=[]
        for phrase in phrases:
            key=hashlib.sha256(canonical({'models':model_hashes,'voice':voice,'speed':speed,'text':phrase,'frontend':'misaki-fork-0.9.6','engine':'kokoro-onnx-0.6.1'}).encode()).hexdigest()
            cached=cache/(key+'.npy')
            if cached.exists():a=np.load(cached,allow_pickle=False)
            else:
                ph,_=g(phrase);a,rate=k.create(ph,voice=voice,speed=speed,is_phonemes=True)
                if rate!=sr:raise ValueError('Unexpected TTS sample rate')
                np.save(cached,a,allow_pickle=False)
            if a.ndim!=1 or not np.isfinite(a).all() or len(a)>sr*120:raise ValueError('Invalid cached speech')
            arrays.append(a)
        try:timed=schedule_phrases(phrases,scene['start'],scene['end'],[len(a)/sr for a in arrays])
        except ValueError as exc:
            errors.append(scene['id']+': '+str(exc));continue
        for i,(cue,a) in enumerate(zip(timed,arrays)):
            a=a.astype(np.float32);peak=max(.01,float(np.max(np.abs(a))));a=a/peak*.70
            at=round(cue['start']*sr);mix[at:at+len(a)]+=a
            cue['scene']=scene['id'];cues.append(cue)
        records.append({'scene':scene['id'],'durations':[len(a)/sr for a in arrays]})
        print('Narration',scene['id'],round(sum(len(a)/sr for a in arrays),2),'s',flush=True)
    if errors:
        (out/'preflight-errors.json').write_text(json.dumps(errors,indent=2))
        raise ValueError('; '.join(errors))
    voice_active=np.zeros(len(mix),dtype=bool)
    for cue in cues:voice_active[round(cue['start']*sr):round(cue['end']*sr)]=True
    # Original quiet percussion on declared BPM; envelope follows speech occupancy.
    bpm=spec.get('timing',{}).get('bpm',120)
    for i,at in enumerate(np.arange(0,spec['video']['duration'],60/bpm)):
        t=np.arange(int(sr*.14))/sr;hit=np.sin(2*np.pi*(72*t+5*(1-np.exp(-30*t))))*np.exp(-35*t)
        pos=round(at*sr);n=min(len(hit),len(mix)-pos)
        mix[pos:pos+n]+=hit[:n]*np.where(voice_active[pos:pos+n],.025,.065)
    peak=float(np.max(np.abs(mix)))
    if peak>.88:mix*=.88/peak
    path=out/'mix.wav'
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr);f.writeframes((mix*32767).astype('<i2').tobytes())
    metadata={'engine':'kokoro-onnx','model':'Kokoro-82M-v1.1-zh','voice':voice,'speed':speed,'source':'https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh','model_license':'Apache-2.0','model_hashes':model_hashes,'alignment':'separately synthesized phrase durations; no forced word alignment','phrases':cues,'scenes':records,'speech_seconds':sum(c['end']-c['start'] for c in cues)}
    (out/'timing.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    def ts(t):
        n=round(t*1000);return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'
    (out/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{ts(c["start"])} --> {ts(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')
    result['captions']=cues;result['narration_metadata']='assets/narration/timing.json'
    result['audio']={'mode':'file','path':'assets/narration/mix.wav'}
    result.setdefault('assets',[]).extend([{'path':f'assets/narration/{name}','source':'Original benchmark script; local Kokoro-82M-v1.1-zh synthesis; '+metadata['source'],'license':'Original script and percussion; model Apache-2.0; generated synthetic voice, not a voice clone'} for name in ['mix.wav','timing.json','captions.srt']])
    return result
