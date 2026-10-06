"""Opt-in real browser integration; enabled in the dedicated CI job."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from vch.pipeline import render
from vch.pipeline import sample_times
from vch.backends import BrowserRenderer
from vch.core import canonical
from vch.evaluate import evaluate

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('VCH_TEST_BROWSER')=='1','Set VCH_TEST_BROWSER=1 after browser setup')
class BrowserIntegrationTests(unittest.TestCase):
    def test_all_scene_types_seek_without_inherited_canvas_state(self):
        # The short hero smoke test missed state leaking across mixed compositions.
        # Keep production dimensions and all transitions; compare exact pixels and telemetry.
        spec=json.loads((ROOT/'benchmarks/reference/candidate.json').read_text())['contract']
        renderer=BrowserRenderer(spec,ROOT,True)
        try:
            times=sample_times(spec)
            def fingerprint(t):
                frame=renderer.sampled(t)
                return hashlib.sha256(frame.image.tobytes()+canonical(frame.elements).encode()).hexdigest()
            reference={t:fingerprint(t) for t in times}
            for t in list(reversed(times))+times[::2]+times[1::2]:
                self.assertEqual(reference[t],fingerprint(t),f'Order-dependent pixels/telemetry at {t}s')
        finally:
            renderer.close()

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
