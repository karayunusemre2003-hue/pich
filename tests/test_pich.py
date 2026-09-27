import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import auto_plan  # noqa: E402
from transcribe import DEFAULT_MODEL  # noqa: E402


class VoteTest(unittest.TestCase):
    def test_word_replaced_only_when_both_other_passes_agree(self):
        phrase = {'start': 10.0, 'end': 12.0, 'text': 'Ama sistemi kurmak 3 sualçı.'}
        w = lambda s, t0: [{'w': x, 'start': t0 + i * 0.3, 'end': t0 + i * 0.3 + 0.2} for i, x in enumerate(s.split())]
        t = {'words': w('Ama sistemi kurmak 3 saat sürdü.', 10.0), 'words_model2': w('ama sistemi kurmak 3 saat sürdü', 10.0)}
        self.assertEqual(auto_plan.vote(phrase, t), 'Ama sistemi kurmak 3 saat sürdü.')
        t['words_model2'] = w('ama sistemi kurmak 3 sa at', 10.0)  # the two others disagree -> keep the base
        self.assertEqual(auto_plan.vote(phrase, t), 'Ama sistemi kurmak 3 sualçı.')

    def test_neighbour_words_do_not_leak_in(self):
        phrase = {'start': 10.0, 'end': 11.0, 'text': 'Sistem sorunsuz çalışırsa'}
        words = [{'w': x, 'start': s, 'end': s + 0.2} for x, s in (('Sistem', 10.0), ('sorunsuz', 10.3), ('çalışırsa', 10.6), ('harcadığın', 11.2))]
        self.assertEqual(auto_plan.vote(phrase, {'words': words, 'words_model2': words}), 'Sistem sorunsuz çalışırsa')

    def test_chunks_keep_number_with_unit(self):
        self.assertIn('3 saat sürdü.', auto_plan.chunks('Ama sistemi kurmak 3 saat sürdü.'))
        self.assertTrue(all(not c.split()[-1].isdigit() for c in auto_plan.chunks('harcadığın zamanı 12 günde geri alıyorsun.')))


class ConformTest(unittest.TestCase):
    def test_landscape_vfr_becomes_vertical_cfr30(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = p / 'wide.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1280x720:rate=24:duration=2',
                            '-f', 'lavfi', '-i', 'sine=d=2', '-c:v', 'libx264', '-c:a', 'aac', '-shortest', str(src)], check=True)
            out, w, h = auto_plan.conform(src, p)
            self.assertNotEqual(out, src)
            ww, hh, r, avg, _ = auto_plan.probe(out)
            self.assertAlmostEqual(ww / hh, 9 / 16, delta=0.01)
            self.assertAlmostEqual(r, 30, delta=0.01)


@unittest.skipUnless(DEFAULT_MODEL.exists() and shutil.which('say') and shutil.which('whisper-cli'), 'needs whisper model + macOS say')
class PichEndToEndTest(unittest.TestCase):
    def test_one_command_turns_a_spoken_clip_into_a_reel(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); aiff = p / 'v.aiff'
            subprocess.run(['say', '-o', str(aiff), 'Record once. Pich cuts the pauses. [[slnc 700]] It writes the captions. [[slnc 700]] '
                            'Then it checks the result before you post it.'], check=True)
            src = p / 'raw.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1080x1920:rate=30', '-i', str(aiff),
                            '-af', 'adelay=500|500,apad=pad_dur=2.5', '-shortest', '-c:v', 'libx264', '-c:a', 'aac', str(src)], check=True)
            r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'pich.py'), str(src), '--out-dir', str(p / 'out'), '--lang', 'en',
                                '--hook', 'DEMO|Raw take|finished Reel', '--cta', 'Try it|on your own video|Star the repo'], capture_output=True, text=True)
            reels = list((p / 'out').glob('raw-pich-v1.mp4'))
            self.assertEqual(len(reels), 1, r.stdout + r.stderr)
            plan = json.loads((p / 'out' / 'plan.json').read_text())
            self.assertGreaterEqual(len(plan['edl']), 4)  # 3 phrases + CTA tail
            self.assertTrue((p / 'out' / 'review.md').exists())
            qa = json.loads((p / 'out' / 'raw-pich-v1.autoqa.json').read_text())
            self.assertNotIn('caption/ASR mismatch', qa['fails'])
            self.assertTrue(qa['basic']['checks']['frames_ok'])


if __name__ == '__main__':
    unittest.main()
