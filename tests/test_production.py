import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from vch.production import produce, frozen_check, invoke_author
from vch.narration import schedule_phrases
from vch.evaluate import measure

BASE=Path(__file__).resolve().parents[1]

class ProductionTests(unittest.TestCase):
    def test_changed_threshold_rejected(self):
        constraints={'requirements':[{'id':'X','target':10}],'video':{'duration':12}}
        with self.assertRaises(ValueError):frozen_check({'requirements':[{'id':'X','target':1}],'video':{'duration':12}},constraints)
    def test_changed_duration_rejected(self):
        with self.assertRaises(ValueError):frozen_check({'requirements':[],'video':{'duration':2}},{'requirements':[],'video':{'duration':3}})
    def test_tts_overflow_is_error(self):
        with self.assertRaises(ValueError):schedule_phrases(['too long'],0,2,[2.1])
    def test_phrase_timing_nonoverlap_and_bounds(self):
        cues=schedule_phrases(['one','two','three'],12,24,[2,3,1])
        self.assertGreaterEqual(cues[0]['start'],12)
        self.assertLessEqual(cues[-1]['end'],24)
        self.assertTrue(all(a['end']<=b['start'] for a,b in zip(cues,cues[1:])))
    def test_missing_tts_evidence_unmeasured(self):
        with self.assertRaises(ValueError):measure('narration_seconds',{}, {}, {}, [],BASE)
    def test_caption_mismatch_unmeasured(self):
        ev={'narration':{'phrases':[{'text':'one','start':0,'end':1}]}}
        with self.assertRaises(ValueError):measure('caption_timing_error_ms',{}, {'captions':[{'text':'other','start':0,'end':1}]}, ev, [],BASE)
    def test_prepare_without_provider_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'job';r=produce('A new prompt',{'requirements':[]},out)
            self.assertEqual(r['state'],'needs_author');self.assertEqual(r['mode'],'agent-workspace-packet')
            self.assertTrue((out/'author-request.json').exists())
            with self.assertRaises(FileExistsError):produce('again',{'requirements':[]},out)
    def test_author_must_return_json(self):
        with self.assertRaises(ValueError):invoke_author([sys.executable,'-c','print("not JSON")'],{},5)
    def test_no_shell_command_string(self):
        with self.assertRaises(ValueError):invoke_author('echo bad',{},5)

@unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
class ProductionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.spec={'version':1,'title':'fixture','seed':1,'video':{'width':96,'height':96,'fps':6,'duration':1},
        'audio':{'mode':'none'},'qa':{'sample_every':.5},
        'scenes':[{'id':'x','start':0,'end':1,'module':'scenes/fixture.py'}],
        'requirements':[{'id':'D','description':'duration','kind':'hard','metric':'duration_s','op':'eq','target':1},
        {'id':'H','description':'look','kind':'human','rubric':'Watch actual output'}]}
        self.response={'contract':self.spec,'files':{'scenes/fixture.py':'from vch.core import Canvas\ndef render(ctx):\n return Canvas(96,96,"#889999").finish()\n'}}
        self.constraints={'video':self.spec['video'],'requirements':self.spec['requirements']}
    def tearDown(self):self.temp.cleanup()
    def test_replay_is_labelled_and_never_approved(self):
        candidate=self.root/'candidate.json';candidate.write_text(json.dumps(self.response))
        r=produce('Test',self.constraints,self.root/'replay',candidate_file=candidate,trust_code=True)
        self.assertEqual(r['mode'],'candidate-replay');self.assertEqual(r['state'],'needs_review')
    def test_author_cannot_write_evaluator(self):
        self.response['files']={'vch/evaluate.py':'forged'}
        candidate=self.root/'candidate.json';candidate.write_text(json.dumps(self.response))
        r=produce('Test',self.constraints,self.root/'blocked',candidate_file=candidate,trust_code=True)
        self.assertEqual(r['state'],'blocked');self.assertIn('restricted',r['attempts'][0]['error'])
    def test_external_author_repairs_failure_without_new_prompt(self):
        candidate=self.root/'candidate.json';candidate.write_text(json.dumps(self.response))
        author=self.root/'author.py'
        author.write_text('import json,sys,hashlib\nfrom pathlib import Path\np=json.load(sys.stdin)\nr=json.loads(Path(sys.argv[1]).read_text())\nif not p.get("feedback"): r["contract"]["requirements"][0]["target"]=2\nif p.get("phase")=="inspect":\n v=Path(p["feedback"]["rendered_frames"][1]);r={"inspection":{"video_sha256":hashlib.sha256(v.read_bytes()).hexdigest(),"evidence":["Synthetic test fixture only; no real inspection"],"limitations":["not a live model"]},"revise":False}\nprint(json.dumps(r))\n')
        r=produce('One user prompt',self.constraints,self.root/'loop',author_command=[sys.executable,str(author),str(candidate)],trust_code=True,max_attempts=2)
        self.assertEqual(len(r['attempts']),2);self.assertEqual(r['attempts'][0]['state'],'blocked')
        self.assertEqual(r['state'],'needs_review')
        # This fixture proves control flow only, never live model intelligence.
        self.assertEqual(r['model_identity'],'not verified by harness')
