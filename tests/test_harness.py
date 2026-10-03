import copy
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from pathlib import Path
from vch.core import validate, load_contract, SceneRenderer, contrast, noise
from vch.evaluate import compare, evaluate, measure, review_template
from vch.pipeline import render, audit

ROOT=Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/explainer.json').read_text())

    def test_valid(self): validate(self.spec,ROOT)
    def test_duplicate_requirement(self):
        self.spec['requirements'].append(self.spec['requirements'][0])
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_gap(self):
        self.spec['scenes'][1]['start']=2.5
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_overlap(self):
        self.spec['scenes'][1]['start']=1.5
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_nan_duration(self):
        self.spec['video']['duration']=float('nan')
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_infinite_target(self):
        self.spec['requirements'][0]['target']=float('inf')
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_bad_qa_interval(self):
        self.spec['qa']['sample_every']=0
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_boolean_not_numeric(self):
        self.assertFalse(compare(True,'eq',1))
        self.assertFalse(compare(1,'eq',True))
    def test_odd_dimensions(self):
        self.spec['video']['width']=639
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_missing_rights(self):
        del self.spec['assets'][0]['license']
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_escape(self):
        self.spec['scenes'][0]['module']='../not-allowed.py'
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_code_optin(self):
        with self.assertRaises(PermissionError):SceneRenderer(self.spec,ROOT)
    def test_deterministic_noise(self):
        self.assertEqual(noise(2,'a'),noise(2,'a'));self.assertNotEqual(noise(2,'a'),noise(3,'a'))
    def test_contrast(self):self.assertAlmostEqual(contrast('#ffffff','#000000'),21)
    def test_nonfinite_metric(self):
        with self.assertRaises(ValueError):compare(float('nan'),'le',10)
    def test_malformed_human(self):
        self.spec['requirements'][-1].pop('rubric')
        with self.assertRaises(ValueError):validate(self.spec,ROOT)
    def test_scene_seek(self):
        renderer=SceneRenderer(self.spec,ROOT,True)
        a=renderer.render(1.1).image.tobytes();renderer.render(7.4)
        self.assertEqual(a,renderer.render(1.1).image.tobytes())


