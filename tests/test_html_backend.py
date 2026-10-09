"""HTML composition backend. Browser tests are opt-in (VCH_TEST_BROWSER=1)."""
import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from vch.backends import create_renderer
from vch.core import canonical, load_contract, resolve_style, validate
from vch.evaluate import evaluate
from vch.pipeline import render

ROOT = Path(__file__).resolve().parents[1]
BROWSER = os.environ.get('VCH_TEST_BROWSER') == '1'

PURE = '''<!doctype html><html><body style="margin:0;background:#101418">
<div id="box" style="position:absolute;width:40px;height:40px;background:#E8EEF4"></div>
<div data-vch-id="title" style="position:absolute;left:24px;top:110px;font:600 28px sans-serif;color:#FFFFFF"><span>Pure</span> <span>time</span></div>
<script>
window.__vch.seek = (t) => {
  document.getElementById('box').style.transform = `translate(${24 + t * 200}px, 40px)`;
};
</script></body></html>'''

IMPURE = PURE.replace("window.__vch.seek = (t) => {", "let calls = 0;\nwindow.__vch.seek = (t) => {\n  document.body.style.background = calls++ % 2 ? '#101418' : '#182028';")

TELEMETRY = '''<!doctype html><html><head><style>
body { margin: 0; background: #FFFFFF; font-family: sans-serif; }
.mask { position: absolute; left: 10px; top: 10px; overflow: hidden; font-size: 30px; }
</style></head><body>
<div class="mask"><span id="hidden" style="display:inline-block;transform:translateY(130%)">Hidden</span></div>
<div id="scaled" style="position:absolute;left:10px;top:60px;font-size:40px;transform:scale(0.5);transform-origin:0 0">Half</div>
<div id="clipped" style="position:absolute;left:150px;top:10px;font-size:30px;clip-path:inset(0 0 100% 0)">Clipped</div>
<div id="faded" style="position:absolute;left:150px;top:60px;font-size:30px;opacity:0.02">Faded</div>
<div data-vch-id="line" style="position:absolute;left:10px;top:110px;font-size:24px"><span>Two</span> <span>words</span></div>
<div id="ink" style="position:absolute;left:180px;top:110px;font-size:24px;color:#000000;background:#FFFFFF">Ink</div>
<svg style="position:absolute;left:0;top:0" width="320" height="180"><text x="230" y="40" font-size="30" fill="#000">Svg</text></svg>
<div id="anim" style="position:absolute;left:0;top:150px;font-size:16px;animation:slide 1s linear both">Slide</div>
<style>@keyframes slide { from { transform: translateX(0px); } to { transform: translateX(100px); } }</style>
<canvas id="gl" width="8" height="8" style="position:absolute;right:0;bottom:0"></canvas>
<script>
const gl = document.getElementById('gl').getContext('webgl');
window.__timelines = { main: { paused: false, pause() { this.paused = true; }, seek(t) { document.getElementById('anim').dataset.t = t; } } };
window.__vch.seek = (t) => { gl.clearColor(1, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT); };
</script></body></html>'''

NETWORK = PURE.replace('<script>', '<script>fetch("https://example.com/beacon").catch(() => {});')
CONSOLE_ERROR = PURE.replace("window.__vch.seek = (t) => {", "window.__vch.seek = (t) => {\n  if (t > 0.4) console.error('shader failed to compile');")
LIBRARY = PURE.replace('<script>', '<script type="module">import { lerp } from "/lib/motion.js"; window.__lerp = lerp;</script><script>')
UNDECLARED = PURE.replace('<script>', '<img src="/secret.png" style="display:none"><script>')
# Composition-authored sound: a short click whose loudest sample lands on each cue.
SOUND = PURE.replace('</script>', '''window.__vch.audio = ({ sampleRate, duration }) => {
  const samples = new Float32Array(Math.round(sampleRate * duration));
  for (const at of [0.25, 0.75]) {
    const start = Math.round(at * sampleRate);
    for (let i = 0; i < 960; i++) samples[start + i] = 0.5 * Math.sin(2 * Math.PI * 3000 * i / sampleRate) * Math.exp(-400 * i / sampleRate);
  }
  return [samples, samples];
};
</script>''')
SHORT_SOUND = SOUND.replace('Math.round(sampleRate * duration)', 'Math.round(sampleRate * duration) - 1')


