"""
Empirical DOM and HTML structure validation suite for Milestone 2.
Directly inspects app/static/index.html and app/static/styles.css.
"""

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = PROJECT_ROOT / "app" / "static" / "index.html"
APP_JS = PROJECT_ROOT / "app" / "static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "app" / "static" / "styles.css"


class DOMNode:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []
        self.text = ""

    @property
    def id(self):
        return self.attrs.get("id")

    @property
    def classes(self):
        cls = self.attrs.get("class", "")
        return set(cls.split()) if cls else set()


class SimpleDOMParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes_by_id = {}
        self.nodes_by_tag = {}
        self.all_nodes = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        node = DOMNode(tag, attrs)
        self.all_nodes.append(node)
        self.nodes_by_tag.setdefault(tag, []).append(node)
        if node.id:
            self.nodes_by_id[node.id] = node
        if self.stack:
            self.stack[-1].children.append(node)
        self.stack.append(node)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].text += data


class TestFrontendDOMAndStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_content = INDEX_HTML.read_text(encoding="utf-8")
        cls.js_content = APP_JS.read_text(encoding="utf-8")
        cls.css_content = STYLES_CSS.read_text(encoding="utf-8")

        parser = SimpleDOMParser()
        parser.feed(cls.html_content)
        cls.dom = parser

    def test_r1_spanish_language_and_title(self):
        """Verify HTML lang is es and title reflects Spanish Google Cloud / Model Armor platform."""
        html_tag_match = re.search(r'<html[^>]*lang=["\']([^"\']+)["\']', self.html_content, re.IGNORECASE)
        self.assertIsNotNone(html_tag_match, "html tag must have lang attribute")
        self.assertEqual(html_tag_match.group(1), "es", "Language must be Spanish ('es')")

        self.assertIn("<title>", self.html_content)
        title_match = re.search(r'<title>(.*?)</title>', self.html_content, re.DOTALL)
        self.assertTrue(title_match)
        title_text = title_match.group(1)
        self.assertIn("Armor Agent", title_text)
        self.assertIn("Vertex AI", title_text)
        self.assertIn("Model Armor", title_text)

    def test_cache_busting_versioning(self):
        """Verify cache-busting v=20261019-v2 query string on static assets."""
        self.assertIn('styles.css?v=20261019-v2', self.html_content)
        self.assertIn('app.js?v=20261019-v2', self.html_content)

    def test_all_js_referenced_element_ids_exist_in_html(self):
        """Verify every DOM element ID queried by app.js exists in index.html."""
        # Extract all document.getElementById('...') from app.js
        get_elem_ids = set(re.findall(r"document\.getElementById\(['\"]([a-zA-Z0-9_\-]+)['\"]\)", self.js_content))
        
        # Verify non-empty
        self.assertGreater(len(get_elem_ids), 15, "app.js should query multiple DOM element IDs")

        missing_ids = []
        for elem_id in get_elem_ids:
            # Some IDs might be created dynamically in templates; check if in HTML or created dynamically
            if elem_id not in self.dom.nodes_by_id:
                # Check if it's dynamically created in js templates or known dynamic element
                if f'id="{elem_id}"' not in self.js_content and f"id='{elem_id}'" not in self.js_content:
                    missing_ids.append(elem_id)

        self.assertEqual(missing_ids, [], f"DOM IDs referenced in app.js missing from index.html: {missing_ids}")

    def test_model_selector_strictly_limited_to_argon_and_flash(self):
        """Verify model selector contains strictly gemini-4-argon and gemini-3.8-flash."""
        model_select = self.dom.nodes_by_id.get("modelSelect")
        self.assertIsNotNone(model_select, "select#modelSelect must exist in DOM")
        self.assertEqual(model_select.tag, "select")

        # Extract options within modelSelect
        select_block_match = re.search(r'<select[^>]*id=["\']modelSelect["\'][^>]*>(.*?)</select>', self.html_content, re.DOTALL)
        self.assertIsNotNone(select_block_match)
        options = re.findall(r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>', select_block_match.group(1))

        self.assertEqual(len(options), 2, f"modelSelect must have exactly 2 options, found {len(options)}: {options}")
        values = [opt[0] for opt in options]
        self.assertEqual(values, ["gemini-4-argon", "gemini-3.8-flash"])

        # Check banned models do not appear anywhere in option values
        banned_models = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.0-pro", "gpt-4"]
        for opt_val in values:
            for banned in banned_models:
                self.assertNotIn(banned, opt_val)

    def test_four_tabs_structure_and_aria_attributes(self):
        """Verify 4-tab container with exact tab keys: chat, audit, policies, logs."""
        required_tabs = ["chat", "audit", "policies", "logs"]
        tab_buttons = [f"tabBtn{t.capitalize()}" for t in required_tabs]
        tab_panels = [f"tabPanel{t.capitalize()}" for t in required_tabs]

        for btn_id in tab_buttons:
            self.assertIn(btn_id, self.dom.nodes_by_id, f"Tab button #{btn_id} must exist")
            btn = self.dom.nodes_by_id[btn_id]
            self.assertEqual(btn.attrs.get("role"), "tab", f"{btn_id} must have role='tab'")
            self.assertIn("aria-selected", btn.attrs)
            self.assertIn("aria-controls", btn.attrs)

        for panel_id in tab_panels:
            self.assertIn(panel_id, self.dom.nodes_by_id, f"Tab panel #{panel_id} must exist")
            panel = self.dom.nodes_by_id[panel_id]
            self.assertEqual(panel.attrs.get("role"), "tabpanel", f"{panel_id} must have role='tabpanel'")
            self.assertIn("aria-labelledby", panel.attrs)

        # Initial active tab should be chat
        chat_btn = self.dom.nodes_by_id["tabBtnChat"]
        self.assertEqual(chat_btn.attrs.get("aria-selected"), "true")
        self.assertIn("active", chat_btn.classes)

        chat_panel = self.dom.nodes_by_id["tabPanelChat"]
        self.assertIn("active", chat_panel.classes)
        self.assertNotIn("hidden", chat_panel.classes)

        # Other 3 panels must start hidden
        for other in ["tabPanelAudit", "tabPanelPolicies", "tabPanelLogs"]:
            panel = self.dom.nodes_by_id[other]
            self.assertIn("hidden", panel.classes, f"{other} should be hidden initially")

    def test_presets_dropdown_options(self):
        """Verify presets dropdown contains 6 options covering 5 threat types and 1 safe query."""
        preset_select = self.dom.nodes_by_id.get("presetSelect")
        self.assertIsNotNone(preset_select, "select#presetSelect must exist")

        select_block_match = re.search(r'<select[^>]*id=["\']presetSelect["\'][^>]*>(.*?)</select>', self.html_content, re.DOTALL)
        self.assertIsNotNone(select_block_match)
        options = re.findall(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>', select_block_match.group(1))

        # Check values: empty placeholder + 0, 1, 2, 3, 4, 5
        values = [opt[0] for opt in options]
        self.assertIn("", values)
        for i in range(6):
            self.assertIn(str(i), values)

        # Check optgroups: Attacks/Leaks and Safe Query
        self.assertIn('optgroup label="🚫 Ataques y Fugas', select_block_match.group(1))
        self.assertIn('optgroup label="✅ Consulta Segura"', select_block_match.group(1))

    def test_theme_segmented_buttons(self):
        """Verify themeDarkBtn and themeLightBtn exist with MD3 structure."""
        dark_btn = self.dom.nodes_by_id.get("themeDarkBtn")
        light_btn = self.dom.nodes_by_id.get("themeLightBtn")

        self.assertIsNotNone(dark_btn, "themeDarkBtn must exist")
        self.assertIsNotNone(light_btn, "themeLightBtn must exist")
        self.assertIn("active", dark_btn.classes, "themeDarkBtn should be active by default")

    def test_official_palette_tokens_in_css(self):
        """Verify official palette #06141B, #11212D, #253745, #4A5C6A, #9BA8AB, #CCD0CF in CSS."""
        palette_hexes = [
            "#06141B",
            "#11212D",
            "#253745",
            "#4A5C6A",
            "#9BA8AB",
            "#CCD0CF"
        ]
        for hex_color in palette_hexes:
            self.assertIn(
                hex_color.lower(),
                self.css_content.lower(),
                f"Official palette color {hex_color} must be defined in styles.css"
            )

        # Check both dark and light theme selectors
        self.assertIn('data-theme="dark"', self.css_content)
        self.assertIn('data-theme="light"', self.css_content)


if __name__ == "__main__":
    unittest.main()
