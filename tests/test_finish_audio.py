import array
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'finish_audio.py'


def command(*args):
    return subprocess.run(args, capture_output=True, text=True)


class FinishAudioTests(unittest.TestCase):
    def make_media(self, p):
        video, music, cue = (p / name for name in ('voice.mp4', 'bed.wav', 'whoosh.wav'))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
            'testsrc2=size=320x180:rate=30:duration=2', '-f', 'lavfi', '-i',
            'sine=frequency=440:sample_rate=48000:duration=2,volume=enable=\'between(t,0.5,1.0)\':volume=0', '-c:v', 'libx264',
            '-c:a', 'aac', '-shortest', str(video)], check=True)
        for file, frequency, duration in ((music, 200, 2), (cue, 800, .1)):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                f'sine=frequency={frequency}:sample_rate=48000:duration={duration}', str(file)], check=True)
        return video, music, cue

    def test_non_destructive_audio_mix_and_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            video, music, cue = self.make_media(p)
            before = video.read_bytes()
            plan = {'source': str(video),
                    'music': {'file': str(music), 'gain_db': -28, 'fade_in_s': .2,
                              'fade_out_s': .3, 'source_note': 'self-generated test tone', 'rights_checked': True},
                    'sfx': [{'file': str(cue), 'gain_db': -18, 'at_s': 1.0,
                             'source_note': 'self-generated test tone', 'rights_checked': True}]}
            path, out = p / 'plan.json', p / 'polished.mp4'
            path.write_text(json.dumps(plan))
            done = command(sys.executable, str(SCRIPT), str(path), str(video), str(out))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(video.read_bytes(), before)
            qa = json.loads((p / 'polished.sound-qa.json').read_text())
            self.assertTrue(qa['input_unchanged'])
            self.assertEqual(qa['frames'], 60)
            self.assertLess(abs(qa['video_duration_s'] - qa['audio_duration_s']), .07)
            self.assertIn('REVIEW', qa['status'])
            self.assertLess(qa['decoded_peak_dbfs'], -0.5)
            pcm = array.array('f', subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(out), '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-']))
            def tone(freq, start, length=.1):
                chunk = pcm[round(start*48000):round((start+length)*48000)]
                return abs(sum(s * complex(math.cos(-2*math.pi*freq*i/48000), math.sin(-2*math.pi*freq*i/48000))
                               for i, s in enumerate(chunk))) / len(chunk)
            self.assertGreater(tone(200, .7), tone(200, .3) * 1.15)  # bed ducks under voice
            self.assertGreater(tone(800, 1.02), tone(800, .8) * 4)  # cue lands at 1 s
            second = command(sys.executable, str(SCRIPT), str(path), str(video), str(out))
            self.assertNotEqual(second.returncode, 0)
            self.assertIn('already exists', second.stderr)

    def test_missing_rights_rejected_before_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            video, music, _ = self.make_media(p)
            plan = {'source': str(video), 'music': {'file': str(music), 'gain_db': -25}}
            path, out = p / 'plan.json', p / 'out.mp4'
            path.write_text(json.dumps(plan))
            bad = command(sys.executable, str(SCRIPT), str(path), str(video), str(out))
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('rights/source', bad.stderr)
            self.assertFalse(out.exists())

    def test_rejects_empty_music_and_cue_on_last_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            video, _, cue = self.make_media(p)
            path, out = p / 'plan.json', p / 'out.mp4'
            for plan, expected in (
                ({'source': str(video), 'music': {}}, 'non-empty object'),
                ({'source': str(video), 'music': []}, 'non-empty object'),
                ({'source': str(video), 'sfx': [{'file': str(cue), 'at_s': 2.0,
                    'gain_db': -18, 'rights_checked': True, 'source_note': 'test tone'}]}, 'before the video ends'),
            ):
                path.write_text(json.dumps(plan))
                bad = command(sys.executable, str(SCRIPT), str(path), str(video), str(out))
                self.assertNotEqual(bad.returncode, 0)
                self.assertIn(expected, bad.stderr)
                self.assertFalse(out.exists())

    def test_hot_music_is_limited_and_decoded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            video, music, _ = self.make_media(p)
            hot = p / 'hot.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(music), '-af', 'volume=12',
                            '-c:a', 'pcm_f32le', str(hot)], check=True)
            path, out = p / 'plan.json', p / 'limited.mp4'
            path.write_text(json.dumps({'source': str(video), 'music': {'file': str(hot),
                'gain_db': 0, 'fade_in_s': 0, 'fade_out_s': 0,
                'rights_checked': True, 'source_note': 'self-generated hot test tone'}}))
            done = command(sys.executable, str(SCRIPT), str(path), str(video), str(out))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertLessEqual(json.loads((p / 'limited.sound-qa.json').read_text())['decoded_peak_dbfs'], -.5)

    def test_concurrent_output_creation_cannot_be_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            video, _, cue = self.make_media(p)
            plan, out = p / 'plan.json', p / 'published.mp4'
            plan.write_text(json.dumps({'source': str(video), 'sfx': [{'file': str(cue),
                'gain_db': -25, 'at_s': 1, 'rights_checked': True, 'source_note': 'test tone'}]}))
            spec = importlib.util.spec_from_file_location('audio_finish_under_test', SCRIPT)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            def competing_writer(_temp, output):
                Path(output).write_bytes(b'other process publication')
                raise FileExistsError('simulated competing publication')
            with patch.object(module.os, 'link', side_effect=competing_writer):
                with self.assertRaises(FileExistsError):
                    module.finish(plan, out)
            self.assertEqual(out.read_bytes(), b'other process publication')
            self.assertFalse((p / 'published.sound-qa.json').exists())
            self.assertFalse(list(p.glob('.published-*.mp4')))

    def test_input_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            a, music, _ = self.make_media(p)
            other = p / 'different.mp4'
            other.write_bytes(a.read_bytes())
            path = p / 'plan.json'
            path.write_text(json.dumps({'source': str(a), 'music': {'file': str(music)}}))
            bad = command(sys.executable, str(SCRIPT), str(path), str(other), str(p / 'out.mp4'))
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('must match', bad.stderr)


if __name__ == '__main__':
    unittest.main()