def contract(**changes):
    spec = {'version': 1, 'title': 'html fixture', 'seed': 5, 'backend': 'html',
            'html': {'entry': 'comp/index.html'},
            'video': {'width': 320, 'height': 180, 'fps': 10, 'duration': 1},
            'scenes': [{'id': 'a', 'start': 0, 'end': 0.5}, {'id': 'b', 'start': 0.5, 'end': 1}],
            'audio': {'mode': 'none'}, 'qa': {'sample_every': 0.5},
            'requirements': [
                {'id': 'SEEK', 'description': 'pure', 'kind': 'hard', 'metric': 'determinism_mismatches', 'op': 'eq', 'target': 0},
                {'id': 'COPY', 'description': 'copy', 'kind': 'proxy', 'metric': 'text_present', 'params': {'strings': ['Pure time']}, 'op': 'eq', 'target': True},
                {'id': 'FONT', 'description': 'size', 'kind': 'proxy', 'metric': 'minimum_text_size_px', 'op': 'ge', 'target': 24},
                {'id': 'CONTRAST', 'description': 'contrast', 'kind': 'proxy', 'metric': 'minimum_contrast', 'op': 'ge', 'target': 4.5},
                {'id': 'OVERLAP', 'description': 'overlap', 'kind': 'proxy', 'metric': 'text_overlap_violations', 'op': 'eq', 'target': 0}]}
    spec.update(changes)
    return spec


class Project:
    def __init__(self, html):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'comp').mkdir()
        (self.root/'comp/index.html').write_text(html)

    def close(self):
        self.temp.cleanup()


class HtmlContractTests(unittest.TestCase):
    def setUp(self):
        self.project = Project(PURE)

    def tearDown(self):
        self.project.close()

    def test_valid_without_scene_modules(self):
        validate(contract(), self.project.root)

    def test_missing_entry_rejected(self):
        with self.assertRaises(ValueError):
            validate(contract(html={'entry': 'comp/missing.html'}), self.project.root)

    def test_entry_at_project_root_rejected(self):
        (self.project.root/'index.html').write_text(PURE)
        with self.assertRaises(ValueError):
            validate(contract(html={'entry': 'index.html'}), self.project.root)

    def test_undeclared_media_in_composition_rejected(self):
        (self.project.root/'comp/photo.png').write_bytes(b'not really a png')
        with self.assertRaises(ValueError):
            validate(contract(), self.project.root)
        spec = contract(assets=[{'path': 'comp/photo.png', 'source': 'own photo', 'license': 'owned by tester'}])
        validate(spec, self.project.root)

    def test_style_pack_is_inlined_and_validated(self):
        spec = json.loads((ROOT/'examples/how-code-becomes-video.json').read_text())
        spec['style'] = 'styles/paper-swiss.json'
        checked = validate(copy.deepcopy(spec), ROOT)
        self.assertEqual(checked['style']['mode'], 'light')
        self.assertEqual(checked['style']['source'], 'styles/paper-swiss.json')
        for bad in ({'mode': 'sepia'}, {'color': {'ink': '#12345'}}, '../outside.json', 'styles/missing.json', 7):
            broken = copy.deepcopy(spec)
            broken['style'] = bad
            with self.assertRaises(ValueError, msg=bad):
                validate(broken, ROOT)

    def test_library_folder_assets_must_be_real_folders(self):
        spec = json.loads((ROOT/'examples/three-prism.json').read_text())
        self.assertEqual(validate(copy.deepcopy(spec), ROOT)['html']['entry'], 'compositions/three-prism/index.html')
        for path in ('compositions/_vendor/missing/', 'compositions/_vendor/three/LICENSE/', '.github/'):
            broken = copy.deepcopy(spec)
            broken['assets'][2]['path'] = path
            with self.assertRaises(ValueError, msg=path):
                validate(broken, ROOT)


