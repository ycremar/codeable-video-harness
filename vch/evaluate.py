"""Explicit measurement semantics; unknown/missing is never pass."""
from __future__ import annotations
import json
import math
import shutil
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from .pipeline import audit, command


METRIC_TYPES = {
    'duration_s':'hard','width_px':'hard','height_px':'hard','fps':'hard','audio_present':'hard',
    'audio_peak_dbfs':'hard','determinism_mismatches':'hard','decode_mae':'proxy',
    'black_fraction':'proxy','text_present':'proxy','text_absent':'proxy',
    'minimum_text_size_px':'proxy','minimum_contrast':'proxy','safe_area_violations':'proxy',
    'minimum_text_hold_s':'proxy','beat_cut_error_ms':'proxy','motion_fraction':'proxy',
    'ocr_contains':'proxy'
}


def measure(metric, params, spec, evidence, trace, out):
    v = next(x for x in evidence['probe']['streams'] if x['codec_type']=='video')
    if metric == 'duration_s': return float(v['duration']), 'ffprobe: encoded video stream'
    if metric in ('width_px','height_px'): return v[metric.split('_')[0]], 'ffprobe: encoded video stream'
    if metric == 'fps':
        a,b = v['avg_frame_rate'].split('/'); return int(a)/int(b), 'ffprobe: encoded video stream'
    if metric == 'audio_present': return any(x['codec_type']=='audio' for x in evidence['probe']['streams']), 'ffprobe: stream inventory'
    if metric == 'audio_peak_dbfs':
        if not any(x['codec_type']=='audio' for x in evidence['probe']['streams']):
            raise ValueError('No audio stream to measure')
        data=command(['ffmpeg','-v','error','-i',str(out/'video.mp4'),'-vn','-f','f32le','-acodec','pcm_f32le','-']).stdout
        peak=float(np.max(np.abs(np.frombuffer(data,dtype='<f4'))))
        return 20*math.log10(max(peak,1e-12)), 'decoded PCM sample peak, not true-peak or loudness'
    if metric == 'determinism_mismatches': return len(evidence['determinism_mismatches']), 'raw sampled frames, reverse/shuffled seeks; finite evidence only'
    if metric == 'decode_mae': return max(x['decode_mae'] for x in evidence['samples']), 'sampled encoded pixels vs renderer pixels; 0..255 MAE'
    if metric == 'black_fraction': return max(x['black_fraction'] for x in evidence['samples']), 'sampled decoded pixels with RGB max <12; deliberate black also counts'
    elements=[e for f in trace for e in f['elements'] if e.get('type')=='text']
    if metric in ('text_present','text_absent'):
        if not elements: raise ValueError('No text telemetry')
        texts='\n'.join(e['text'] for e in elements)
        needles=params['strings']
        if not needles: raise ValueError('Empty text query')
        found=[q in texts for q in needles]
        return (all(found) if metric=='text_present' else not any(found)), 'all-frame instrumented text trace; not OCR, not proof against occlusion'
    if metric == 'minimum_text_size_px':
        if not elements: raise ValueError('No text telemetry')
        return min(e['size'] for e in elements), 'instrumented font size in output pixels; not perceived legibility'
    if metric == 'minimum_contrast':
        if not elements: raise ValueError('No text telemetry')
        return min(e['contrast'] for e in elements), 'declared text/background contrast; overlapping artwork not modeled'
    if metric == 'safe_area_violations':
        if not elements: raise ValueError('No text telemetry')
        l,t,r,b=params.get('margins',[0,0,0,0]); w,h=spec['video']['width'],spec['video']['height']
        return sum(e['bbox'][0]<l or e['bbox'][1]<t or e['bbox'][2]>w-r or e['bbox'][3]>h-b for e in elements), 'all-frame rasterizer text bounds; assumes telemetry is honest'
    if metric == 'minimum_text_hold_s':
        requested=params.get('ids',[])
        if not requested: raise ValueError('Specify text element IDs to measure')
        best={k:0 for k in requested}; streak={k:0 for k in requested}; previous={}
        for frame in trace:
            seen={e['id']:e['text'] for e in frame['elements'] if e['id'] in requested}
            for key in requested:
                streak[key]=streak[key]+1 if key in seen and previous.get(key)==seen[key] else (1 if key in seen else 0)
                best[key]=max(best[key],streak[key])
            previous=seen
        if any(x==0 for x in best.values()): raise ValueError('Requested text ID never rendered')
        return min(best.values())/spec['video']['fps'], 'longest continuous identical-text interval per requested ID; actual visibility requires review'
    if metric == 'beat_cut_error_ms':
        timing=spec.get('timing',{}); bpm=timing.get('bpm')
        if not bpm: raise ValueError('No beat grid')
        offset=timing.get('beat_offset',0); step=60/bpm
        cuts=[x['start'] for x in spec['scenes'][1:]]
        if not cuts: raise ValueError('No cuts')
        return max(abs((t-offset)-round((t-offset)/step)*step)*1000 for t in cuts), 'declared scene cuts vs declared beat grid; not detected audio onsets'
    if metric == 'motion_fraction':
        samples=evidence['samples']; diffs=[]
        threshold=params.get('pixel_delta',8)
        for a,b in zip(samples,samples[1:]):
            aa=np.asarray(Image.open(out/a['file'])).astype(float); bb=np.asarray(Image.open(out/b['file'])).astype(float)
            diffs.append(float(np.mean(np.max(abs(aa-bb),axis=2)>threshold)))
        if not diffs: raise ValueError('Need multiple decoded frames')
        return float(np.mean(diffs)), 'fraction changed between sampled decoded frames; includes cuts, not an excitement score'
    if metric == 'ocr_contains':
        if not shutil.which('tesseract'): raise ValueError('Tesseract unavailable')
        if not params.get('strings'): raise ValueError('Empty OCR query')
        lang=params.get('lang','eng'); all_text=[]
        for sample in evidence['samples']:
            result=command(['tesseract',str(out/sample['file']),'stdout','-l',lang,'--psm','11'])
            all_text.append(result.stdout.decode(errors='replace'))
        text='\n'.join(all_text).casefold()
        return all(q.casefold() in text for q in params['strings']), 'Tesseract on sampled decoded pixels; OCR can miss/stutter; supplemental evidence'
    raise KeyError(f'No evaluator registered: {metric}')


