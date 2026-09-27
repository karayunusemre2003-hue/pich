import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / 'scripts' / 'stock.py'


@unittest.skipUnless(os.environ.get('PEXELS_API_KEY'), 'set PEXELS_API_KEY to run the live Pexels test')
class StockTest(unittest.TestCase):
    def test_search_and_get_photo_with_provenance(self):
        r = subprocess.run([sys.executable, str(STOCK), 'search', 'tomato', '--limit', '2'], capture_output=True, text=True, check=True)
        pid = r.stdout.split()[0]
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run([sys.executable, str(STOCK), 'get', pid, '--photo', '--out', temp], check=True, capture_output=True)
            meta = json.loads(next(Path(temp).glob('*.json')).read_text())
            self.assertEqual((meta['source'], meta['id']), ('Pexels', int(pid)))
            self.assertIn('pexels.com/license', meta['license'])
            again = subprocess.run([sys.executable, str(STOCK), 'get', pid, '--photo', '--out', temp], capture_output=True, text=True)
            self.assertIn('refuse to overwrite', again.stderr)


if __name__ == '__main__':
    unittest.main()
