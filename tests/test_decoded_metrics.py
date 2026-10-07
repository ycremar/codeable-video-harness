"""Decoded-evidence metrics: each has a true pass and a deliberate failure on real encodes."""
import copy
import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from vch.core import validate
from vch.evaluate import evaluate, measure
from vch.pipeline import render

SCENE = '''from vch.core import Canvas
def render(ctx):
    c = Canvas(96, 96, "#202830")
    mode = ctx["scene"].get("params", {}).get("mode", "moving")
    t = ctx["t"]
    if mode == "moving":
        c.draw.ellipse((10 + t * 30, 30, 30 + t * 30, 50), fill="#E0E8F0")
    if mode == "flash" and abs(t - 1.0) < 1e-6:
        c.draw.rectangle((0, 0, 96, 96), fill="#FFFFFF")
    if mode == "overlap":
        c.text("a", (10, 10), "AAAA", ctx["root"] / "Inter.ttf", 20, "#FFFFFF")
        c.text("b", (14, 12), "BBBB", ctx["root"] / "Inter.ttf", 20, "#FFFFFF")
    return c.finish()
'''
ROOT = Path(__file__).resolve().parents[1]


def requirement(id_, metric, op, target, params=None, kind='proxy'):
    r = {'id': id_, 'description': id_, 'kind': kind, 'metric': metric, 'op': op, 'target': target}
    if params is not None:
        r['params'] = params
    return r


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class DecodedMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        (cls.root/'scene.py').write_text(SCENE)
        shutil.copy(ROOT/'assets/fonts/Inter.ttf', cls.root/'Inter.ttf')
        cls.base = {'version': 1, 'title': 'decoded', 'seed': 3,
                    'video': {'width': 96, 'height': 96, 'fps': 12, 'duration': 2},
                    'assets': [{'path': 'Inter.ttf', 'source': 'repo fixture', 'license': 'SIL OFL 1.1'}],
                    'scenes': [{'id': 's', 'start': 0, 'end': 2, 'module': 'scene.py', 'params': {'mode': 'moving'}}],
                    'audio': {'mode': 'procedural', 'gain': 0.6, 'bed': False},
                    'timing': {'bpm': 120, 'hits': [0.5, {'t': 1.0, 'kind': 'impact'}, 1.5]},
                    'qa': {'sample_every': 0.5}, 'requirements': []}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_spec(self, name, requirements, **changes):
        spec = copy.deepcopy(self.base)
        spec['requirements'] = requirements
        for key, value in changes.items():
            spec[key] = value
        validate(spec, self.root)
        out = render(spec, self.root, self.root/'runs'/name, True)
        return {r['id']: r for r in evaluate(out)['requirements']}, out

    def test_moving_clip_passes_timing_audio_and_motion_checks(self):
        rows, _ = self.run_spec('good', [
            requirement('FRAMES', 'encoded_frame_count', 'eq', 24, kind='hard'),
            requirement('PTS', 'frame_timestamp_jitter_ms', 'le', 1, kind='hard'),
            requirement('TP', 'true_peak_dbtp', 'le', -1, kind='hard'),
            requirement('LUFS', 'integrated_loudness_lufs', 'le', -10, kind='hard'),
            requirement('HITS', 'audio_hit_sync_ms', 'le', 15),
            requirement('HOLD', 'max_static_hold_s', 'le', 0.5),
            requirement('POPS', 'single_frame_pops', 'eq', 0)])
        for key, row in rows.items():
            self.assertEqual(row['status'], 'pass', (key, row))

    def test_one_flash_frame_is_a_pop_unless_excluded(self):
        scenes = [{'id': 's', 'start': 0, 'end': 2, 'module': 'scene.py', 'params': {'mode': 'flash'}}]
        rows, _ = self.run_spec('flash', [
            requirement('POPS', 'single_frame_pops', 'eq', 0),
            requirement('POPS-EXCLUDED', 'single_frame_pops', 'eq', 0, {'exclude': [[0.9, 1.1]]})], scenes=scenes)
        self.assertEqual(rows['POPS']['status'], 'fail')
        self.assertEqual(rows['POPS']['value'], 1)
        self.assertEqual(rows['POPS-EXCLUDED']['status'], 'pass')

    def test_static_clip_fails_dead_time(self):
        scenes = [{'id': 's', 'start': 0, 'end': 2, 'module': 'scene.py', 'params': {'mode': 'still'}}]
        rows, _ = self.run_spec('still', [requirement('HOLD', 'max_static_hold_s', 'le', 1.0)], scenes=scenes)
        self.assertEqual(rows['HOLD']['status'], 'fail')
        self.assertGreater(rows['HOLD']['value'], 1.8)

    def test_overlapping_text_is_counted(self):
        scenes = [{'id': 's', 'start': 0, 'end': 2, 'module': 'scene.py', 'params': {'mode': 'overlap'}}]
        rows, _ = self.run_spec('overlap', [requirement('OVERLAP', 'text_overlap_violations', 'eq', 0),
                                            requirement('IGNORED', 'text_overlap_violations', 'eq', 0, {'ignore_ids': ['b']})],
                                scenes=scenes)
        self.assertEqual(rows['OVERLAP']['status'], 'fail')
        self.assertEqual(rows['OVERLAP']['value'], 24)
        self.assertEqual(rows['IGNORED']['status'], 'pass')

    def test_sound_away_from_declared_hit_fails_sync(self):
        data = np.zeros(48000)
        data[24000:24048] = 0.8  # click at 0.5 s into the file
        with wave.open(str(self.root/'click.wav'), 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(48000)
            f.writeframes(np.rint(data*32767).astype('<i2').tobytes())
        assets = self.base['assets'] + [{'path': 'click.wav', 'source': 'synthetic fixture', 'license': 'test fixture'}]
        audio = {'mode': 'mix', 'layers': [{'path': 'click.wav', 'at': 1.0, 'align': 'peak'}]}
        rows, _ = self.run_spec('late', [requirement('HITS', 'audio_hit_sync_ms', 'le', 20)],
                                assets=assets, audio=audio, timing={'bpm': 120, 'hits': [0.5]})
        self.assertEqual(rows['HITS']['status'], 'fail')
        self.assertAlmostEqual(rows['HITS']['value'], 500, delta=10)

    def test_missing_decoded_evidence_stays_unmeasured(self):
        with self.assertRaises(ValueError):
            measure('max_static_hold_s', {}, self.base, {'probe': {'streams': []}}, [], self.root)
        with self.assertRaises(ValueError):
            measure('integrated_loudness_lufs', {}, self.base, {'probe': {'streams': []}}, [], self.root)


if __name__ == '__main__':
    unittest.main()
