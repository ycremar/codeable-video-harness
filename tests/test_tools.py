import json
import shutil
import tempfile
import unittest
from pathlib import Path

from vch.pipeline import render
from vch.tools import profile_media, render_stills, still_times, storyboard_markdown

ROOT = Path(__file__).resolve().parents[1]
SCENE = 'from vch.core import Canvas\ndef render(ctx):\n c=Canvas(96,96,"#334455")\n c.draw.rectangle((5+ctx["t"]*20,30,25+ctx["t"]*20,50),fill="#EEEEEE")\n return c.finish()\n'


class StoryboardTests(unittest.TestCase):
    def test_storyboard_lists_scenes_beats_and_hits(self):
        spec = json.loads((ROOT/'examples/html.json').read_text())
        text = storyboard_markdown(spec)
        self.assertIn('| 2 | contract | 2–4 | 4 | 2 impact, 2.5 tick, 3 tick, 3.5 tick |', text)
        self.assertIn('Human `CRAFT`', text)

    def test_still_times(self):
        spec = json.loads((ROOT/'examples/html.json').read_text())
        self.assertEqual(len(still_times(spec, beats=True)), 24)
        self.assertEqual(still_times(spec, times=[1.01]), [1.0])
        self.assertAlmostEqual(max(still_times(spec)), 359/30)
        with self.assertRaises(ValueError):
            still_times(spec, times=[12.0])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class StillsAndProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        (cls.root/'scene.py').write_text(SCENE)
        cls.spec = {'version': 1, 'title': 'tools', 'seed': 1, 'video': {'width': 96, 'height': 96, 'fps': 10, 'duration': 2},
                    'scenes': [{'id': 'a', 'start': 0, 'end': 1, 'module': 'scene.py'},
                               {'id': 'b', 'start': 1, 'end': 2, 'module': 'scene.py'}],
                    'audio': {'mode': 'procedural', 'gain': 0.5, 'bed': True}, 'timing': {'bpm': 120},
                    'qa': {'sample_every': 1},
                    'requirements': [{'id': 'D', 'description': 'd', 'kind': 'hard', 'metric': 'duration_s', 'op': 'eq', 'target': 2}]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_stills_sheet_and_no_overwrite(self):
        out = self.root/'stills'
        summary = render_stills(self.spec, self.root, out, times=still_times(self.spec), trust_code=True)
        self.assertEqual([s['scene'] for s in summary['stills']], ['a', 'a', 'b', 'b', 'b'])
        self.assertTrue((out/'sheet.jpg').is_file())
        self.assertEqual(json.loads((out/'stills.json').read_text())['stills'][0]['t'], 0.0)
        with self.assertRaises(FileExistsError):
            render_stills(self.spec, self.root, out, times=[0.0], trust_code=True)

    def test_profile_of_a_render_recovers_tempo_and_frames(self):
        run = render(self.spec, self.root, self.root/'runs/profiled', True)
        profile = profile_media(run/'video.mp4', self.root/'profile')
        self.assertAlmostEqual(profile['video']['duration_s'], 2.0, delta=0.05)
        self.assertEqual(len(profile['audio']['onsets']), 4)
        self.assertTrue((self.root/'profile/contact.jpg').is_file())
        self.assertTrue((self.root/'profile/timeline.png').is_file())
        audio_only = profile_media(run/'audio.wav', self.root/'profile-audio')
        self.assertNotIn('video', audio_only)
        self.assertEqual(len(audio_only['audio']['onsets']), 4)


if __name__ == '__main__':
    unittest.main()
