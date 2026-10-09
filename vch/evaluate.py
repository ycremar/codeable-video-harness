"""Explicit measurement semantics; unknown/missing is never pass."""
from __future__ import annotations
import json
import math
import shutil
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from . import signals
from .core import normalized_hits
from .pipeline import audit, command


METRIC_TYPES = {
    'duration_s':'hard','width_px':'hard','height_px':'hard','fps':'hard','audio_present':'hard',
    'audio_peak_dbfs':'hard','determinism_mismatches':'hard','decode_mae':'proxy',
    'black_fraction':'proxy','text_present':'proxy','text_absent':'proxy',
    'minimum_text_size_px':'proxy','minimum_contrast':'proxy','safe_area_violations':'proxy',
    'minimum_text_hold_s':'proxy','beat_cut_error_ms':'proxy','motion_fraction':'proxy',
    'ocr_contains':'proxy',
    'integrated_loudness_lufs':'hard','true_peak_dbtp':'hard','encoded_frame_count':'hard',
    'frame_timestamp_jitter_ms':'hard','text_overlap_violations':'proxy','max_static_hold_s':'proxy',
    'single_frame_pops':'proxy','loop_seam_ratio':'proxy','audio_hit_sync_ms':'proxy'
}


SETTLED_OPACITY_FRACTION = .95


def _settled_text(elements, fraction):
    """Split text observations into settled ones and fade transitions (opacity < fraction × that id's max)."""
    if type(fraction) not in (int, float) or not 0 < fraction <= 1:
        raise ValueError('settled_fraction must be in (0, 1]')
    peak = {}
    for e in elements:
        peak[e['id']] = max(peak.get(e['id'], 0), e.get('opacity', 1))
    settled = [e for e in elements if e.get('opacity', 1) >= fraction*peak[e['id']]]
    return settled, len(elements)-len(settled)


def _decoded(evidence, key):
    if key not in evidence:
        raise ValueError(f'Missing decoded evidence "{key}"; re-render with this harness version')
    return evidence[key]


def _loudness(metric, evidence):
    analysis = _decoded(evidence, 'audio_analysis')
    key = 'integrated_lufs' if metric == 'integrated_loudness_lufs' else 'true_peak_dbtp'
    if analysis.get(key) is None:
        raise ValueError('Audio too short/silent for a BS.1770 measurement')
    if metric == 'integrated_loudness_lufs':
        return analysis[key], 'ffmpeg ebur128 BS.1770 integrated loudness of the encoded (AAC) audio; not perceived mix quality'
    return analysis[key], 'ffmpeg ebur128 4x-oversampled true peak of the encoded audio; decoder/platform resampling can differ'


def _frame_timing(metric, evidence):
    timing = _decoded(evidence, 'frame_timing')
    if metric == 'encoded_frame_count':
        return timing['frames'], 'ffprobe packet count of the encoded video stream'
    return timing['max_jitter_ms'], 'max |pts - (pts0 + i/fps)| over encoded packets; constant-rate grid check only'


def _text_overlaps(params, trace):
    min_fraction = params.get('min_fraction', .25)
    if type(min_fraction) not in (int, float) or not 0 < min_fraction <= 1:
        raise ValueError('min_fraction must be in (0, 1]')
    ignore = set(params.get('ignore_ids', []))
    if not any(e.get('type') == 'text' for f in trace for e in f['elements']):
        raise ValueError('No text telemetry')
    count = sum(len(signals.overlap_pairs(f['elements'], min_fraction=min_fraction, ignore=ignore)) for f in trace)
    return count, f'frame×pair count of distinct text boxes intersecting by ≥{min_fraction:.0%} of the smaller box; layered designs may intend overlap'


