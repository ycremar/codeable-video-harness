"""One free-form prompt, including initial contract extraction, then production.

The first contract is an AI proposal frozen for this run, not user-approved truth.
PROMPT-FIDELITY stays human-reviewed; a model cannot certify its own extraction.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vch.production import author_packet, invoke_author, produce

FIDELITY={'id':'PROMPT-FIDELITY','description':'The extracted contract and produced artifact faithfully satisfy the original user prompt, without omitted requirements.',
          'kind':'human','rubric':'Compare the original prompt, frozen contract and actual MP4. Identify missing or weakened requirements, unsupported claims, and style/delivery gaps with timestamps. Model self-review cannot approve this criterion.'}


def run(prompt,out,command,model_dir=None,trust_code=False,max_attempts=3):
    if not prompt.strip():raise ValueError('Prompt cannot be empty')
    if not 1<=max_attempts<=3:raise ValueError('Attempt cap is 1..3')
    if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):raise ValueError('Author command must be a nonempty argv array')
    if not trust_code:raise PermissionError('Trusted author/render worker opt-in required')
    out=Path(out).resolve()
    if out.exists():raise FileExistsError('Use a new immutable output directory')
    out.mkdir(parents=True);(out/'prompt.txt').write_text(prompt)
    request=author_packet(prompt,{'requirements':[]})
    request['phase']='plan'
    request['planning_instruction']='Extract the explicit user requirements into a complete version-1 contract. Choose reasonable documented assumptions for unspecified production details. Return contract, optional scene files, and assumptions. This initial contract is a proposal; after this response the harness freezes its technical fields and requirements. Do not claim fidelity is approved. Use only registered metrics from the provided list; subjective intent needs human rubrics.'
    from vch.evaluate import METRIC_TYPES
    request['registered_metrics']=METRIC_TYPES
    (out/'planning-request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2))
    try:
        response=invoke_author(command,request,300)
        spec=response['contract']
        if not isinstance(spec.get('requirements'),list) or not spec['requirements']:raise ValueError('Planning response has no requirements')
        if any(r.get('id')=='PROMPT-FIDELITY' for r in spec['requirements']):raise ValueError('Reserved requirement ID')
        spec['requirements'].append(FIDELITY.copy())
        constraints={k:spec[k] for k in ['video','requirements']}
        constraints['backend']=spec.get('backend','pillow')
        candidate=out/'planning-response.json';candidate.write_text(json.dumps(response,ensure_ascii=False,indent=2))
        (out/'frozen-constraints.json').write_text(json.dumps(constraints,ensure_ascii=False,indent=2))
        bridge=[sys.executable,str(Path(__file__).resolve().parents[1]/'adapters/planned_author.py'),'--first-response',str(candidate),'--upstream-command',json.dumps(command)]
        result=produce(prompt,constraints,out/'production',author_command=bridge,model_dir=model_dir,trust_code=True,max_attempts=max_attempts)
        result['contract_origin']='AI-proposed, frozen after initial extraction; PROMPT-FIDELITY remains human review'
        (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
    except Exception as exc:
        (out/'result.json').write_text(json.dumps({'state':'blocked','error':str(exc)},indent=2));raise


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prompt');g.add_argument('--prompt-file')
    p.add_argument('--out',required=True);p.add_argument('--author-command',required=True);p.add_argument('--speech-model-dir');p.add_argument('--trust-scene-code',action='store_true');p.add_argument('--max-attempts',type=int,default=3)
    args=p.parse_args()
    try:r=run(args.prompt or Path(args.prompt_file).read_text(),args.out,json.loads(args.author_command),args.speech_model_dir,args.trust_scene_code,args.max_attempts)
    except (ValueError,PermissionError,OSError) as exc:p.exit(2,str(exc)+'\n')
    print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(3 if r['state']=='needs_review' else 0 if r['state']=='accepted_by_contract' else 2)
if __name__=='__main__':main()
