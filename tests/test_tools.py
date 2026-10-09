import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from fakes import FakeRenderer, clicks, html_project
from vch.pipeline import _render
from vch.tools import (compare_profiles, diversity_markdown, preview_sound, profile_media, render_stills, still_times,
                       storyboard_markdown)

ROOT = Path(__file__).resolve().parents[1]
CLICK_TIMES = [0.25, 0.75, 1.25, 1.75]


def sliding_bar(t):
    image = Image.new('RGB', (96, 96), '#334455')
    ImageDraw.Draw(image).rectangle((5 + t * 20, 30, 25 + t * 20, 50), fill='#EEEEEE')
    return image


class CompareProfilesTests(unittest.TestCase):
    def test_table_lists_both_values_and_ratio(self):
        first = {'input': 'reference.mp4', 'video': {'duration_s': 30.0, 'density': {'edge_density': {'median': 0.08}}},
                 'audio': {'integrated_lufs': -14.0}}
        second = {'input': 'candidate.mp4', 'video': {'duration_s': 15.0, 'density': {'edge_density': {'median': 0.04}}},
                  'audio': {'integrated_lufs': -16.0}}
        table = compare_profiles(first, second)
        self.assertIn('| duration (s) | 30.0 | 15.0 | 0.50 |', table)
        self.assertIn('| edge density, median | 0.08 | 0.04 | 0.50 |', table)
        # Ratios of logarithmic units would mislead, so loudness rows show values only.
        self.assertIn('| integrated loudness (LUFS) | -14.0 | -16.0 |  |', table)
        self.assertIn('not to grade', table)

    def test_missing_values_stay_blank(self):
        table = compare_profiles({'input': 'a'}, {'input': 'b', 'video': {'cuts_per_10s': 1.0}})
        self.assertIn('| hard cuts per 10 s |  | 1.0 |  |', table)


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT/'examples/how-code-becomes-video.json').read_text())

    def test_storyboard_lists_scenes_beats_and_cues(self):
        text = storyboard_markdown(self.spec)
        self.assertIn('| 2 | brief | 6–12 | 12 | 6 brief.arrive, 6.5 brief.row1, 6.75 brief.row2,', text)
        self.assertIn('audio `composition`', text)
        self.assertIn('Human `CRAFT`', text)

    def test_still_times(self):
        self.assertEqual(len(still_times(self.spec, beats=True)), 96)
        self.assertEqual(still_times(self.spec, times=[1.01]), [1.0])
        self.assertAlmostEqual(max(still_times(self.spec)), 1439/30)
        with self.assertRaises(ValueError):
            still_times(self.spec, times=[48.0])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class StillsSoundAndProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.spec = {'version': 1, 'title': 'tools', 'seed': 1, **html_project(cls.root),
                    'video': {'width': 96, 'height': 96, 'fps': 10, 'duration': 2},
                    'scenes': [{'id': 'a', 'start': 0, 'end': 1}, {'id': 'b', 'start': 1, 'end': 2}],
                    'audio': {'mode': 'composition'},
                    'timing': {'bpm': 120, 'hits': [{'t': t, 'cue': f'c{i}'} for i, t in enumerate(CLICK_TIMES)]},
                    'qa': {'sample_every': 1},
                    'requirements': [{'id': 'D', 'description': 'd', 'kind': 'hard', 'metric': 'duration_s', 'op': 'eq', 'target': 2}]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def renderer(self, times=CLICK_TIMES):
        return FakeRenderer(sliding_bar, audio=clicks(times=times, duration=2))

    def render(self, name):
        return _render(self.spec, self.root, self.root/'runs'/name, self.renderer())

    def test_stills_sheet_and_no_overwrite(self):
        out = self.root/'stills'
        with patch('vch.tools.create_renderer', return_value=self.renderer()):
            summary = render_stills(self.spec, self.root, out, times=still_times(self.spec), trust_code=True)
            self.assertEqual([s['scene'] for s in summary['stills']], ['a', 'a', 'b', 'b', 'b'])
            self.assertTrue((out/'sheet.jpg').is_file())
            self.assertEqual(json.loads((out/'stills.json').read_text())['stills'][0]['t'], 0.0)
            with self.assertRaises(FileExistsError):
                render_stills(self.spec, self.root, out, times=[0.0], trust_code=True)

    def test_stills_report_next_frame_change(self):
        with patch('vch.tools.create_renderer', return_value=self.renderer()):
            summary = render_stills(self.spec, self.root, self.root/'stills-motion', times=[0.5, 1.9], trust_code=True, motion=True)
        self.assertGreater(summary['stills'][0]['frame_change'], 0)
        self.assertNotIn('frame_change', summary['stills'][1])  # no next frame inside the film

    def test_sound_preview_finds_placed_cues_and_reports_misses(self):
        with patch('vch.tools.create_renderer', return_value=self.renderer()):
            summary = preview_sound(self.spec, self.root, self.root/'sound', trust_code=True)
        self.assertEqual(summary['onsets'], 4)
        self.assertLess(summary['worst_hit_ms'], 2)
        self.assertEqual(summary['missed'], [])
        self.assertTrue((self.root/'sound/audio.wav').is_file())
        with patch('vch.tools.create_renderer', return_value=self.renderer(times=CLICK_TIMES[:3])):
            summary = preview_sound(self.spec, self.root, self.root/'sound-missing', trust_code=True)
        self.assertEqual([h['cue'] for h in summary['missed']], ['c3'])

    def test_diversity_of_a_render_with_itself_is_zero(self):
        run = self.render('diverse')
        table = diversity_markdown([run, run/'video.mp4'])
        self.assertIn('| diverse | 0.00 | 0.00 |', table)
        with self.assertRaises(ValueError):
            diversity_markdown([run])

    def test_profile_of_a_render_recovers_onsets_and_frames(self):
        run = self.render('profiled')
        profile = profile_media(run/'video.mp4', self.root/'profile')
        self.assertAlmostEqual(profile['video']['duration_s'], 2.0, delta=0.05)
        self.assertEqual(len(profile['audio']['onsets']), 4)
        self.assertTrue((self.root/'profile/contact.jpg').is_file())
        density = profile['video']['density']
        self.assertGreater(density['frames'], 0)
        self.assertGreater(density['edge_density']['median'], 0)
        self.assertTrue((self.root/'profile/timeline.png').is_file())
        audio_only = profile_media(run/'audio.wav', self.root/'profile-audio')
        self.assertNotIn('video', audio_only)
        self.assertEqual(len(audio_only['audio']['onsets']), 4)


if __name__ == '__main__':
    unittest.main()
