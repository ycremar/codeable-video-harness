import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from fakes import FakeRenderer, html_project, moving_disc
from vch.core import contrast_rgb, validate
from vch.evaluate import compare, evaluate, measure, review_template
from vch.pipeline import _render, audit

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT/'examples/how-code-becomes-video.json'


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(EXAMPLE.read_text())

    def test_valid(self):
        validate(self.spec, ROOT)

    def test_duplicate_requirement(self):
        self.spec['requirements'].append(self.spec['requirements'][0])
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_gap(self):
        self.spec['scenes'][1]['start'] = 6.5
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_overlap(self):
        self.spec['scenes'][1]['start'] = 5.5
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_nan_duration(self):
        self.spec['video']['duration'] = float('nan')
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_infinite_target(self):
        self.spec['requirements'][0]['target'] = float('inf')
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_bad_qa_interval(self):
        self.spec['qa']['sample_every'] = 0
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_boolean_not_numeric(self):
        self.assertFalse(compare(True, 'eq', 1))
        self.assertFalse(compare(1, 'eq', True))

    def test_odd_dimensions(self):
        self.spec['video']['width'] = 1919
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_missing_rights(self):
        del self.spec['assets'][0]['license']
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_entry_cannot_escape_the_project(self):
        self.spec['html']['entry'] = '../outside/index.html'
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_html_is_the_only_backend(self):
        for backend in ('scene', 'pdoom', None):
            spec = copy.deepcopy(self.spec)
            spec['backend'] = backend
            with self.assertRaises(ValueError, msg=backend):
                validate(spec, ROOT)

    def test_retired_procedural_audio_is_rejected(self):
        self.spec['audio'] = {'mode': 'procedural', 'gain': 0.8}
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_duplicate_cue_names_rejected(self):
        self.spec['timing']['hits'][1]['cue'] = self.spec['timing']['hits'][0]['cue']
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_contrast(self):
        self.assertAlmostEqual(contrast_rgb((255, 255, 255), (0, 0, 0)), 21)

    def test_nonfinite_metric(self):
        with self.assertRaises(ValueError):
            compare(float('nan'), 'le', 10)

    def test_malformed_human(self):
        self.spec['requirements'][-1].pop('rubric')
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)


