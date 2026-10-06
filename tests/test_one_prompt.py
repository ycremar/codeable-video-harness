import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ms=importlib.util.spec_from_file_location('one_prompt',ROOT/'scripts/one_prompt.py');m=importlib.util.module_from_spec(ms);ms.loader.exec_module(m)

@unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
class OnePromptTests(unittest.TestCase):
    def test_prompt_extract_render_inspect_has_no_human_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);author=root/'author.py'
            spec={'version':1,'title':'fixture','seed':1,'video':{'width':96,'height':96,'fps':4,'duration':1},'scenes':[{'id':'x','start':0,'end':1,'module':'scenes/test.py'}],'requirements':[{'id':'D','description':'one second','kind':'hard','metric':'duration_s','op':'eq','target':1}]}
            response={'contract':spec,'files':{'scenes/test.py':'from vch.core import Canvas\ndef render(ctx): return Canvas(96,96,"#778899").finish()'}}
            (root/'candidate.json').write_text(json.dumps(response))
            author.write_text('import json,sys,hashlib\nfrom pathlib import Path\np=json.load(sys.stdin)\nif p.get("phase")=="inspect":\n v=Path(p["feedback"]["rendered_frames"][1]);r={"inspection":{"video_sha256":hashlib.sha256(v.read_bytes()).hexdigest(),"evidence":["fixture only"]},"revise":False}\nelse:r=json.loads(Path(sys.argv[1]).read_text())\nprint(json.dumps(r))\n')
            result=m.run('Make a one-second animation',root/'job',[sys.executable,str(author),str(root/'candidate.json')],trust_code=True,max_attempts=1)
            self.assertEqual(result['state'],'needs_review')
            frozen=json.loads((root/'job/frozen-constraints.json').read_text())
            self.assertEqual(frozen['requirements'][-1]['id'],'PROMPT-FIDELITY')
            report=json.loads((Path(result['final_run'])/'report.json').read_text())
            self.assertEqual(report['requirements'][-1]['status'],'unmeasured')