class MeasurementTests(unittest.TestCase):
    def test_bad_typography(self):
        spec,root=load_contract(ROOT/'examples/explainer.json')
        spec['scenes'][0]['module']='scenes/broken.py'
        renderer=SceneRenderer(spec,root,True)
        trace=[{'t':0,'frame':0,'elements':renderer.render(0).elements}]
        ev={'probe':{'streams':[{'codec_type':'video'}]}}
        value,_=measure('safe_area_violations',{'margins':[20,20,20,20]},spec,ev,trace,ROOT)
        self.assertGreater(value,0)
        value,_=measure('minimum_contrast',{},spec,ev,trace,ROOT);self.assertLess(value,1.1)
        value,_=measure('minimum_text_size_px',{},spec,ev,trace,ROOT);self.assertLess(value,18)
        value,_=measure('text_absent',{'strings':['BOOK NOW']},spec,ev,trace,ROOT);self.assertFalse(value)
    def test_missing_telemetry_is_unknown(self):
        ev={'probe':{'streams':[{'codec_type':'video'}]}}
        with self.assertRaises(ValueError):measure('safe_area_violations',{}, {},ev,[],ROOT)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class RenderIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        (cls.root/'scene.py').write_text('from vch.core import Canvas\ndef render(ctx):\n c=Canvas(96,96,"#CCCCCC")\n c.draw.ellipse((20+ctx["t"]*10,20,40+ctx["t"]*10,40),fill="#2255AA")\n return c.finish()\n')
        cls.spec={'version':1,'title':'test','seed':1,'video':{'width':96,'height':96,'fps':6,'duration':1},
                  'scenes':[{'id':'s','start':0,'end':1,'module':'scene.py'}],
                  'audio':{'mode':'none'},'qa':{'sample_every':.5},
                  'requirements':[{'id':'D','description':'one second','kind':'hard','metric':'duration_s','op':'eq','target':1},
                                  {'id':'SEEK','description':'repeatable','kind':'hard','metric':'determinism_mismatches','op':'eq','target':0},
                                  {'id':'HUM','description':'visual quality','kind':'human','rubric':'Inspect output'}]}
        validate(cls.spec,cls.root)
        cls.out=render(cls.spec,cls.root,cls.root/'runs/good',True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_requires_review(self):
        r=evaluate(self.out);self.assertEqual(r['state'],'needs_review');self.assertFalse(r['accepted'])
    def test_completed_bound_review(self):
        review=review_template(self.out);review['reviewer']='Synthetic unit-test fixture (not real approval)'
        review['decisions']['HUM'].update(decision='pass',reason='Unit test only',evidence=['frames/0000.png'])
        path=self.root/'runs/review.json';path.write_text(json.dumps(review))
        self.assertTrue(evaluate(self.out,path)['accepted'])
    def test_stale_review(self):
        review=review_template(self.out);review['binding']='old';review['reviewer']='Test'
        review['decisions']['HUM'].update(decision='pass',reason='old',evidence=['old.mp4'])
        path=self.root/'runs/stale.json';path.write_text(json.dumps(review))
        self.assertFalse(evaluate(self.out,path)['accepted'])
    def test_failed_review_blocks(self):
        review=review_template(self.out);review['reviewer']='Synthetic negative fixture'
        review['decisions']['HUM'].update(decision='fail',reason='Test failure',evidence=['video.mp4 t=0'])
        path=self.root/'runs/fail-review.json';path.write_text(json.dumps(review))
        self.assertEqual(evaluate(self.out,path)['state'],'blocked')
    def test_missing_metric_dependency_unmeasured(self):
        with patch('vch.evaluate.measure',side_effect=subprocess.CalledProcessError(1,['missing-language'])):
            result=evaluate(self.out)
        self.assertEqual(result['state'],'blocked')
        self.assertEqual(result['requirements'][0]['status'],'unmeasured')
    def test_artifact_tamper(self):
        target=self.out/'video.mp4';original=target.read_bytes()
        try:
            target.write_bytes(original+b'tamper')
            with self.assertRaises(ValueError):audit(self.out)
        finally:target.write_bytes(original)
    def test_frame_tamper(self):
        target=next((self.out/'frames').glob('*.png'));original=target.read_bytes()
        try:
            target.write_bytes(original+b'tamper')
            with self.assertRaises(ValueError):audit(self.out)
        finally:target.write_bytes(original)
    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError):render(self.spec,self.root,self.out,True)
    def test_unknown_metric_blocks(self):
        spec=copy.deepcopy(self.spec);spec['requirements'].append({'id':'MAGIC','description':'be impressive','kind':'proxy','metric':'shock_score','op':'ge','target':.9})
        out=render(spec,self.root,self.root/'runs/unknown',True)
        result=evaluate(out);self.assertEqual(result['state'],'blocked');self.assertEqual(result['requirements'][-1]['status'],'unmeasured')
    def test_proxy_cannot_be_promoted(self):
        spec=copy.deepcopy(self.spec);spec['requirements'].append({'id':'PROXY','description':'black check','kind':'hard','metric':'black_fraction','op':'le','target':1})
        out=render(spec,self.root,self.root/'runs/proxy',True)
        self.assertEqual(evaluate(out)['requirements'][-1]['status'],'unmeasured')
    def test_stateful_scene_detected(self):
        (self.root/'stateful.py').write_text('from vch.core import Canvas\nn=0\ndef render(ctx):\n global n\n n+=1\n return Canvas(96,96,(n%255,20,30)).finish()\n')
        spec=copy.deepcopy(self.spec);spec['scenes'][0]['module']='stateful.py'
        out=render(spec,self.root,self.root/'runs/stateful',True)
        self.assertEqual(evaluate(out)['requirements'][1]['status'],'fail')


if __name__=='__main__':unittest.main()
