"""Offline parser tests; fixture is illustrative, not a live Wikivoyage download."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import parser


HTML = """<!doctype html><html><body>
<nav><ul><li>Site menu</li></ul></nav>
<div id="mw-content-text"><div class="mw-parser-output">
<div class="mw-heading mw-heading2"><h2>Baggage</h2><span class="mw-editsection">edit</span></div>
<div class="mw-heading mw-heading3"><h3>Pack expecting complications</h3></div>
<ul><li>Identification</li><li>Means of purchasing (cash, credit card)</li>
<li>Identification</li></ul>
<div class="mw-heading mw-heading2"><h2>Other</h2></div>
<ul><li>Odor eliminator – for long trips</li>
<li>Ear plugs are useful when you travel.</li>
<li>An eye mask is good for those who need darkness</li>
<li>Alarm clocks are perhaps less necessary these days.</li>
<li>A utility <a href="/wiki/Knife">knife</a> for outdoor life; not recommended for city-life.</li>
<li>   </li></ul>
<div class="mw-heading mw-heading2"><h2>See also</h2></div>
<ul><li>Not a packing item</li></ul>
</div></div><footer><ul><li>Site footer</li></ul></footer>
</body></html>"""


class ParserTests(unittest.TestCase):
    def test_explanation_without_comma_is_not_part_of_item(self):
        html = '<div id="mw-content-text"><h2>Other</h2><p>Bring a rain jacket because it may rain.</p></div>'
        self.assertEqual(parser.parse_packing_html(html),
                         [{"name": "Other", "items": ["a rain jacket"]}])

    def test_lowercase_recommendation_starts_a_new_item(self):
        html = '<div id="mw-content-text"><h2>Other</h2><p>Bring a camera. bring spare batteries.</p></div>'
        self.assertEqual(parser.parse_packing_html(html)[0]["items"],
                         ["a camera", "spare batteries"])

    def test_abbreviation_inside_item_is_preserved(self):
        html = '<div id="mw-content-text"><h2>Other</h2><p>Bring a U.S. Army knife. pack batteries.</p></div>'
        self.assertEqual(parser.parse_packing_html(html)[0]["items"],
                         ["a U.S. Army knife", "batteries"])

    def test_excluded_subsection_and_descendants_are_skipped(self):
        html = '''<div id="mw-content-text"><h2>Other</h2>
        <ul><li>Camera</li></ul><h3>References</h3>
        <ul><li>Fake reference</li></ul><h4>Books</h4><p>Bring fake book.</p>
        <h3>Useful gear</h3><ul><li>Batteries</li></ul></div>'''
        self.assertEqual(parser.parse_packing_html(html), [
            {"name": "Other", "items": ["Camera"]},
            {"name": "Other / Useful gear", "items": ["Batteries"]},
        ])

    def test_categories_and_items(self):
        result = parser.parse_packing_html(HTML)
        self.assertEqual([c["name"] for c in result], ["Baggage / Pack expecting complications", "Other"])
        self.assertEqual(result[0]["items"], ["Identification", "Means of purchasing (cash, credit card)"])
        self.assertEqual(result[1]["items"], [
            "Odor eliminator", "Ear plugs", "An eye mask", "Alarm clocks", "A utility knife for outdoor life"
        ])

    def test_missing_article_does_not_succeed(self):
        with self.assertRaises(parser.ParserError):
            parser.parse_packing_html("<html><body><nav><ul><li>Menu</li></ul></nav></body></html>")

    def test_empty_article_does_not_succeed(self):
        with self.assertRaises(parser.ParserError):
            parser.parse_packing_html('<div id="mw-content-text"><div class="mw-parser-output"><h2>Other</h2><p>Prose only.</p></div></div>')

    def test_saving_valid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data" / "packing_data.json"
            with patch.object(parser, "OUTPUT_FILE", path):
                parser.save_json(parser.parse_packing_html(HTML))
                import json
                loaded = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(loaded["type"], "general_packing")
                self.assertEqual(len(loaded["categories"]), 2)
                self.assertNotIn("Not a packing item", str(loaded))

    def test_parse_failure_cannot_replace_old_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data" / "packing_data.json"
            path.parent.mkdir()
            path.write_text('{"existing": true}', encoding="utf-8")
            with patch.object(parser, "OUTPUT_FILE", path), \
                 patch.object(parser, "make_user_agent", return_value="test-agent"), \
                 patch.object(parser, "download_html", return_value=b"<html></html>"):
                self.assertEqual(parser.main(), 1)
                self.assertEqual(path.read_text(encoding="utf-8"), '{"existing": true}')

    def test_long_real_list_item_is_not_dropped_or_truncated(self):
        long_item = (
            "Clothing you need before you can reach a shop "
            "(especially if going to a climate where what you are wearing isn't adequate)"
        )
        from bs4 import BeautifulSoup
        li = BeautifulSoup(f"<li>{long_item}</li>", "html.parser").li
        self.assertEqual(parser.extract_item(li), long_item)

    def test_paragraph_advice_and_html_links(self):
        html = """<div id="mw-content-text"><div class="mw-parser-output">
        <h2>See and do</h2><h3>Power supplies</h3>
        <p>Bring battery chargers and travel <a href="/wiki/Adapter">power adapters</a>
        for any electrical device you may use. Be sure to check the correct voltage.</p>
        <h3>Photography and videos</h3>
        <p>You'll probably want to bring a camera, along with sufficient storage and
        batteries, unless you're satisfied with your mobile phone's camera app.</p>
        </div></div>"""
        self.assertEqual(parser.parse_packing_html(html), [
            {"name": "See and do / Power supplies", "items": [
                "battery chargers and travel power adapters for any electrical device you may use"
            ]},
            {"name": "See and do / Photography and videos", "items": [
                "a camera, along with sufficient storage and batteries"
            ]},
        ])

    def test_prose_not_automatically_converted_to_item(self):
        html = """<div id="mw-content-text"><div class="mw-parser-output"><h2>Wear</h2>
        <p>Clothes typically make up most of travellers' baggage. Packing a tuxedo
        because you're unsure about a formal dinner signals over-packing.</p>
        <p>Bring stuff you enjoy. Take half the clothes and twice the money.</p>
        </div></div>"""
        with self.assertRaises(parser.ParserError):
            parser.parse_packing_html(html)

    def test_normalize_whitespace_and_case_insensitive_duplicates_across_sources(self):
        html = """<div id="mw-content-text"><div class="mw-parser-output">
        <h2>Other</h2><p>Bring   a  <b>travel&nbsp;adapter</b>.</p>
        <ul><li>A travel adapter</li><li>  Identification  </li>
        <li>identification</li><li> </li></ul>
        </div></div>"""
        self.assertEqual(parser.parse_packing_html(html)[0]["items"],
                         ["a travel adapter", "Identification"])

    def test_nested_bullets_are_independent(self):
        html = """<div id="mw-content-text"><div class="mw-parser-output">
        <h2>Other</h2><ul><li>Travel kit<ul><li>Bandages</li>
        <li>Flashlight</li></ul></li></ul></div></div>"""
        self.assertEqual(parser.parse_packing_html(html)[0]["items"],
                         ["Travel kit", "Bandages", "Flashlight"])

    def test_no_sidebar_or_edit_controls(self):
        html = """<div id="mw-content-text"><div class="mw-parser-output">
        <nav><p>Bring fake menu item.</p></nav>
        <div class="mw-heading mw-heading2"><h2>Other</h2>
        <span class="mw-editsection">Edit</span></div>
        <p>Bring a <b>rain jacket</b>.</p>
        <div class="noprint"><ul><li>Fake button</li></ul></div>
        <h2>See also</h2><ul><li>Fake related article</li></ul>
        </div></div>"""
        self.assertEqual(parser.parse_packing_html(html),
                         [{"name": "Other", "items": ["a rain jacket"]}])

    def test_invalid_or_empty_json_cannot_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data" / "packing_data.json"
            path.parent.mkdir()
            old = '{"existing": true}'
            path.write_text(old, encoding="utf-8")
            with patch.object(parser, "OUTPUT_FILE", path):
                for invalid in ([], [{"name": "Other", "items": []}],
                                [{"name": "Other", "items": [""]}]):
                    with self.assertRaises(parser.ParserError):
                        parser.save_json(invalid)
                    self.assertEqual(path.read_text(encoding="utf-8"), old)

    def test_empty_html_fails(self):
        for empty in ("", "<html></html>",
                      '<div id="mw-content-text"><h2>Other</h2><p>General prose.</p></div>'):
            with self.subTest(html=empty), self.assertRaises(parser.ParserError):
                parser.parse_packing_html(empty)


if __name__ == "__main__":
    unittest.main()
