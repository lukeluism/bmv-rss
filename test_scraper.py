import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import scraper


HTML = '''<base href="https://www.bmv.de/">
<div class="search-results"><ul class="card-list"><li class="card">
<p class="card-title"><a class="card-link" href="SharedDocs/DE/Pressemitteilungen/2026/001-test.html"><strong>Mehr E-<abbr>Pkw</abbr> &amp; Bahn</strong></a></p>
<p class="card-date"><strong>Datum:</strong> 23.10.2026</p>
</li></ul></div>
<a class="pagination-link-next" href="SiteGlobals/Forms/Suche/DE/Expertensuche_Formular.html?page=2">Weiter</a>'''


class ScraperTests(unittest.TestCase):
    def test_base_url_nested_title_and_pagination(self):
        items, next_url = scraper.parse_page(HTML, scraper.SOURCE)
        self.assertEqual(items[0]['url'], 'https://www.bmv.de/SharedDocs/DE/Pressemitteilungen/2026/001-test.html')
        self.assertEqual(items[0]['title'], 'Mehr E-Pkw & Bahn')
        self.assertEqual(items[0]['date'], '2026-10-23')
        self.assertTrue(next_url.startswith('https://www.bmv.de/SiteGlobals/'))

    def test_empty_or_malformed_results_fail(self):
        for html in ('<html>Wartung</html>', HTML.replace('23.10.2026', 'unbekannt'), HTML.replace('23.10.2026', '31.02.2026')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                scraper.parse_page(html, scraper.SOURCE)

    def test_repeated_pagination_fails(self):
        with patch('scraper.fetch', return_value=HTML), patch('scraper.time.sleep'):
            with self.assertRaises(ValueError):
                scraper.collect(scraper.SOURCE, 3)

    def test_repeat_run_and_failure_preserve_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, output = Path(tmp) / 'items.json', Path(tmp) / 'public'
            argv = ['scraper.py', '--site-url', 'https://example.github.io/bmv-rss', '--pages', '1', '--state', str(state), '--output', str(output)]
            with patch('sys.argv', argv), patch('scraper.fetch', return_value=HTML):
                scraper.run()
                first = state.read_bytes()
                scraper.run()
                self.assertEqual(state.read_bytes(), first)
                self.assertEqual(json.loads((output / 'status.json').read_text())['new_items'], 0)
                feed = (output / 'feed.xml').read_bytes()
            with patch('sys.argv', argv), patch('scraper.fetch', return_value='<html>Wartung</html>'):
                with self.assertRaises(ValueError):
                    scraper.run()
            self.assertEqual(state.read_bytes(), first)
            self.assertEqual((output / 'feed.xml').read_bytes(), feed)

    def test_xml_and_source_date(self):
        items, _ = scraper.parse_page(HTML, scraper.SOURCE)
        root = ET.fromstring(scraper.render_feed(items, 'https://example.github.io/bmv-rss', scraper.SOURCE, datetime.now(timezone.utc)))
        item = root.find('./channel/item')
        self.assertEqual(item.findtext('title'), 'Mehr E-Pkw & Bahn')
        self.assertEqual(item.findtext(f'{{{scraper.DC}}}date'), '2026-10-23')
        self.assertIsNone(item.find('pubDate'))


if __name__ == '__main__':
    unittest.main()
