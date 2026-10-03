from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import load_contract, SceneRenderer, source_manifest
from .pipeline import render, audit
from .evaluate import evaluate, review_template, METRIC_TYPES


def main():
    parser=argparse.ArgumentParser(description='Evidence-first code-video harness')
    sub=parser.add_subparsers(dest='cmd',required=True)
    for name in ('validate','packet'):
        p=sub.add_parser(name); p.add_argument('contract')
    p=sub.add_parser('metrics')
    p=sub.add_parser('run'); p.add_argument('contract'); p.add_argument('--out',required=True);p.add_argument('--trust-scene-code',action='store_true')
    p=sub.add_parser('still');p.add_argument('contract');p.add_argument('--time',type=float,required=True);p.add_argument('--out',required=True);p.add_argument('--trust-scene-code',action='store_true')
    p=sub.add_parser('evaluate');p.add_argument('run');p.add_argument('--review');p.add_argument('--project-root')
    p=sub.add_parser('audit');p.add_argument('run');p.add_argument('--project-root')
    p=sub.add_parser('review-template');p.add_argument('run');p.add_argument('--out',required=True)
    p=sub.add_parser('compare');p.add_argument('first');p.add_argument('second')
    args=parser.parse_args()
    try:
        if args.cmd=='metrics':
            print(json.dumps(METRIC_TYPES,indent=2));return
        if args.cmd in ('validate','packet','run','still'):
            spec,root=load_contract(args.contract)
        if args.cmd=='validate':
            print('Contract structurally valid; unknown metrics remain unmeasured at evaluation.');return
        if args.cmd=='packet':
            packet={'task':'Author or repair code-rendered video. Do not copy the reference style.',
                    'contract':spec,'project_root':str(root),'source':source_manifest(root,spec),
                    'read_first':['AGENTS.md','docs/AUTHORING.md','docs/MEASUREMENT.md'],
                    'write_scope':['scenes/','assets/ (rights documented)'],
                    'protected':['examples/*.json requirements/thresholds unless owner approves changes','vch/evaluate.py','tests/'],
                    'loop':['Read requirements and sources','Map every requirement to evidence; flag undefined criteria',
                            'Propose storyboard and timing','Implement pure render(t,seed)',
                            'Render boundary/midpoint stills and LOOK at them','Run full render/evaluator',
                            'Read report.json and decoded contact sheet','Repair exact failed requirements; max 3 attempts',
                            'Leave human review pending; record model ID only if runtime reports it'],
                    'output':['changed files','commands actually executed','requirement IDs addressed','remaining failures/unmeasured','real artifact paths'],
                    'stop':['No silent acceptance-threshold changes','No paid API calls without permission','No public upload','No claim of universal quality from proxy scores']}
            print(json.dumps(packet,ensure_ascii=False,indent=2));return
        if args.cmd=='still':
            path=Path(args.out)
            if path.exists(): raise FileExistsError('Refuse to overwrite an existing still')
            path.parent.mkdir(parents=True,exist_ok=True)
            SceneRenderer(spec,root,args.trust_scene_code).sampled(args.time).image.save(path)
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
