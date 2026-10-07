import copy
import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from vch import signals
from vch.audio import SAMPLE_RATE, beat_bed, master, mix_track, procedural_track
from vch.core import validate

ROOT = Path(__file__).resolve().parents[1]


def legacy_bed(spec):
    """The procedural bed exactly as the harness produced it before cue hits existed."""
    sr, seconds = 48000, spec['video']['duration']
    signal = np.zeros(round(sr*seconds), dtype=np.float64)
    bpm = spec.get('timing', {}).get('bpm', 120)
    offset = spec.get('timing', {}).get('beat_offset', 0)
    for i, start in enumerate(np.arange(offset, seconds, 60/bpm)):
        if start < 0:
            continue
        t = np.arange(int(sr*.22))/sr
        hit = np.sin(2*np.pi*(70*t + 14*(1-np.exp(-32*t))))*np.exp(-28*t)
        if i % 2:
            hit += .25*np.sin(2*np.pi*720*t)*np.exp(-60*t)
        a = round(start*sr); b = min(a+len(hit), len(signal))
        signal[a:b] += hit[:b-a]
    peak = max(1, float(np.max(np.abs(signal))))
    return signal/peak*spec['audio']['gain']


def write_click_wav(path, *, lead_s, seconds=0.5):
    """A licensed-asset stand-in: silence, then one click `lead_s` into the file."""
    data = np.zeros(int(SAMPLE_RATE * seconds))
    data[int(lead_s * SAMPLE_RATE):int(lead_s * SAMPLE_RATE) + 48] = 0.8
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SAMPLE_RATE)
        f.writeframes(np.rint(data * 32767).astype('<i2').tobytes())


class ProceduralAudioTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT/'examples/explainer.json').read_text())

    def test_bed_is_unchanged_for_existing_contracts(self):
        track, info = procedural_track(self.spec)
        self.assertTrue(np.array_equal(track, legacy_bed(self.spec)))
        self.assertEqual(info['hits'], [])

    def test_hits_are_placed_by_measured_peak(self):
        spec = copy.deepcopy(self.spec)
        spec['audio']['bed'] = False
        spec['timing']['hits'] = [1.0, {'t': 2.5, 'kind': 'impact'}, {'t': 4.0, 'kind': 'chime'}]
        track, info = procedural_track(spec)
        mono24k = track[::2]
        found = [e['t'] for e in signals.detect_onsets(mono24k, rate=SAMPLE_RATE // 2)]
        self.assertEqual(len(found), 3)
        for a, b in zip(found, [1.0, 2.5, 4.0]):
            self.assertLess(abs(a - b), 0.002)
        self.assertGreater(info['hits'][1]['peak_offset_s'], 0)

    def test_bed_matches_function(self):
        bed = beat_bed(duration=2, bpm=120, offset=0)
        self.assertEqual(len(bed), 2 * SAMPLE_RATE)
        self.assertGreater(np.max(np.abs(bed)), 0.5)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT/'examples/explainer.json').read_text())

    def test_hits_must_be_inside_duration(self):
        self.spec['timing']['hits'] = [8.0]
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_unknown_hit_kind_rejected(self):
        self.spec['timing']['hits'] = [{'t': 1, 'kind': 'explosion'}]
        with self.assertRaises(ValueError):
            validate(self.spec, ROOT)

    def test_mix_layers_need_declared_assets(self):
        self.spec['audio'] = {'mode': 'mix', 'layers': [{'path': 'assets/sfx/undeclared.wav', 'at': 1}]}
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

    def detected(self, track):
        mono = track.mean(axis=1)[::2]
        return [e['t'] for e in signals.detect_onsets(mono, rate=SAMPLE_RATE // 2)]

    def test_peak_alignment_ignores_file_lead_in(self):
        track, info = mix_track(self.spec('peak'), self.root)
        self.assertAlmostEqual(self.detected(track)[0], 0.5, delta=0.002)
        self.assertAlmostEqual(info['layers'][0]['peak_offset_s'], 0.1, delta=0.001)
        track, _ = mix_track(self.spec('start'), self.root)
        self.assertAlmostEqual(self.detected(track)[0], 0.6, delta=0.002)

    def test_ceiling_limits_gain_and_is_reported(self):
        track, _ = mix_track(self.spec('peak'), self.root)
        mastered, report = master(track, target=-6, ceiling_dbfs=-3)
        self.assertTrue(report['limited_by_ceiling'])
        self.assertLessEqual(20*np.log10(np.max(np.abs(mastered))), -3 + 1e-6)


if __name__ == '__main__':
    unittest.main()
