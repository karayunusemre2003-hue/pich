import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HV = ROOT / 'scripts' / 'hook_variants.py'
sys.path.insert(0, str(ROOT / 'tests'))
from test_render_reel import make_source, reel_plan  # noqa: E402


class HookVariantsTest(unittest.TestCase):
    def test_sheet_pick_and_overflow_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p, 4)
            plan = reel_plan(src); plan.pop('slide'); plan['audio'].pop('sfx')
            plan['edl'] = [{'start': 0.3, 'end': 3.7}]; plan['captions'] = {'items': []}
            plan['layers'] = [plan['layers'][0]]
            (p / 'plan.json').write_text(json.dumps(plan))
            variants = [{'name': 'A', 'hook': {'from_text': 'Kısa', 'to_text': 'hook'}},
                        {'name': 'B', 'hook': {'from_text': 'Başka', 'to_text': 'fikir'}}]
            (p / 'v.json').write_text(json.dumps(variants))
            out = p / 'hv'
            subprocess.run([sys.executable, str(HV), str(p / 'plan.json'), str(p / 'v.json'), '--out-dir', str(out)], check=True, capture_output=True)
            with Image.open(out / 'hooks.jpg') as im: self.assertEqual(im.width, 720)
            frames = int(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v', '-show_entries',
                                                  'stream=nb_read_frames', '-of', 'csv=p=0', str(out / 'preview_A.mp4')]))
            self.assertEqual(frames, 90)  # --until 3 at 30 fps
            ok_a = (out / 'preview_A.ok').read_text()
            variants[0]['hook']['to_text'] = 'değişti'; (p / 'v.json').write_text(json.dumps(variants))
            subprocess.run([sys.executable, str(HV), str(p / 'plan.json'), str(p / 'v.json'), '--out-dir', str(out)], check=True, capture_output=True)
            self.assertNotEqual((out / 'preview_A.ok').read_text(), ok_a)  # changed copy -> re-rendered, not reused
            subprocess.run([sys.executable, str(HV), str(p / 'plan.json'), str(p / 'v.json'), '--out-dir', str(out), '--pick', 'B'], check=True, capture_output=True)
            final = json.loads((out / 'plan.final.json').read_text())
            self.assertEqual(final['layers'][0]['from_text'], 'Başka')
            self.assertIn('Seçilen hook: **B**', (out / 'STATE.md').read_text())
            (p / 'long.json').write_text(json.dumps([{'name': 'L', 'hook': {'from_text': 'Bu çok çok uzun bir hook metni', 'to_text': 'taşar mı acaba'}}]))
            r = subprocess.run([sys.executable, str(HV), str(p / 'plan.json'), str(p / 'long.json'), '--out-dir', str(p / 'hv2')], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('hook text too long', r.stderr)


if __name__ == '__main__':
    unittest.main()
