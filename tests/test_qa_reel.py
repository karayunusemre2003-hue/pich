import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RENDER, QA = ROOT / 'scripts' / 'render_reel.py', ROOT / 'scripts' / 'qa_reel.py'
sys.path.insert(0, str(ROOT / 'scripts')); sys.path.insert(0, str(ROOT / 'tests'))
import qa_reel  # noqa: E402
from test_render_reel import make_source, reel_plan  # noqa: E402

from transcribe import DEFAULT_MODEL as MODEL  # noqa: E402


def run_qa(out, plan, *extra):
    r = subprocess.run([sys.executable, str(QA), str(out), '--plan', str(plan), *extra], capture_output=True, text=True)
    rep = json.loads(Path(str(out)[:-4] + '.autoqa.json').read_text())
    return r.returncode, rep


def reencode(src, dst, *args):
    """Broken copy of a render + its output-bound manifest (QA refuses files without one)."""
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), *args, '-c:v', 'libx264', '-c:a', 'aac', str(dst)], check=True)
    man = json.loads(Path(str(src)[:-4] + '.manifest.json').read_text()); man['output'] = str(Path(dst).resolve())
    Path(str(dst)[:-4] + '.manifest.json').write_text(json.dumps(man))


class FaceOverlapTest(unittest.TestCase):
    def test_core_fail_chin_warn_clear_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            png = Path(temp) / 'cap.png'
            im = Image.new('RGBA', (1080, 100), (0, 0, 0, 0)); im.paste((255, 255, 255, 255), (200, 40, 880, 80)); im.save(png)
            face = [0.3, 0.3, 0.4, 0.3]  # y 0.30-0.60, mouth core ends at 0.516
            def conflicts(y_px):
                L = {'path': str(png), 'kind': 'caption', 'x': 0, 'y': y_px, 't0': 0, 't1': 1}
                return [c['severity'] for c in qa_reel.face_layer_conflicts([(0.5, [face])], [L], 1080, 1920)]
            self.assertEqual(conflicts(int(0.45 * 1920) - 40), ['fail'])   # over the mouth
            self.assertEqual(conflicts(int(0.56 * 1920) - 40), ['warn'])   # on the chin
            self.assertEqual(conflicts(int(0.70 * 1920) - 40), [])         # below the face
            # rests above the face, but its 'rise' slide-in starts lower and sweeps across the mouth -> must still fail
            L = {'path': str(png), 'kind': 'cta_card', 'x': 0, 'y': int(0.20 * 1920) - 40, 't0': 0, 't1': 1, 'rise': 400}
            self.assertEqual([c['severity'] for c in qa_reel.face_layer_conflicts([(0.5, [face])], [L], 1080, 1920)], ['fail'])


class CameraWindowTest(unittest.TestCase):
    def test_slide_wins_last_broll_on_top_and_fades_show_camera(self):
        pip = {'pip_box': [584, 540, 440, 600], 'pip_crop': [0, 0, 540, 736]}
        man = {'slide': dict(pip, t0=10, t1=12),
               'camera_windows': [dict(t0=1, t1=5, mode='full', fade_in=0.2, fade_out=0.2), dict(pip, t0=3, t1=4, mode='full_pip')]}
        self.assertEqual(qa_reel.active_window(man, 11)['t0'], 10)            # slide above B-roll
        self.assertEqual(qa_reel.active_window(man, 3.5)['mode'], 'full_pip')  # later B-roll drawn on top
        self.assertEqual(qa_reel.active_window(man, 2)['mode'], 'full')
        self.assertIsNone(qa_reel.active_window(man, 1.1))                     # fading in: camera still visible
        man2 = {'camera_windows': [dict(t0=1, t1=3, mode='full'), dict(t0=2, t1=4, mode='full')]}
        self.assertEqual(qa_reel.hidden_intervals(man2), [[1, 4]])             # merged, no double count


class MatchingTest(unittest.TestCase):
    def test_turkish_casing_and_order(self):
        self.assertEqual(qa_reel.norm_words('IŞIK İstanbul'), qa_reel.norm_words('ışık istanbul'))
        import difflib
        cap = qa_reel.norm_words('bir iki üç dört')
        ok = sum(b.size for b in difflib.SequenceMatcher(a=cap, b=qa_reel.norm_words('bir iki üç dört'), autojunk=False).get_matching_blocks())
        rev = sum(b.size for b in difflib.SequenceMatcher(a=cap, b=qa_reel.norm_words('dört üç iki bir'), autojunk=False).get_matching_blocks())
        self.assertEqual(ok, 4); self.assertLess(rev, 2)

    def test_flat_envelope_prefers_zero_lag(self):
        self.assertEqual(qa_reel.best_lag([-20.0] * 80, [-20.0] * 80)[0], 0)


class QaReelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(); p = Path(cls.tmp)
        src = make_source(p); plan = reel_plan(src); plan['slide']['pip'] = {'box': [584, 540, 440, 600], 'crop': [160, 130, 760, 1038]}
        cls.plan = p / 'plan.json'; cls.plan.write_text(json.dumps(plan))
        cls.good = p / 'good.mp4'
        subprocess.run([sys.executable, str(RENDER), str(cls.plan), str(cls.good), '--preview'], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_good_render_passes_objective_checks(self):
        code, rep = run_qa(self.good, self.plan, '--no-asr', '--no-faces')
        self.assertEqual((code, rep['status']), (0, 'AUTO_PASS'), rep['fails'])
        self.assertTrue(all(abs(s['lag_ms']) <= 10 for s in rep['sync']), rep['sync'])
        self.assertTrue(rep['human_review_required'])
        self.assertTrue(Path(str(self.good)[:-4] + '.autoqa.jpg').exists())

    def test_voice_stem_matches_render_timeline(self):
        man = json.loads(Path(str(self.good)[:-4] + '.manifest.json').read_text())
        stem = Path(self.tmp) / 'stem.wav'; qa_reel.voice_stem(man, stem)
        dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(stem)]))
        self.assertAlmostEqual(dur, man['duration_s'], delta=0.05)

    def test_voice_stem_applies_segment_volume(self):
        man = json.loads(Path(str(self.good)[:-4] + '.manifest.json').read_text())
        man['edl'][0]['volume'] = 0  # a muted segment must be silent in the stem too
        stem = Path(self.tmp) / 'stem0.wav'; qa_reel.voice_stem(man, stem)
        from speech_map import db, load_pcm
        pcm = load_pcm(stem); d0 = man['edl'][0]['src_end'] - man['edl'][0]['src_start']
        self.assertLess(db(pcm, 0.3, d0 - 0.3), -80)

    def test_manifest_must_belong_to_file(self):
        other = Path(self.tmp) / 'copy.mp4'; shutil.copy(self.good, other)
        shutil.copy(str(self.good)[:-4] + '.manifest.json', str(other)[:-4] + '.manifest.json')
        r = subprocess.run([sys.executable, str(QA), str(other), '--plan', str(self.plan), '--no-asr', '--no-faces'], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn('belongs to', r.stderr)

    def test_broken_fixtures_fail(self):
        p = Path(self.tmp)
        cases = {'sync': ['-af', 'adelay=150|150,atrim=end=4.8'],
                 'loudness': ['-af', 'volume=-18dB'],
                 'black last frame': ['-vf', "drawbox=c=black:t=fill:enable='gte(n,143)'"]}  # only the very last frame
        for needle, args in cases.items():
            bad = p / f"bad_{needle.split()[0]}.mp4"; reencode(self.good, bad, *args)
            code, rep = run_qa(bad, self.plan, '--no-asr', '--no-faces')
            self.assertEqual(code, 1, needle)
            self.assertTrue(any(needle in f for f in rep['fails']), (needle, rep['fails']))

    @unittest.skipUnless(MODEL.exists() and shutil.which('say') and shutil.which('whisper-cli'), 'needs whisper model + macOS say')
    def test_caption_asr_roundtrip_catches_wrong_caption(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); aiff = p / 'v.aiff'
            subprocess.run(['say', '-v', 'Yelda', '-o', str(aiff), 'Bugün pazara gittim ve domates aldım.'], check=True)
            src = p / 'src.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=540x960:rate=30', '-i', str(aiff),
                            '-af', 'apad=pad_dur=0.6,adelay=300|300', '-shortest', '-c:v', 'libx264', '-c:a', 'aac', str(src)], check=True)
            dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(src)]))
            for text, want in (('Bugün pazara gittim ve domates aldım.', 0), ('Dün sinemaya gidip patlamış mısır yedim.', 1)):
                plan = {'source': str(src), 'source_size': [540, 960], 'build_dir': str(p / f'b{want}'),
                        'edl': [{'start': 0.0, 'end': round(dur - 0.1, 2)}],
                        'captions': {'items': [{'seg': 0, 'start': 0.3, 'end': round(dur - 0.4, 2), 'text': text}]},
                        'audio': {'loudnorm': {'I': -14, 'TP': -1.5, 'LRA': 9}}}
                pp = p / f'plan{want}.json'; pp.write_text(json.dumps(plan)); out = p / f'o{want}.mp4'
                subprocess.run([sys.executable, str(RENDER), str(pp), str(out), '--preview'], check=True, capture_output=True)
                code, rep = run_qa(out, pp, '--no-faces')
                self.assertEqual(any('caption' in f for f in rep['fails']), bool(want), rep['asr'])


if __name__ == '__main__':
    unittest.main()
