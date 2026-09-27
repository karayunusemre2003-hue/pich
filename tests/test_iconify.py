import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts')); sys.path.insert(0, str(ROOT / 'tests'))
import iconify  # noqa: E402
from test_render_reel import RENDER, make_source, reel_plan  # noqa: E402


class IconifyOfflineTest(unittest.TestCase):
    """No network: name/SVG/plan validation must hold even when the API is unreachable."""

    def test_names(self):
        self.assertEqual(iconify.check_name('lucide:bell'), ['lucide', 'bell'])
        for bad in ('lucide:bell\n', '../../etc:passwd', 'bell', 'a:' + 'b' * 100, None, 'Lucide:Bell'):
            with self.assertRaises(ValueError, msg=repr(bad)): iconify.check_name(bad)

    def test_svg_content_guard(self):
        ok = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0h24v24H0z"/></svg>'
        iconify.check_svg(ok, 't')
        for bad in (b'<svg viewBox="0 0 24 24"><image href="http://x/y.png"/></svg>',
                    b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg/>',
                    b'<svg viewBox="0 0 2400 24"><path/></svg>',  # 100:1 aspect
                    b'<html>not an svg</html>'):
            with self.assertRaises(ValueError, msg=bad[:30]): iconify.check_svg(bad, 't')

    def test_plan_rejects_bad_icon_fields_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); src = make_source(p, 3)
            for layer, needle in (({'icon': '../../etc:passwd'}, 'prefix:name'), ({'icon': 'lucide:bell', 'card': 'yes'}, 'card'),
                                  ({'icon': 'lucide:bell', 'color': 'mor'}, 'color')):
                plan = reel_plan(src); plan['layers'] = [dict({'kind': 'icon', 'y': 300, 'from': 'start', 'to': 'end'}, **layer)]
                (p / 'plan.json').write_text(json.dumps(plan))
                r = subprocess.run([sys.executable, str(RENDER), str(p / 'plan.json'), str(p / 'x.mp4'), '--graph-only'], capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0, layer); self.assertIn(needle, r.stderr, layer)


if __name__ == '__main__':
    unittest.main()
