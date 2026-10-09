import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from fakes import FakeRenderer, clicks, moving_disc
from vch import signals
from vch.audio import SAMPLE_RATE, composition_track, master, mix_track, render_audio
from vch.core import validate

ROOT = Path(__file__).resolve().parents[1]
CUES = [0.5, 1.25, 2.0]


def write_click_wav(path, *, lead_s, seconds=0.5):
    """A licensed-asset stand-in: silence, then one click `lead_s` into the file."""
    data = np.zeros(int(SAMPLE_RATE * seconds))
    data[int(lead_s * SAMPLE_RATE):int(lead_s * SAMPLE_RATE) + 48] = 0.8
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SAMPLE_RATE)
        f.writeframes(np.rint(data * 32767).astype('<i2').tobytes())


def composition_spec(duration=3, **audio):
    return {'video': {'duration': duration}, 'timing': {'hits': CUES}, 'audio': {'mode': 'composition', **audio}}


def detected(track):
    mono = track.mean(axis=1)[::2]
    return [e['t'] for e in signals.detect_onsets(mono, rate=SAMPLE_RATE // 2)]


class CompositionAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def renderer(self, synthesize):
        return FakeRenderer(moving_disc(), audio=synthesize)

    def test_cues_are_found_where_the_composition_placed_them(self):
        track, info = composition_track(composition_spec(), self.renderer(clicks(times=CUES, duration=3)))
        self.assertEqual(info['channels'], 2)
        self.assertEqual(len(info['sha256']), 64)
        found = detected(track)
        self.assertEqual(len(found), len(CUES))
        for a, b in zip(found, CUES):
            self.assertLess(abs(a - b), 0.002)

    def test_mastering_reaches_the_loudness_target(self):
        spec = composition_spec(loudness_target=-20, peak_ceiling_dbfs=-1)
        path, info = render_audio(spec, ROOT, self.out, self.renderer(clicks(times=CUES, duration=3, level=0.3, bed=0.2)))
        self.assertEqual(info['mode'], 'composition')
        self.assertFalse(info['mastering']['limited_by_ceiling'])
        self.assertAlmostEqual(signals.loudness_of_file(path)['integrated_lufs'], -20, delta=0.5)

    def test_wrong_length_or_nonfinite_samples_are_rejected(self):
        short = lambda rate: np.zeros((rate, 2))
        broken = lambda rate: np.full((3 * rate, 2), np.nan)
        for synthesize in (short, broken):
            with self.assertRaises(ValueError):
                composition_track(composition_spec(), self.renderer(synthesize))

    def test_a_renderer_without_audio_is_rejected(self):
        with self.assertRaises(ValueError):
            composition_track(composition_spec(), None)

    def test_clipping_without_a_ceiling_gain_is_rejected(self):
        loud = lambda rate: np.full((3 * rate, 1), 1.5)
        with self.assertRaisesRegex(ValueError, 'clips above 0 dBFS'):
            render_audio(composition_spec(), ROOT, self.out, self.renderer(loud))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT/'examples/how-code-becomes-video.json').read_text())

    def test_composition_audio_is_valid(self):
        self.assertEqual(validate(self.spec, ROOT)['audio']['mode'], 'composition')

    def test_hits_must_be_inside_duration(self):
        self.spec['timing']['hits'] = [48.0]
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_hit_labels_are_short_strings(self):
        for label in ('x' * 81, 7, ''):
            self.spec['timing']['hits'] = [{'t': 1, 'cue': label}]
            with self.assertRaises(ValueError, msg=label):
                validate(self.spec, ROOT)

    def test_mix_layers_need_declared_assets(self):
        self.spec['audio'] = {'mode': 'mix', 'layers': [{'path': 'assets/sfx/undeclared.wav', 'at': 1}]}
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_mix_needs_a_layer(self):
        self.spec['audio'] = {'mode': 'mix', 'layers': []}
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_loudness_target_range(self):
        self.spec['audio']['loudness_target'] = 3
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
class MixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'assets').mkdir()
        write_click_wav(self.root/'assets/click.wav', lead_s=0.1)

    def tearDown(self):
        self.temp.cleanup()

    def spec(self, align):
        return {'video': {'duration': 2}, 'timing': {},
                'audio': {'mode': 'mix', 'layers': [{'path': 'assets/click.wav', 'at': 0.5, 'align': align}]}}

    def test_peak_alignment_ignores_file_lead_in(self):
        track, info = mix_track(self.spec('peak'), self.root)
        self.assertAlmostEqual(detected(track)[0], 0.5, delta=0.002)
        self.assertAlmostEqual(info['layers'][0]['peak_offset_s'], 0.1, delta=0.001)
        track, _ = mix_track(self.spec('start'), self.root)
        self.assertAlmostEqual(detected(track)[0], 0.6, delta=0.002)

    def test_ceiling_limits_gain_and_is_reported(self):
        track, _ = mix_track(self.spec('peak'), self.root)
        mastered, report = master(track, target=-6, ceiling_dbfs=-3)
        self.assertTrue(report['limited_by_ceiling'])
        self.assertLessEqual(20*np.log10(np.max(np.abs(mastered))), -3 + 1e-6)


if __name__ == '__main__':
    unittest.main()