class MeasurementTests(unittest.TestCase):
    def test_bad_typography(self):
        spec = {'video': {'width': 96, 'height': 96}}
        text = {'id': 'ad', 'type': 'text', 'text': 'BOOK NOW', 'size': 12, 'bbox': [2, 2, 60, 14], 'contrast': 1.05, 'opacity': 1}
        trace = [{'t': 0, 'frame': 0, 'elements': [text]}]
        ev = {'probe': {'streams': [{'codec_type': 'video'}]}}
        value, _ = measure('safe_area_violations', {'margins': [20, 20, 20, 20]}, spec, ev, trace, ROOT)
        self.assertGreater(value, 0)
        value, _ = measure('minimum_contrast', {}, spec, ev, trace, ROOT)
        self.assertLess(value, 1.1)
        value, _ = measure('minimum_text_size_px', {}, spec, ev, trace, ROOT)
        self.assertLess(value, 18)
        value, _ = measure('text_absent', {'strings': ['BOOK NOW']}, spec, ev, trace, ROOT)
        self.assertFalse(value)

    def test_missing_telemetry_is_unknown(self):
        ev = {'probe': {'streams': [{'codec_type': 'video'}]}}
        with self.assertRaises(ValueError):
            measure('safe_area_violations', {}, {}, ev, [], ROOT)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class RenderIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.spec = {'version': 1, 'title': 'test', 'seed': 1, **html_project(cls.root),
                    'video': {'width': 96, 'height': 96, 'fps': 6, 'duration': 1},
                    'scenes': [{'id': 's', 'start': 0, 'end': 1}],
                    'audio': {'mode': 'none'}, 'qa': {'sample_every': .5},
                    'requirements': [{'id': 'D', 'description': 'one second', 'kind': 'hard', 'metric': 'duration_s', 'op': 'eq', 'target': 1},
                                     {'id': 'SEEK', 'description': 'repeatable', 'kind': 'hard', 'metric': 'determinism_mismatches', 'op': 'eq', 'target': 0},
                                     {'id': 'HUM', 'description': 'visual quality', 'kind': 'human', 'rubric': 'Inspect output'}]}
        validate(cls.spec, cls.root)
        cls.out = cls.render(cls.spec, 'good')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def render(cls, spec, name, renderer=None):
        return _render(spec, cls.root, cls.root/'runs'/name, renderer or FakeRenderer(moving_disc()))

    def test_requires_review(self):
        r = evaluate(self.out)
        self.assertEqual(r['state'], 'needs_review')
        self.assertFalse(r['accepted'])

    def test_completed_bound_review(self):
        review = review_template(self.out)
        review['reviewer'] = 'Synthetic unit-test fixture (not real approval)'
        review['decisions']['HUM'].update(decision='pass', reason='Unit test only', evidence=['frames/0000.png'])
        path = self.root/'runs/review.json'
        path.write_text(json.dumps(review))
        self.assertTrue(evaluate(self.out, path)['accepted'])

    def test_stale_review(self):
        review = review_template(self.out)
        review['binding'] = 'old'
        review['reviewer'] = 'Test'
        review['decisions']['HUM'].update(decision='pass', reason='old', evidence=['old.mp4'])
        path = self.root/'runs/stale.json'
        path.write_text(json.dumps(review))
        self.assertFalse(evaluate(self.out, path)['accepted'])

    def test_failed_review_blocks(self):
        review = review_template(self.out)
        review['reviewer'] = 'Synthetic negative fixture'
        review['decisions']['HUM'].update(decision='fail', reason='Test failure', evidence=['video.mp4 t=0'])
        path = self.root/'runs/fail-review.json'
        path.write_text(json.dumps(review))
        self.assertEqual(evaluate(self.out, path)['state'], 'blocked')

    def test_missing_metric_dependency_unmeasured(self):
        with patch('vch.evaluate.measure', side_effect=subprocess.CalledProcessError(1, ['missing-language'])):
            result = evaluate(self.out)
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['requirements'][0]['status'], 'unmeasured')

    def test_artifact_tamper(self):
        target = self.out/'video.mp4'
        original = target.read_bytes()
        try:
            target.write_bytes(original + b'tamper')
            with self.assertRaises(ValueError):
                audit(self.out)
        finally:
            target.write_bytes(original)

    def test_frame_tamper(self):
        target = next((self.out/'frames').glob('*.png'))
        original = target.read_bytes()
        try:
            target.write_bytes(original + b'tamper')
            with self.assertRaises(ValueError):
                audit(self.out)
        finally:
            target.write_bytes(original)

    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError):
            _render(self.spec, self.root, self.out, FakeRenderer(moving_disc()))

    def test_unknown_metric_blocks(self):
        spec = copy.deepcopy(self.spec)
        spec['requirements'].append({'id': 'MAGIC', 'description': 'be impressive', 'kind': 'proxy', 'metric': 'shock_score', 'op': 'ge', 'target': .9})
        result = evaluate(self.render(spec, 'unknown'))
        self.assertEqual(result['state'], 'blocked')
        self.assertEqual(result['requirements'][-1]['status'], 'unmeasured')

    def test_proxy_cannot_be_promoted(self):
        spec = copy.deepcopy(self.spec)
        spec['requirements'].append({'id': 'PROXY', 'description': 'black check', 'kind': 'hard', 'metric': 'black_fraction', 'op': 'le', 'target': 1})
        self.assertEqual(evaluate(self.render(spec, 'proxy'))['requirements'][-1]['status'], 'unmeasured')

    def test_state_carried_between_frames_is_detected(self):
        calls = [0]

        def stateful(t):
            calls[0] += 1
            return Image.new('RGB', (96, 96), (calls[0] % 255, 20, 30))
        out = self.render(self.spec, 'stateful', FakeRenderer(stateful))
        self.assertEqual(evaluate(out)['requirements'][1]['status'], 'fail')


if __name__ == '__main__':
    unittest.main()
