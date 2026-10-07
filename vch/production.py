"""Single user brief -> author -> frozen contract -> render -> repair.

A configured author command is the model boundary. Candidate replay is explicitly
labelled and must never be reported as an independent live-model generation test.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from .core import canonical, contained, validate, digest
from .pipeline import render
from .evaluate import evaluate, review_template


# Authors may write code and markup; media files carry rights and must arrive as declared assets.
COMPOSITION_TEXT_SUFFIXES = {'.html', '.js', '.mjs', '.css', '.json', '.svg', '.glsl', '.txt'}


def writable(rel):
    """True for author-writable paths: scenes/*.py or text files under compositions/."""
    if rel.is_absolute() or not rel.parts or any(part in ('..', '') or part.startswith('.') for part in rel.parts):
        return False
    if rel.parts[0] == 'scenes':
        return rel.suffix == '.py'
    return rel.parts[0] == 'compositions' and len(rel.parts) > 2 and rel.suffix.lower() in COMPOSITION_TEXT_SUFFIXES


def frozen_check(spec, constraints):
    if spec.get('requirements') != constraints['requirements']:
        raise ValueError('Author changed frozen requirements or thresholds')
    for field,value in constraints.get('video',{}).items():
        if spec.get('video',{}).get(field)!=value:raise ValueError(f'Author changed frozen video.{field}')
    if 'backend' in constraints and spec.get('backend','pillow')!=constraints['backend']:
        raise ValueError('Author changed required backend')


def author_packet(prompt, constraints, feedback=None):
    root=Path(__file__).resolve().parents[1]
    return {'protocol':'vch-author-v1','prompt':prompt,'constraints':constraints,
            'instructions':(root/'docs/SINGLE_PROMPT.md').read_text(),
            'contract_example':json.loads((root/'examples/explainer.json').read_text()),
            'response_schema':{'contract':'Complete version-1 contract; preserve constraints.requirements and video exactly',
                               'files':'Optional object of relative paths -> UTF-8 source: scenes/*.py or compositions/<name>/** text files (.html .js .css .json .svg .glsl); no other writes accepted',
                               'author':'Optional self-reported provenance, not verified model identity'},
            'feedback':feedback,'rules':['Return a single JSON object, no Markdown fences','Do not change frozen requirements',
                                       'Human reviews remain pending','Do not invoke paid services from scene code']}


def invoke_author(command, packet, timeout):
    if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):
        raise ValueError('Author command must be a nonempty JSON argv array (never a shell string)')
    result=subprocess.run(command,input=canonical(packet),text=True,capture_output=True,timeout=timeout)
    if result.returncode:raise ValueError(f'Author command failed with exit {result.returncode}; no fallback generation claimed')
    try:return json.loads(result.stdout)
    except json.JSONDecodeError as exc:raise ValueError('Author did not return a JSON object') from exc


def produce(prompt, constraints, out, candidate_file=None, author_command=None, model_dir=None,
            trust_code=False,max_attempts=3,author_timeout=300):
    if not prompt.strip():raise ValueError('Prompt cannot be empty')
    if candidate_file and author_command:raise ValueError('Choose candidate replay OR live author, not both')
    if not 1<=max_attempts<=3:raise ValueError('Attempt cap is 1..3')
    out=Path(out).resolve()
    if out.exists():raise FileExistsError('Production sessions are immutable; use a new output directory')
    out.mkdir(parents=True)
    (out/'prompt.txt').write_text(prompt)
    (out/'constraints.json').write_text(json.dumps(constraints,ensure_ascii=False,indent=2))
    packet=author_packet(prompt,constraints)
    (out/'author-request.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2))
    mode='candidate-replay' if candidate_file else 'live-author-command' if author_command else 'agent-workspace-packet'
    session={'mode':mode,'prompt_sha256':digest(out/'prompt.txt'),'constraints_sha256':digest(out/'constraints.json'),
             'attempts':[],'model_identity':'not verified by harness','state':'needs_author'}
    def save(): (out/'session.json').write_text(json.dumps(session,ensure_ascii=False,indent=2))
    save()
    if not candidate_file and not author_command:return session
    if not trust_code:raise PermissionError('Review code/author command and opt in with --trust-scene-code')
    base=Path(__file__).resolve().parents[1];feedback=None
    for i in range(1,(1 if candidate_file else max_attempts)+1):
        attempt=out/f'attempt-{i:02}';attempt.mkdir();project=attempt/'project';project.mkdir()
        response=json.loads(Path(candidate_file).read_text()) if candidate_file else invoke_author(author_command,author_packet(prompt,constraints,feedback),author_timeout)
        (attempt/'author-response.json').write_text(json.dumps(response,ensure_ascii=False,indent=2))
        record={'attempt':i,'response_sha256':digest(attempt/'author-response.json')}
        session['attempts'].append(record)
        try:
            spec=response['contract'];frozen_check(spec,constraints)
            shutil.copytree(base/'assets/fonts',project/'assets/fonts')
            shutil.copytree(base/'scenes',project/'scenes',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(base/'compositions',project/'compositions')
            for path,content in response.get('files',{}).items():
                rel=Path(path)
                if not writable(rel):raise ValueError('Author writes restricted to scenes/*.py and compositions/** text files (no media without rights records)')
                dest=contained(project,path);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content)
            validate(spec,project)
            if any(s.get('narration') for s in spec['scenes']):
                if not model_dir:raise ValueError('Narrated candidate requires explicit local --speech-model-dir')
                from .narration import synthesize
                spec=synthesize(spec,project,model_dir,voice=spec.get('speech',{}).get('voice','zf_001'),speed=spec.get('speech',{}).get('speed',1.1))
            frozen_check(spec,constraints);validate(spec,project)
            (project/'contract.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2))
            run=render(spec,project,project/'runs/render',True)
            report=evaluate(run)
            (run/'review.template.json').write_text(json.dumps(review_template(run),ensure_ascii=False,indent=2))
            record.update(state=report['state'],run=str(run),video_sha256=digest(run/'video.mp4'))
            feedback={'report':report,'rendered_frames':[str(run/x) for x in ['contact-sheet.jpg','video.mp4']],
                      'instruction':'Inspect actual frames using your normal tools. Repair only named failures. Preserve every frozen requirement.'}
            if report['machine_ok']:
                if author_command:
                    request=author_packet(prompt,constraints,feedback)
                    request['phase']='inspect'
                    request['inspection_instruction']='Inspect the encoded MP4/contact sheet with your own tools. Return inspection={video_sha256,evidence:[paths/timestamps],limitations:[...]}, revise:boolean, and a complete contract/files if revise=true. This is an agent attestation, never human approval.'
                    inspection=invoke_author(author_command,request,author_timeout)
                    (attempt/'author-inspection.json').write_text(json.dumps(inspection,ensure_ascii=False,indent=2))
                    attestation=inspection.get('inspection',{})
                    if attestation.get('video_sha256')!=record['video_sha256'] or not attestation.get('evidence'):
                        raise ValueError('Author did not provide artifact-bound inspection evidence')
                    record['agent_inspection']='self-attested; not human approval'
                    if inspection.get('revise'):
                        feedback['agent_inspection']=inspection
                        record['state']='revision_requested';save();continue
                session['state']=report['state'];session['final_run']=str(run);save();return session
        except Exception as exc:
            record.update(state='blocked',error=str(exc));feedback={'error':str(exc),'previous_response':str(attempt/'author-response.json')}
        session['state']='blocked';save()
    return session
