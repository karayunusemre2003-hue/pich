import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / 'scripts' / 'render_reel.py'
SPEECH = ROOT / 'scripts' / 'speech_map.py'
DEMO = ROOT / 'examples' / 'demo'
DEMO_GRAPH = ROOT / 'tests' / 'fixtures' / 'demo.filter_graph.txt'
sys.path.insert(0, str(ROOT / 'scripts'))
from render_reel import Timeline  # noqa: E402


def make_source(p, dur=6):
    """Vertical synthetic camera: tone during 0.5-2.5 s and 3.5-5.5 s, silence elsewhere."""
    src = p / 'source.mp4'
    tone = "sin(2*PI*440*t)*0.4*(between(t\\,0.5\\,2.5)+between(t\\,3.5\\,5.5))"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=size=540x960:rate=30:duration={dur}',
                    '-f', 'lavfi', '-i', f'aevalsrc={tone}:s=48000:d={dur}', '-c:v', 'libx264', '-pix_fmt', 'yuvj420p',
                    '-c:a', 'aac', '-shortest', str(src)], check=True)
    return src


def reel_plan(src):
    return {'source': str(src), 'fps': 30, 'width': 1080, 'height': 1920, 'source_size': [540, 960],
            'edl': [{'start': 0.3, 'end': 2.7}, {'start': 3.3, 'end': 5.7, 'zoom': 1.06, 'volume': 0.5}],
            'slide': {'start': {'seg': 1, 't': 'start'}, 'end': {'seg': 1, 't': 'end'},
                      'eyebrow': 'TEST', 'title': ['Birinci', 'ikinci'],
                      'steps': [{'icon': 'image', 'label': 'Adım bir', 'at': {'seg': 1, 't': 'start'}},
                                {'icon': 'code', 'label': 'Adım iki', 'at': {'seg': 1, 't': 4.5}}],
                      'pip': {'box': [584, 540, 440, 600], 'crop': [160, 130, 760, 1038]}},
            'layers': [{'kind': 'hook_card', 'eyebrow': 'KANCA', 'from_text': 'Buradan', 'to_text': 'oraya',
                        'y': 96, 'from': 'start', 'to': {'seg': 0, 't': 'end', 'offset': -0.05}, 'fade_out': 0.2},
                       {'kind': 'cta_card', 'lines': ['Satır bir', 'satır iki'], 'pill': 'Yorumlara yaz',
                        'y': 1250, 'from': {'seg': 1, 't': 5.0}, 'to': 'end', 'fade_in': 0.2, 'rise': 20}],
            'captions': {'items': [{'seg': 0, 'start': 0.5, 'end': 1.5, 'text': 'Merhaba dünya', 'hl': ['dünya']},
                                   {'seg': 0, 'start': 1.6, 'end': 2.5, 'text': 'İkinci satır'}]},
            'audio': {'music': {'synth': 'pad', 'gain_db': -17},
                      'sfx': [{'synth': 'whoosh', 'at': {'slide': 'start', 'offset': -0.3}, 'gain_db': -21},
                              {'synth': 'chime', 'at': {'seg': 1, 't': 5.0}, 'gain_db': -20}]}}


class TimelineTest(unittest.TestCase):
    def test_source_time_maps_and_clamps_inside_segment(self):
        tl = Timeline([{'start': 1.0, 'end': 2.0}, {'start': 5.0, 'end': 6.0}], 30)
        self.assertEqual(tl.total, 60)
        self.assertAlmostEqual(tl.o(5.5, 1), 1.5)
        self.assertAlmostEqual(tl.o(9.0, 1), 2.0)   # clamped to segment end
        self.assertAlmostEqual(tl.o(0.0, 1), 1.0)   # clamped to segment start
        self.assertAlmostEqual(tl.t({'seg': 1, 't': 'end', 'offset': -0.05}), 1.95)

    def test_empty_segment_rejected(self):
        with self.assertRaises(ValueError):
            Timeline([{'start': 2.0, 'end': 2.0}], 30)


