"""Use one logged planning response once, then delegate repairs/inspection.

No shell and no hidden model selection. This adapter is used by one_prompt.py.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--first-response',required=True);p.add_argument('--upstream-command',required=True);args=p.parse_args()
request=json.load(sys.stdin)
if not request.get('feedback') and request.get('phase')!='inspect':
    print(Path(args.first_response).read_text())
else:
    command=json.loads(args.upstream_command)
    if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):raise ValueError('Expected argv list')
    result=subprocess.run(command,input=json.dumps(request),text=True,capture_output=True,timeout=300)
    if result.returncode:
        print('Upstream author failed',file=sys.stderr);raise SystemExit(result.returncode)
    print(result.stdout)
