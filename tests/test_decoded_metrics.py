"""Decoded-evidence metrics: each has a true pass and a deliberate failure on real encodes."""
import copy
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from fakes import FakeRenderer, clicks, html_project
from vch.core import validate
from vch.evaluate import evaluate, measure
from vch.pipeline import _render

FPS, DURATION = 12, 2


def frames(mode):
    def draw(t):
        image = Image.new('RGB', (96, 96), '#202830')
        if mode == 'moving':
            ImageDraw.Draw(image).ellipse((10 + t * 30, 30, 30 + t * 30, 50), fill='#E0E8F0')
        if mode == 'flash' and abs(t - 1.0) < 1e-6:
            ImageDraw.Draw(image).rectangle((0, 0, 96, 96), fill='#FFFFFF')
        return image
    return draw


def overlapping_text(t):
    word = {'type': 'text', 'size': 20, 'contrast': 12.0, 'opacity': 1}
    return [{**word, 'id': 'a', 'text': 'AAAA', 'bbox': [10, 10, 60, 30]},
            {**word, 'id': 'b', 'text': 'BBBB', 'bbox': [14, 12, 64, 32]}]


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
        cls.base = {'version': 1, 'title': 'decoded', 'seed': 3, **html_project(cls.root),
                    'video': {'width': 96, 'height': 96, 'fps': FPS, 'duration': DURATION},
                    'scenes': [{'id': 's', 'start': 0, 'end': DURATION}],
                    'audio': {'mode': 'composition'},
                    'timing': {'bpm': 120, 'hits': [0.5, {'t': 1.0, 'cue': 'middle'}, 1.5]},
                    'qa': {'sample_every': 0.5}, 'requirements': []}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_spec(self, name, requirements, renderer=None, **changes):
        spec = copy.deepcopy(self.base)
        spec['requirements'] = requirements
        spec.update(changes)
        validate(spec, self.root)
        renderer = renderer or FakeRenderer(frames('moving'), audio=clicks(times=[0.5, 1.0, 1.5], duration=DURATION, bed=0.05))
        out = _render(spec, self.root, self.root/'runs'/name, renderer)
        return {r['id']: r for r in evaluate(out)['requirements']}, out

    def test_moving_clip_passes_timing_audio_and_motion_checks(self):
        rows, _ = self.run_spec('good', [
            requirement('FRAMES', 'encoded_frame_count', 'eq', FPS * DURATION, kind='hard'),
            requirement('PTS', 'frame_timestamp_jitter_ms', 'le', 1, kind='hard'),
            requirement('TP', 'true_peak_dbtp', 'le', -1, kind='hard'),
            requirement('LUFS', 'integrated_loudness_lufs', 'le', -10, kind='hard'),
            requirement('HITS', 'audio_hit_sync_ms', 'le', 15),
            requirement('HOLD', 'max_static_hold_s', 'le', 0.5),
            requirement('POPS', 'single_frame_pops', 'eq', 0)])
        for key, row in rows.items():
            self.assertEqual(row['status'], 'pass', (key, row))

    def test_one_flash_frame_is_a_pop_unless_excluded(self):
        rows, _ = self.run_spec('flash', [
            requirement('POPS', 'single_frame_pops', 'eq', 0),
            requirement('POPS-EXCLUDED', 'single_frame_pops', 'eq', 0, {'exclude': [[0.9, 1.1]]})],
            renderer=FakeRenderer(frames('flash')), audio={'mode': 'none'})
        self.assertEqual(rows['POPS']['status'], 'fail')
        self.assertEqual(rows['POPS']['value'], 1)
        self.assertEqual(rows['POPS-EXCLUDED']['status'], 'pass')

    def test_static_clip_fails_dead_time(self):
        rows, _ = self.run_spec('still', [requirement('HOLD', 'max_static_hold_s', 'le', 1.0)],
                                renderer=FakeRenderer(frames('still')), audio={'mode': 'none'})
        self.assertEqual(rows['HOLD']['status'], 'fail')
        self.assertGreater(rows['HOLD']['value'], 1.8)

    def test_overlapping_text_is_counted(self):
        rows, _ = self.run_spec('overlap', [requirement('OVERLAP', 'text_overlap_violations', 'eq', 0),
                                            requirement('IGNORED', 'text_overlap_violations', 'eq', 0, {'ignore_ids': ['b']})],
                                renderer=FakeRenderer(frames('still'), elements=overlapping_text), audio={'mode': 'none'})
        self.assertEqual(rows['OVERLAP']['status'], 'fail')
        self.assertEqual(rows['OVERLAP']['value'], FPS * DURATION)
        self.assertEqual(rows['IGNORED']['status'], 'pass')

    def test_sound_away_from_declared_hit_fails_sync(self):
        data = np.zeros(48000)
        data[24000:24048] = 0.8  # click at 0.5 s into the file
        with wave.open(str(self.root/'click.wav'), 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(48000)
            f.writeframes(np.rint(data*32767).astype('<i2').tobytes())
        assets = [{'path': 'click.wav', 'source': 'synthetic fixture', 'license': 'test fixture'}]
        audio = {'mode': 'mix', 'layers': [{'path': 'click.wav', 'at': 1.0, 'align': 'peak'}]}
        rows, _ = self.run_spec('late', [requirement('HITS', 'audio_hit_sync_ms', 'le', 20)],
                                renderer=FakeRenderer(frames('moving')), assets=assets, audio=audio,
                                timing={'bpm': 120, 'hits': [0.5]})
        self.assertEqual(rows['HITS']['status'], 'fail')
        self.assertAlmostEqual(rows['HITS']['value'], 500, delta=10)

    def test_missing_decoded_evidence_stays_unmeasured(self):
        with self.assertRaises(ValueError):
            measure('max_static_hold_s', {}, self.base, {'probe': {'streams': []}}, [], self.root)
        with self.assertRaises(ValueError):
            measure('integrated_loudness_lufs', {}, self.base, {'probe': {'streams': []}}, [], self.root)


if __name__ == '__main__':
    unittest.main()