def compare(value, op, target):
    if isinstance(value,(int,float)) and not isinstance(value,bool) and not math.isfinite(value):
        raise ValueError('Non-finite metric is not a score')
    if type(target) in (int,float) and not math.isfinite(target):
        raise ValueError('Non-finite target is not an acceptance threshold')
    if op=='eq': return type(value)==type(target) and value==target if isinstance(target,bool) or isinstance(value,bool) else value==target
    if type(value) not in (int,float) or type(target) not in (int,float):
        raise ValueError('Ordered comparison requires numbers')
    if op=='le': return value<=target
    if op=='ge': return value>=target
    raise ValueError('Unknown comparison')


def evaluate(out, review_path=None, root=None):
    out=Path(out); manifest=audit(out,root)
    spec=json.loads((out/'contract.json').read_text()); evidence=json.loads((out/'evidence.json').read_text())
    trace=[json.loads(x) for x in (out/'trace.jsonl').read_text().splitlines()]
    review=json.loads(Path(review_path).read_text()) if review_path else {}
    review_valid=review.get('binding')==manifest['review_binding']
    rows=[]
    for req in spec['requirements']:
        row={'id':req['id'],'description':req['description'],'kind':req['kind'],'status':'unmeasured'}
        if req['kind']=='human':
            r=review.get('decisions',{}).get(req['id'])
            if r and review_valid and review.get('reviewer') and r.get('reason') and r.get('evidence'):
                if r.get('decision') in ('pass','fail'):
                    row.update(status=r['decision'],reason=r['reason'],evidence=r['evidence'],reviewer=review['reviewer'])
            else:
                row['reason']='No completed, artifact-bound review (or review is stale)'
        else:
            metric=req['metric']; row.update(metric=metric,target=req['target'],op=req['op'])
            try:
                kind=METRIC_TYPES.get(metric)
                if kind is None: raise KeyError(f'No evaluator registered: {metric}')
                if req['kind']=='hard' and kind=='proxy':
                    raise ValueError('This metric is a proxy; cannot relabel as objective hard evidence')
                value,source=measure(metric,req.get('params',{}),spec,evidence,trace,out)
                row.update(value=value,evidence=source,status='pass' if compare(value,req['op'],req['target']) else 'fail')
            except (KeyError,ValueError,TypeError,IndexError,OSError,subprocess.SubprocessError) as e:
                row['reason']=str(e)
        rows.append(row)
    total=len(rows); measured=sum(x['status']!='unmeasured' for x in rows)
    machine=[x for x in rows if x['kind']!='human']; humans=[x for x in rows if x['kind']=='human']
    machine_ok=all(x['status']=='pass' for x in machine)
    all_ok=machine_ok and all(x['status']=='pass' for x in humans)
    review_failed=any(x['status']=='fail' for x in humans)
    result={'binding':manifest['review_binding'],'coverage':{'total':total,'measured':measured,'ratio':measured/total},
            'machine_ok':machine_ok,'accepted':all_ok,
            'state':'accepted_by_contract' if all_ok else ('needs_review' if machine_ok and not review_failed else 'blocked'),
            'requirements':rows,'warning':'Acceptance applies only to this contract. No universal aesthetic score. Human review is an attestation, not authenticated identity.'}
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    lines=['# Requirement evaluation',f"State: **{result['state']}** · Coverage: {measured}/{total}",'',
           '| ID | Type | Result | Observed | Evidence / limitation |','|---|---|---|---|---|']
    for x in rows:
        clean=lambda y:str(y).replace('|','/').replace('\n',' ')
        lines.append('| '+' | '.join(map(clean,[x['id'],x['kind'],x['status'],x.get('value','—'),x.get('evidence',x.get('reason',''))]))+' |')
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    return result


def review_template(out):
    out=Path(out); m=audit(out); spec=json.loads((out/'contract.json').read_text())
    return {'binding':m['review_binding'],'reviewer':'',
            'decisions':{r['id']:{'decision':'pending','reason':'','evidence':[],'rubric':r['rubric']} for r in spec['requirements'] if r['kind']=='human'}}
