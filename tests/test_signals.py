import shutil
import unittest

import numpy as np

from vch import signals
from vch.audio import SAMPLE_RATE, hit_sound, place

RATE = signals.ANALYSIS_SAMPLE_RATE


def click_track(times, seconds, kind='tick'):
    track = np.zeros(int(RATE * seconds))
    for t in times:
        place(track, hit_sound(kind, rate=RATE), at=t, align='peak', rate=RATE)
    return track


class DensityTests(unittest.TestCase):
    def test_flat_frame_has_no_detail(self):
        flat = np.full((90, 160, 3), 40, dtype=np.uint8)
        density = signals.frame_density(flat)
        self.assertEqual(density['edge_density'], 0.0)
        self.assertEqual(density['used_cells'], 0.0)
        self.assertAlmostEqual(density['colourfulness'], 0.0)

    def test_detail_in_one_corner_uses_few_cells(self):
        frame = np.full((90, 160, 3), 20, dtype=np.uint8)
        frame[5:20, 5:25:2] = 230  # thin vertical strokes, like text, in one grid cell
        corner = signals.frame_density(frame)
        frame[:, ::4] = 230        # strokes across the whole frame
        spread = signals.frame_density(frame)
        self.assertGreater(corner['edge_density'], 0)
        self.assertLess(corner['used_cells'], 0.1)
        self.assertEqual(spread['used_cells'], 1.0)
        self.assertGreater(spread['edge_density'], corner['edge_density'])

    def test_colourfulness_orders_grey_below_saturated(self):
        grey = np.full((90, 160, 3), 128, dtype=np.uint8)
        vivid = grey.copy()
        vivid[:, :80] = (230, 40, 40)
        vivid[:, 80:] = (40, 60, 230)
        self.assertGreater(signals.frame_density(vivid)['colourfulness'], 50)
        self.assertAlmostEqual(signals.frame_density(grey)['colourfulness'], 0.0)


class OnsetTests(unittest.TestCase):
    def test_onsets_land_on_measured_peaks(self):
        times = [0.0, 0.5, 1.25, 2.0]
        found = [e['t'] for e in signals.detect_onsets(click_track(times, 3), rate=RATE)]
        self.assertEqual(len(found), len(times))
        for a, b in zip(found, times):
            self.assertLess(abs(a - b), 0.002)

    def test_tempo_and_phase_from_click_train(self):
        times = list(np.arange(0.1, 12, 0.5))
        track = click_track(times, 12.5)
        onsets = signals.detect_onsets(track, rate=RATE)
        tempo = signals.estimate_tempo(track, rate=RATE, onsets=onsets)
        self.assertAlmostEqual(tempo['bpm'], 120, delta=0.2)
        self.assertAlmostEqual(tempo['beat_offset_s'], 0.1, delta=0.005)

    def test_silence_has_no_onsets(self):
        self.assertEqual(signals.detect_onsets(np.zeros(RATE * 2), rate=RATE), [])


class MotionSignalTests(unittest.TestCase):
    fps = 10

    def test_static_hold_and_exclusion(self):
        diff = [0] + [5] * 9 + [0] * 20 + [5] * 10
        hold, start = signals.longest_still_hold(diff, fps=self.fps)
        self.assertAlmostEqual(hold, 2.0)
        self.assertAlmostEqual(start, 0.9)
        hold, _ = signals.longest_still_hold(diff, fps=self.fps, exclude=[[1.0, 3.0]])
        self.assertLess(hold, 0.2)

    def test_one_frame_pop_is_not_a_cut(self):
        # Frame 5 differs from both neighbours; frame 15 is a hard cut that stays changed.
        diff = [0] * 30
        bridge = [0] * 30
        diff[5], diff[6] = 40, 40
        diff[15], bridge[15], bridge[16] = 40, 40, 40
        self.assertEqual(signals.single_frame_pops(diff, bridge, fps=self.fps), [0.5])
        self.assertEqual(signals.single_frame_pops(diff, bridge, fps=self.fps, exclude=[[0.4, 0.6]]), [])

    def test_small_flicker_below_floor_ignored(self):
        diff, bridge = [0, 3, 3, 0], [0, 0, 0.5, 0]
        self.assertEqual(signals.single_frame_pops(diff, bridge, fps=self.fps), [])

    def test_loop_seam_ratio(self):
        motion = {'diff': [0] + [4.0] * 20, 'loop_seam': 0.0}
        self.assertEqual(signals.loop_seam_ratio(motion, fps=self.fps), 0.0)
        motion['loop_seam'] = 40.0
        self.assertAlmostEqual(signals.loop_seam_ratio(motion, fps=self.fps), 10.0)

    def test_exclusion_windows_validated(self):
        for bad in ([[2, 1]], [[0, float('nan')]], [1, 2], 'x'):
            with self.assertRaises(ValueError):
                signals.check_windows(bad)


class OverlapTests(unittest.TestCase):
    def box(self, id_, rect, type_='text'):
        return {'id': id_, 'type': type_, 'bbox': rect}

    def test_overlap_threshold_and_exclusions(self):
        a = self.box('a', [0, 0, 100, 40])
        self.assertEqual(signals.overlap_pairs([a, self.box('b', [50, 0, 150, 40])]), [('a', 'b')])
        self.assertEqual(signals.overlap_pairs([a, self.box('b', [90, 0, 190, 40])]), [])
        self.assertEqual(signals.overlap_pairs([a, self.box('a', [0, 0, 100, 40])]), [])
        self.assertEqual(signals.overlap_pairs([a, self.box('g', [0, 0, 100, 40], 'text-group')]), [])
        self.assertEqual(signals.overlap_pairs([a, self.box('b', [50, 0, 150, 40])], ignore={'b'}), [])

    def test_line_fragments_used_when_present(self):
        wrapped = {'id': 'p', 'type': 'text', 'bbox': [0, 0, 300, 80], 'rects': [[0, 0, 300, 40], [0, 40, 60, 80]]}
        self.assertEqual(signals.overlap_pairs([wrapped, self.box('q', [200, 45, 300, 80])]), [])


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
class LoudnessTests(unittest.TestCase):
    def test_sine_loudness_matches_bs1770(self):
        t = np.arange(SAMPLE_RATE * 3) / SAMPLE_RATE
        sine = 0.1 * np.sin(2 * np.pi * 1000 * t)  # -20 dBFS peak 1 kHz -> -23 LUFS
        result = signals.loudness_of_samples(sine, rate=SAMPLE_RATE)
        self.assertAlmostEqual(result['integrated_lufs'], -23.0, delta=0.3)
        self.assertAlmostEqual(result['true_peak_dbtp'], -20.0, delta=0.3)


if __name__ == '__main__':
    unittest.main()