def _motion_metric(metric, params, spec, evidence):
    motion = _decoded(evidence, 'decoded_motion'); fps = spec['video']['fps']
    exclude = signals.check_windows(params.get('exclude'))
    note = f"; excluded windows {exclude}" if exclude else ''
    if metric == 'max_static_hold_s':
        delta = params.get('still_delta', signals.DEFAULT_STILL_DELTA)
        hold, start = signals.longest_still_hold(motion['diff'], fps=fps, still_delta=delta, exclude=exclude)
        where = f' starting {start:.3f}s' if start is not None else ''
        return hold, f'longest decoded run with mean luma change <{delta}/255 per frame{where}{note}; slow drifts count as still'
    if metric == 'single_frame_pops':
        pops = signals.single_frame_pops(motion['diff'], motion['bridge'], fps=fps,
                                         ratio=params.get('ratio', signals.DEFAULT_POP_RATIO),
                                         floor=params.get('floor', signals.DEFAULT_POP_FLOOR), exclude=exclude)
        return len(pops), f'decoded frames unlike both neighbours (one-frame flashes/jumps) at {pops[:8]}{note}; intentional flashes count'
    ratio = signals.loop_seam_ratio(motion, fps=fps, still_delta=params.get('still_delta', signals.DEFAULT_STILL_DELTA))
    return ratio, 'last→first decoded-frame change relative to neighbouring frame steps; 0 = identical frames'


def _hit_sync(spec, evidence):
    hits = [h['t'] for h in normalized_hits(spec.get('timing', {}))]
    if not hits:
        raise ValueError('No declared timing.hits')
    onsets = _decoded(evidence, 'audio_analysis').get('onsets', [])
    if not onsets:
        raise ValueError('No detectable audio onsets')
    errors = [min(abs(o-h) for o in onsets)*1000 for h in hits]
    worst = max(range(len(hits)), key=errors.__getitem__)
    return errors[worst], f'max distance from {len(hits)} declared hits to detected transient peaks (worst at {hits[worst]:.3f}s); onsets are not attributed to sources'


def measure(metric, params, spec, evidence, trace, out):
    if metric in ('integrated_loudness_lufs', 'true_peak_dbtp'):
        return _loudness(metric, evidence)
    if metric in ('encoded_frame_count', 'frame_timestamp_jitter_ms'):
        return _frame_timing(metric, evidence)
    if metric == 'text_overlap_violations':
        return _text_overlaps(params, trace)
    if metric in ('max_static_hold_s', 'single_frame_pops', 'loop_seam_ratio'):
        return _motion_metric(metric, params, spec, evidence)
    if metric == 'audio_hit_sync_ms':
        return _hit_sync(spec, evidence)
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
        # text-group = visible text of one data-vch-id element whose words are separate nodes.
        readable=[e for f in trace for e in f['elements'] if e.get('type') in ('text','text-group')]
        texts='\n'.join(e['text'] for e in readable)
        needles=params['strings']
        if not needles: raise ValueError('Empty text query')
        found=[q in texts for q in needles]
        return (all(found) if metric=='text_present' else not any(found)), 'all-frame instrumented text trace; not OCR, not proof against occlusion'
    if metric == 'minimum_text_size_px':
        if not elements: raise ValueError('No text telemetry')
        return min(e['size'] for e in elements), 'instrumented font size in output pixels; not perceived legibility'
    if metric == 'minimum_contrast':
        if not elements: raise ValueError('No text telemetry')
        settled,transitional=_settled_text(elements,params.get('settled_fraction',SETTLED_OPACITY_FRACTION))
        known=[e['contrast'] for e in settled if e.get('contrast') is not None]
        unknown=len(settled)-len(known)
        if unknown and not params.get('allow_unknown'):
            raise ValueError(f'{unknown} text observations have unknown contrast (e.g. transparent or gradient fill); set allow_unknown only if that is acceptable')
        if not known: raise ValueError('No text observation has a measurable contrast')
        source='declared or rendered-pixel text/background contrast; overlapping artwork not modeled'
        if transitional: source+=f'; {transitional} fade-in/out observations below the element\'s settled opacity excluded'
        return min(known), source+(f'; {unknown} unknown observations excluded by contract' if unknown else '')
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
