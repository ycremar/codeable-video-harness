from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import load_contract, SceneRenderer, source_manifest
from .pipeline import render, audit
from .evaluate import evaluate, review_template, METRIC_TYPES
from .backends import create_renderer
from .tools import still_times, render_stills, storyboard_markdown, profile_media, summary_line, compare_profiles


def main():
    parser=argparse.ArgumentParser(description='Evidence-first code-video harness')
    sub=parser.add_subparsers(dest='cmd',required=True)
    for name in ('validate','packet'):
        p=sub.add_parser(name); p.add_argument('contract')
    p=sub.add_parser('metrics')
    p=sub.add_parser('run'); p.add_argument('contract'); p.add_argument('--out',required=True);p.add_argument('--trust-scene-code',action='store_true')
    p=sub.add_parser('still');p.add_argument('contract');p.add_argument('--time',type=float,required=True);p.add_argument('--out',required=True);p.add_argument('--trust-scene-code',action='store_true')
    p=sub.add_parser('stills',help='Render preview stills + sheet before a full render')
    p.add_argument('contract');p.add_argument('--out',required=True);p.add_argument('--times',help='Comma-separated seconds')
    p.add_argument('--beats',action='store_true',help='One still per beat of timing.bpm');p.add_argument('--trust-scene-code',action='store_true')
    p.add_argument('--motion',action='store_true',help='Also report each still\'s change to the next frame (dead-time proxy)')
    p=sub.add_parser('storyboard',help='Print a timestamped storyboard table from a contract');p.add_argument('contract')
    p=sub.add_parser('profile',help='Measure pacing/sound of a video or audio file (reference or candidate)')
    p.add_argument('media');p.add_argument('--out',required=True);p.add_argument('--every',type=float,default=1.0);p.add_argument('--max-fps',type=float,default=30.0)
    p=sub.add_parser('profile-compare',help='Side-by-side proxies from two profile.json files');p.add_argument('first');p.add_argument('second')
    p=sub.add_parser('evaluate');p.add_argument('run');p.add_argument('--review');p.add_argument('--project-root')
    p=sub.add_parser('audit');p.add_argument('run');p.add_argument('--project-root')
    p=sub.add_parser('review-template');p.add_argument('run');p.add_argument('--out',required=True)
    p=sub.add_parser('compare');p.add_argument('first');p.add_argument('second')
    p=sub.add_parser('produce')
    prompt=p.add_mutually_exclusive_group(required=True)
    prompt.add_argument('--prompt');prompt.add_argument('--prompt-file')
    p.add_argument('--constraints',required=True);p.add_argument('--out',required=True)
    author=p.add_mutually_exclusive_group()
    author.add_argument('--candidate-file');author.add_argument('--author-command',help='JSON argv array; reads request from stdin, returns JSON')
    p.add_argument('--speech-model-dir');p.add_argument('--trust-scene-code',action='store_true')
    p.add_argument('--max-attempts',type=int,default=3);p.add_argument('--author-timeout',type=int,default=300)
    args=parser.parse_args()
    try:
        if args.cmd=='produce':
            from .production import produce
            result=produce(args.prompt or Path(args.prompt_file).read_text(),json.loads(Path(args.constraints).read_text()),args.out,
                candidate_file=args.candidate_file,author_command=json.loads(args.author_command) if args.author_command else None,
                model_dir=args.speech_model_dir,trust_code=args.trust_scene_code,max_attempts=args.max_attempts,author_timeout=args.author_timeout)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            raise SystemExit(0 if result['state']=='accepted_by_contract' else 3 if result['state']=='needs_review' else 2)
        if args.cmd=='metrics':
            print(json.dumps(METRIC_TYPES,indent=2));return
        if args.cmd=='profile-compare':
            first,second=(json.loads(Path(x).read_text()) for x in (args.first,args.second))
            print(compare_profiles(first,second),end='');return
        if args.cmd=='profile':
            print(json.dumps(summary_line(profile_media(Path(args.media),Path(args.out),every=args.every,max_fps=args.max_fps)),ensure_ascii=False,indent=2));return
        if args.cmd in ('validate','packet','run','still','stills','storyboard'):
            spec,root=load_contract(args.contract)
        if args.cmd=='validate':
            print('Contract structurally valid; unknown metrics remain unmeasured at evaluation.');return
        if args.cmd=='packet':
            packet={'task':'Author or repair code-rendered video. Do not copy the reference style.',
                    'contract':spec,'project_root':str(root),'source':source_manifest(root,spec),
                    'read_first':['AGENTS.md','docs/AUTHORING.md','docs/MEASUREMENT.md'],
                    'write_scope':['scenes/','compositions/ (html backend)','assets/ (rights documented)'],
                    'protected':['examples/*.json requirements/thresholds unless owner approves changes','vch/evaluate.py','tests/'],
                    'loop':['Read requirements and sources','Map every requirement to evidence; flag undefined criteria',
                            'Propose storyboard and timing','Implement pure render(t,seed)',
                            'Render stills (vch stills, or --beats) and LOOK at them','Run full render/evaluator',
                            'Read report.json and decoded contact sheet','Repair exact failed requirements; max 3 attempts',
                            'Leave human review pending; record model ID only if runtime reports it'],
                    'output':['changed files','commands actually executed','requirement IDs addressed','remaining failures/unmeasured','real artifact paths'],
                    'stop':['No silent acceptance-threshold changes','No paid API calls without permission','No public upload','No claim of universal quality from proxy scores']}
            print(json.dumps(packet,ensure_ascii=False,indent=2));return
        if args.cmd=='storyboard':
            print(storyboard_markdown(spec),end='');return
        if args.cmd=='stills':
            times=[float(x) for x in args.times.split(',')] if args.times else None
            summary=render_stills(spec,root,Path(args.out),times=still_times(spec,times=times,beats=args.beats),trust_code=args.trust_scene_code,motion=args.motion)
            print(json.dumps({'out':args.out,'stills':len(summary['stills']),'warnings':summary['warnings']},ensure_ascii=False,indent=2));return
        if args.cmd=='still':
            path=Path(args.out)
            if path.exists(): raise FileExistsError('Refuse to overwrite an existing still')
            path.parent.mkdir(parents=True,exist_ok=True)
            renderer=create_renderer(spec,root,args.trust_scene_code)
            try: renderer.sampled(args.time).image.save(path)
            finally:
                if hasattr(renderer,'close'): renderer.close()
            print(path);return
        if args.cmd=='run':
            out=render(spec,root,args.out,args.trust_scene_code)
            result=evaluate(out)
            (out/'review.template.json').write_text(json.dumps(review_template(out),ensure_ascii=False,indent=2))
            print(json.dumps({'run':str(out),'state':result['state'],'coverage':result['coverage']}))
            # 2 = blocked, 3 = needs a review, 0 = accepted; no misleading green exit.
            raise SystemExit(0 if result['accepted'] else (3 if result['state']=='needs_review' else 2))
        if args.cmd=='evaluate':
            result=evaluate(args.run,args.review,args.project_root)
            print(json.dumps({'state':result['state'],'coverage':result['coverage']}))
            raise SystemExit(0 if result['accepted'] else (3 if result['state']=='needs_review' else 2))
        if args.cmd=='review-template':
            path=Path(args.out)
            if path.exists(): raise FileExistsError('Refuse to overwrite review decisions')
            path.write_text(json.dumps(review_template(args.run),ensure_ascii=False,indent=2));return
        if args.cmd=='audit':
            audit(args.run,args.project_root);print('Artifact integrity verified (not a cryptographic signature).');return
        if args.cmd=='compare':
            for p in (args.first,args.second): audit(p)
            a=json.loads((Path(args.first)/'report.json').read_text());b=json.loads((Path(args.second)/'report.json').read_text())
            sa=json.loads((Path(args.first)/'contract.json').read_text());sb=json.loads((Path(args.second)/'contract.json').read_text())
            if sa['requirements']!=sb['requirements']:
                raise ValueError('Requirements changed: comparison is not a valid quality improvement claim')
            amap={x['id']:x for x in a['requirements']}
            print(json.dumps([{'id':x['id'],'before':amap[x['id']]['status'],'after':x['status'],
                               'before_value':amap[x['id']].get('value'),'after_value':x.get('value')} for x in b['requirements']],ensure_ascii=False,indent=2))
    except (ValueError,KeyError,PermissionError,FileExistsError) as e:
        parser.exit(2,f'ERROR: {e}\n')