@unittest.skipUnless(BROWSER and shutil.which('ffmpeg'), 'Set VCH_TEST_BROWSER=1 after browser setup')
class HtmlBrowserTests(unittest.TestCase):
    def render(self, html, name, **changes):
        project = Project(html)
        self.addCleanup(project.close)
        spec = contract(**changes)
        validate(spec, project.root)
        out = render(spec, project.root, project.root/'runs'/name, True)
        return {r['id']: r for r in evaluate(out)['requirements']}, out

    def test_pure_composition_passes_and_reports_grouped_copy(self):
        rows, out = self.render(PURE, 'pure')
        for key, row in rows.items():
            self.assertEqual(row['status'], 'pass', (key, row))
        manifest = json.loads((out/'manifest.json').read_text())
        self.assertIn('html-composition', manifest['runtime']['renderer']['name'])

    def test_console_error_blocks_the_render(self):
        with self.assertRaisesRegex(RuntimeError, 'console.error: shader failed'):
            self.render(CONSOLE_ERROR, 'console')

    def test_declared_library_folder_is_served_and_others_are_not(self):
        project = Project(LIBRARY)
        self.addCleanup(project.close)
        (project.root/'lib').mkdir()
        (project.root/'lib/motion.js').write_text('export const lerp = (a, b, p) => a + (b - a) * p;\n')
        library = {'path': 'lib/', 'source': 'test fixture', 'license': 'MIT'}
        spec = contract(assets=[library])
        validate(spec, project.root)
        rows = {r['id']: r for r in evaluate(render(spec, project.root, project.root/'runs/lib', True))['requirements']}
        self.assertEqual(rows['SEEK']['status'], 'pass')
        with self.assertRaisesRegex(ValueError, 'missing or outside'):
            render(contract(), project.root, project.root/'runs/nolib', True)

    def test_three_clip_seeks_purely(self):
        spec, root = load_contract(ROOT/'examples/three-pulse.json')
        renderer = create_renderer(spec, root, True)
        try:
            seen = {}
            for t in (1.0, 4.5, 2.25, 4.5, 1.0, 2.25):
                frame = renderer.render(t)
                key = hashlib.sha256(frame.image.tobytes() + canonical(frame.elements).encode()).hexdigest()
                self.assertEqual(seen.setdefault(t, key), key, f'seek order changed t={t}')
        finally:
            renderer.close()

    def test_state_carried_between_frames_is_detected(self):
        rows, _ = self.render(IMPURE, 'impure')
        self.assertEqual(rows['SEEK']['status'], 'fail')
        self.assertGreater(rows['SEEK']['value'], 0)

    def test_network_request_blocks_render(self):
        with self.assertRaisesRegex(ValueError, 'non-local'):
            self.render(NETWORK, 'network')

    def test_undeclared_local_file_blocks_render(self):
        project = Project(UNDECLARED)
        self.addCleanup(project.close)
        (project.root/'secret.png').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'outside its folder'):
            render(contract(), project.root, project.root/'runs/undeclared', True)

    def test_telemetry_semantics_and_adapters(self):
        from vch.html_backend import HtmlRenderer
        project = Project(TELEMETRY)
        self.addCleanup(project.close)
        spec = contract()
        renderer = HtmlRenderer(spec, project.root, True)
        try:
            frame = renderer.sampled(0.5)
            by_text = {e['text']: e for e in frame.elements}
            for invisible in ('Hidden', 'Clipped', 'Faded'):
                self.assertNotIn(invisible, by_text)
            self.assertAlmostEqual(by_text['Half']['size'], 20, delta=1.0)
            self.assertAlmostEqual(by_text['Svg']['size'], 30, delta=1.5)
            self.assertGreater(by_text['Ink']['contrast'], 15)
            self.assertEqual(by_text['Two words']['type'], 'text-group')
            self.assertAlmostEqual(by_text['Slide']['bbox'][0], 50, delta=1.0)  # CSS animation seeked to 0.5 s
            self.assertEqual(renderer.page.evaluate("document.getElementById('anim').dataset.t"), '0.5')
            pixel = np.asarray(frame.image)[-2, -2]
            self.assertEqual(tuple(int(v) for v in pixel), (255, 0, 0))  # WebGL canvas captured
        finally:
            renderer.close()

    def test_temporal_samples_blur_deterministically(self):
        from vch.html_backend import HtmlRenderer
        project = Project(PURE)
        self.addCleanup(project.close)
        def frames(spec, count):
            renderer = HtmlRenderer(spec, project.root, True)  # one Playwright session per thread at a time
            try:
                return [np.asarray(renderer.sampled(0.3).image) for _ in range(count)]
            finally:
                renderer.close()
        sharp = frames(contract(), 1)[0]
        blurred = frames(contract(render={'samples': 3, 'shutter': 0.9}), 2)
        self.assertFalse(np.array_equal(sharp, blurred[0]))
        self.assertTrue(np.array_equal(blurred[0], blurred[1]))

    def test_composition_audio_is_synthesized_in_the_page(self):
        sound = {'mode': 'composition'}
        hits = {'hits': [{'t': 0.25, 'cue': 'first'}, {'t': 0.75, 'cue': 'second'}]}
        extra = [{'id': 'AUDIO', 'description': 'sound', 'kind': 'hard', 'metric': 'audio_present', 'op': 'eq', 'target': True},
                 {'id': 'HITS', 'description': 'sync', 'kind': 'proxy', 'metric': 'audio_hit_sync_ms', 'op': 'le', 'target': 20}]
        rows, out = self.render(SOUND, 'sound', audio=sound, timing=hits, requirements=contract()['requirements'] + extra)
        for key, row in rows.items():
            self.assertEqual(row['status'], 'pass', (key, row))
        evidence = json.loads((out/'evidence.json').read_text())
        self.assertEqual(evidence['audio_render']['mode'], 'composition')
        self.assertEqual(evidence['audio_render']['channels'], 2)

    def test_composition_audio_must_exist_and_fill_the_film(self):
        with self.assertRaisesRegex(RuntimeError, 'window.__vch.audio'):
            self.render(PURE, 'no-audio', audio={'mode': 'composition'})
        with self.assertRaisesRegex(RuntimeError, 'Float32Arrays of 48000 samples'):
            self.render(SHORT_SOUND, 'short-audio', audio={'mode': 'composition'})

    def test_example_clip_opening_passes_its_checks(self):
        spec = json.loads((ROOT/'examples/three-pulse.json').read_text())
        spec['video'].update(fps=10, duration=3)
        spec['scenes'] = [{**spec['scenes'][0], 'end': 3}]
        spec['timing']['hits'] = [h for h in spec['timing']['hits'] if h['t'] < 3]
        keep = {'SEEK', 'AUDIO', 'FONT', 'CONTRAST', 'SAFE', 'OVERLAP', 'POPS', 'HITS'}
        spec['requirements'] = [r for r in spec['requirements'] if r['id'] in keep]
        with tempfile.TemporaryDirectory() as d:
            out = render(copy.deepcopy(spec), ROOT, Path(d)/'run', True)
            result = evaluate(out)
        self.assertTrue(result['machine_ok'], [r for r in result['requirements'] if r['status'] != 'pass'])

    def test_dense_example_loads_its_sources_and_seeks_purely(self):
        spec, root = load_contract(ROOT/'examples/how-code-becomes-video.json')
        renderer = create_renderer(spec, root, True)
        try:
            order = [0.0, 9.9, 21.9, 46.0, 21.9, 0.0, 46.0, 9.9]
            shots = {}
            for t in order:
                frame = renderer.render(t)
                key = hashlib.sha256(frame.image.tobytes() + canonical(frame.elements).encode()).hexdigest()
                self.assertEqual(shots.setdefault(t, key), key, f'seek order changed t={t}')
            texts = ' '.join(e['text'] for e in renderer.render(9.9).elements if e.get('type') in ('text', 'text-group'))
        finally:
            renderer.close()
        # Counts on screen come from the contract and the corpus file, not from literals in the composition.
        self.assertIn(f"{len(spec['requirements'])} requirements, frozen before the render", texts)
        self.assertIn('frame 0297 / 1,440', texts)

    def test_style_pack_reskins_the_same_film(self):
        spec, root = load_contract(ROOT/'examples/how-code-becomes-video.json')
        luma = {}
        for name in ('night-blueprint', 'paper-swiss'):
            styled = copy.deepcopy(spec)
            styled['style'] = resolve_style(f'styles/{name}.json', root)
            renderer = create_renderer(styled, root, True)
            try:
                frame = renderer.render(9.9)
            finally:
                renderer.close()
            luma[name] = float(np.asarray(frame.image.convert('L')).mean()) / 255
            texts = ' '.join(e['text'] for e in frame.elements if e.get('type') == 'text')
            self.assertIn('The prompt reads', texts)
        self.assertLess(luma['night-blueprint'], 0.25)
        self.assertGreater(luma['paper-swiss'], 0.7)


if __name__ == '__main__':
    unittest.main()
