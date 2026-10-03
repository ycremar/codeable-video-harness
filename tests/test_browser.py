"""Opt-in real browser integration; enabled in the dedicated CI job."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from vch.pipeline import render
from vch.evaluate import evaluate

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('VCH_TEST_BROWSER')=='1','Set VCH_TEST_BROWSER=1 after browser setup')
class BrowserIntegrationTests(unittest.TestCase):
    def test_real_pdoom_stream_decode_and_seeks(self):
        spec=json.loads((ROOT/'benchmarks/reference/candidate.json').read_text())['contract']
        spec['video']={'width':640,'height':360,'fps':4,'duration':1}
        spec['scenes']=spec['scenes'][:1];spec['scenes'][0]['end']=1
        spec['qa']={'sample_every':.5}
        spec['requirements']=[
            {'id':'D','description':'one second encoded','kind':'hard','metric':'duration_s','op':'eq','target':1},
            {'id':'SEEK','description':'seek repeatable','kind':'hard','metric':'determinism_mismatches','op':'eq','target':0},
            {'id':'ENCODE','description':'decoded pixels','kind':'proxy','metric':'decode_mae','op':'le','target':8}]
        with tempfile.TemporaryDirectory() as d:
            out=render(spec,ROOT,Path(d)/'run',True)
            r=evaluate(out)
            self.assertTrue(r['machine_ok'],r)
            manifest=json.loads((out/'manifest.json').read_text())
            self.assertIn('pdoom',manifest['runtime']['renderer']['name'])
            self.assertFalse(manifest['runtime']['renderer']['full_upstream_engine'])