class RenderReelTest(unittest.TestCase):
    def test_full_plan_renders_with_qa_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p)
            (p / 'plan.json').write_text(json.dumps(reel_plan(src)))
            out = p / 'reel.mp4'
            subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(out), '--preview'], check=True, capture_output=True)
            qa = json.loads((p / 'reel.qa.json').read_text())
            self.assertEqual(qa['status'], 'REVIEW')
            self.assertEqual(qa['frames'], 144)
            self.assertTrue(qa['checks']['frames_ok'] and qa['checks']['av_ok'])
            self.assertEqual(qa['color_range'], 'tv')
            self.assertLess(abs(qa['lufs_i'] + 14), 2.5)
            man = json.loads((p / 'build' / 'plan_manifest.json').read_text())
            self.assertEqual([round(t, 3) for t in man['slide']['steps']], [2.4, 3.6])
            r = subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(out)], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('refuse to overwrite', r.stderr)

    def test_external_music_requires_rights_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p, 3)
            plan = reel_plan(src); plan.pop('slide'); plan['layers'] = []
            plan['edl'] = [{'start': 0.3, 'end': 2.7}]; plan['captions'] = {'items': []}
            plan['audio'] = {'music': {'file': str(src), 'gain_db': -20}}
            (p / 'plan.json').write_text(json.dumps(plan))
            r = subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'o.mp4')], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('rights_checked', r.stderr)

    def test_demo_plan_reproduces_golden_filter_graph(self):
        """Any change to graph construction shows up here; regenerate the fixture only on purpose."""
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            for f in ('make_demo.py',):
                (t / f).write_text((DEMO / f).read_text())
            subprocess.run([sys.executable, str(t / 'make_demo.py')], check=True, capture_output=True)
            subprocess.run([sys.executable, str(RENDER), str(t / 'plan.json'), str(t / 'x.mp4'), '--graph-only'], check=True, capture_output=True)
            self.assertEqual((t / 'build' / 'work' / 'filter_graph.txt').read_text(), DEMO_GRAPH.read_text())

    def test_invalid_plans_rejected_before_work(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p, 3)
            cases = [({'width': 720}, '1080x1920'), ({'source_range': 'pc,drawtext=x'}, 'source_range'),
                     ({'audio': {'music': {'file': str(src), 'rights_checked': 'false'}}}, 'rights_checked'),
                     ({'audio': {'sfx': [{'synth': 'whoosh', 'at': 'start', 'gain_db': '0,volume=9'}]}}, 'gain_db'),
                     ({'fps': 25}, 'fps'),  # source is 30 fps
                     ({'layers': [{'kind': 'cta_card', 'lines': ['a', 'b', 'c'], 'pill': 'x', 'y': 1250, 'from': 'start', 'to': 'end'}]}, '2 lines'),
                     ({'layers': [{'kind': 'hook_card', 'eyebrow': 'Ç' * 60, 'from_text': 'a', 'to_text': 'b', 'y': 96, 'from': 'start', 'to': 'end'}]}, 'too long')]
            for patch, needle in cases:
                plan = reel_plan(src); plan.update(patch)
                (p / 'plan.json').write_text(json.dumps(plan))
                r = subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'o.mp4')], capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0, patch)
                self.assertIn(needle, r.stderr, patch)


    def test_until_must_be_positive(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p, 3); (p / 'plan.json').write_text(json.dumps(reel_plan(src)))
            r = subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'o.mp4'), '--until', '0'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0); self.assertIn('--until', r.stderr)


    def test_logo_layer_from_verified_library(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p, 3); plan = reel_plan(src)
            lib = p / 'logos'; lib.mkdir()  # a throwaway library: the repo ships no brand logos
            from PIL import Image
            Image.new('RGBA', (256, 256), (255, 255, 255, 255)).save(lib / 'claude-white.png')
            (lib / 'manifest.json').write_text(json.dumps({'logos': {'claude-white': {
                'file': 'claude-white.png', 'source_url': 'https://example.com/brand', 'verified_at': '2026-01-01'}}}))
            os.environ['PICH_LOGOS_DIR'] = str(lib); self.addCleanup(os.environ.pop, 'PICH_LOGOS_DIR', None)
            plan['layers'] = [{'kind': 'png', 'logo': 'claude-white', 'height': 96, 'y': 300, 'from': 'start', 'to': 'end'}]
            (p / 'plan.json').write_text(json.dumps(plan))
            subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'x.mp4'), '--graph-only'], check=True, capture_output=True)
            man = json.loads((p / 'build' / 'plan_manifest.json').read_text())
            logo = [L for L in man['layers'] if L['kind'] == 'logo'][0]
            self.assertEqual(logo['h'], 96)
            plan['layers'][0]['logo'] = 'krea'  # deliberately not in the library (unclaimed on Brandfetch)
            (p / 'plan.json').write_text(json.dumps(plan))
            r = subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'x.mp4'), '--graph-only'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0); self.assertIn('not in the verified library', r.stderr)

    def test_broll_full_pip_and_card(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p)
            clip = p / 'clip.mp4'  # 25 fps landscape clip: renderer must conform fps and crop to the target
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=25:duration=4', '-c:v', 'libx264', str(clip)], check=True)
            plan = reel_plan(src); plan.pop('slide'); plan['audio']['sfx'] = []
            plan['layers'] = [
                {'kind': 'broll', 'mode': 'full', 'src': str(clip), 'from': {'seg': 0, 't': 1.0}, 'to': {'seg': 0, 't': 2.0}},
                {'kind': 'broll', 'mode': 'full_pip', 'src': str(clip), 'src_start': 0.5, 'from': {'seg': 1, 't': 3.5}, 'to': {'seg': 1, 't': 4.5},
                 'pip': {'box': [584, 540, 440, 600], 'crop': [160, 130, 760, 1038]}},
                {'kind': 'broll', 'mode': 'card', 'src': str(clip), 'width': 500, 'y': 300, 'from': {'seg': 1, 't': 4.6}, 'to': {'seg': 1, 't': 5.6}}]
            (p / 'plan.json').write_text(json.dumps(plan))
            subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'b.mp4'), '--preview'], check=True, capture_output=True)
            man = json.loads((p / 'b.manifest.json').read_text())
            self.assertEqual([w['mode'] for w in man['camera_windows']], ['full', 'full_pip'])
            card = [L for L in man['layers'] if L['kind'] == 'broll_card'][0]
            self.assertEqual((card['w'], card['h']), (500, 280))  # 500*360/640=281.25 -> even
            # the full cutaway replaces the camera: at t=0.8 (inside seg0 window) the frame is the test pattern, not the camera
            def frame(t):
                f = p / f'f{t}.png'; subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', str(p / 'b.mp4'), '-frames:v', '1', str(f)], check=True)
                from PIL import Image
                return Image.open(f).convert('RGB').resize((54, 96))
            cam = frame(0.1); cut = frame(1.2)
            diff = sum(abs(a - b) for pa, pb in zip(cam.getdata(), cut.getdata()) for a, b in zip(pa, pb)) / (54 * 96 * 3)
            self.assertGreater(diff, 20)
            for bad, needle in ((dict(plan['layers'][0], to={'seg': 0, 't': 0.9}), 'empty or reversed'),
                                (dict(plan['layers'][0], fade_in=0.8, fade_out=0.8), 'fades must')):
                (p / 'plan.json').write_text(json.dumps(dict(plan, layers=[bad])))
                r = subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'c.mp4'), '--preview'], capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0); self.assertIn(needle, r.stderr)
            sar = p / 'sar.mp4'  # anamorphic 320x360 with SAR 2:1 displays as 640x360
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x360:rate=25:duration=1', '-vf', 'setsar=2',
                            '-c:v', 'libx264', str(sar)], check=True)
            from render_reel import video_geometry
            self.assertEqual(video_geometry(sar)[:2], (640, 360))
            rot = p / 'rot.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-display_rotation', '90', '-i', str(clip), '-c', 'copy', str(rot)], check=True)
            self.assertEqual(video_geometry(rot)[:2], (360, 640))
            too_long = dict(plan); too_long['layers'] = [dict(plan['layers'][0], to='end')]  # 4.1 s window > 4.0 s clip
            (p / 'plan.json').write_text(json.dumps(too_long))
            r = subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'c.mp4'), '--preview'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0); self.assertIn('longer than the clip', r.stderr)

    def test_iconify_icon_layers(self):
        try: urllib.request.urlopen(urllib.request.Request('https://api.iconify.design/lucide/bell.svg', headers={'User-Agent': 'pich/0.7'}), timeout=10)
        except Exception: self.skipTest('Iconify API unreachable')
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p, 3); plan = reel_plan(src)
            plan['layers'] = [{'kind': 'icon', 'icon': 'lucide:bell', 'size': 96, 'color': 'yellow', 'card': True, 'y': 300, 'from': 'start', 'to': 'end'},
                              {'kind': 'icon', 'icon': 'fluent-emoji-flat:tomato', 'size': 120, 'color': None, 'y': 600, 'from': 'start', 'to': 'end'}]
            (p / 'plan.json').write_text(json.dumps(plan))
            subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'x.mp4'), '--graph-only'], check=True, capture_output=True)
            man = json.loads((p / 'build' / 'plan_manifest.json').read_text())
            self.assertEqual([L['kind'] for L in man['layers'] if L['kind'] == 'icon'], ['icon', 'icon'])
            prov = [o for o in man['overlays'] if o.get('kind') == 'icon']
            self.assertEqual([o['license'] for o in prov], ['ISC', 'MIT'])
            card = [L for L in man['layers'] if L['kind'] == 'icon'][0]
            self.assertGreater(card['w'], 96)  # icon sits on a padded card

    def test_preview_uses_cached_half_res_proxy_for_big_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = p / 'big.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1440x2560:rate=30:duration=3',
                            '-f', 'lavfi', '-i', 'sine=frequency=300:sample_rate=48000:duration=3', '-c:v', 'libx264', '-preset', 'ultrafast',
                            '-c:a', 'aac', '-shortest', str(src)], check=True)
            plan = {'source': str(src), 'source_size': [1440, 2560], 'edl': [{'start': 0.5, 'end': 2.5, 'zoom': 1.06}],
                    'audio': {'loudnorm': {'I': -14, 'TP': -1.5, 'LRA': 9}}}
            (p / 'plan.json').write_text(json.dumps(plan))
            subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'pv.mp4'), '--preview'], check=True, capture_output=True)
            man = json.loads((p / 'pv.manifest.json').read_text())
            self.assertIn('pich/proxy', man['source'])
            self.assertEqual(man['edl'][0]['crop'][:2], [int(720 / 1.06) // 2 * 2, int(1280 / 1.06) // 2 * 2])


class SpeechMapTest(unittest.TestCase):
    def test_finds_speech_and_rejects_cut_inside_speech(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p)
            out = p / 'sm.json'
            subprocess.run([sys.executable, str(SPEECH), str(src), '--out', str(out)], check=True, capture_output=True)
            sm = json.loads(out.read_text())
            self.assertEqual(len(sm['speech']), 2)
            self.assertAlmostEqual(sm['speech'][0][0], 0.5, delta=0.03)
            good = {'fps': 30, 'edl': [{'start': 0.3, 'end': 2.7}]}
            bad = {'fps': 30, 'edl': [{'start': 1.0, 'end': 2.0}]}
            past_eof = {'fps': 30, 'edl': [{'start': 7.0, 'end': 8.0}]}
            for plan, code in ((good, 0), (bad, 1), (past_eof, 1)):
                (p / 'plan.json').write_text(json.dumps(plan))
                r = subprocess.run([sys.executable, str(SPEECH), str(src), '--check-plan', str(p / 'plan.json')], capture_output=True, text=True)
                self.assertEqual(r.returncode, code, r.stdout)


if __name__ == '__main__':
    unittest.main()
