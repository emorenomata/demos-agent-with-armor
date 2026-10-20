"""
Empirical Challenger Test Suite for Milestone 3 Live Deployment.
Target: armor-agent-service behind Global External Application Load Balancer at http://34.117.66.159

Uses Python standard library (urllib.request) to ensure zero dependency friction.
"""

import concurrent.futures
import json
import re
import time
import unittest
import urllib.request
import urllib.error
from html.parser import HTMLParser

TARGET_URL = "http://34.117.66.159"
TIMEOUT = 30.0


def make_request(path: str, method: str = "GET", data: bytes = None, headers: dict = None):
    url = f"{TARGET_URL}{path}"
    req_headers = {"User-Agent": "M3EmpiricalChallenger/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # Direct connection, no proxy
    return opener.open(req, timeout=TIMEOUT)


class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = set()
        self.classes = set()
        self.attrs_by_id = {}
        self.links = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self.tags.append((tag, attr_dict))
        element_id = attr_dict.get("id")
        if element_id:
            self.ids.add(element_id)
            self.attrs_by_id[element_id] = attr_dict
        if "class" in attr_dict:
            for c in attr_dict["class"].split():
                self.classes.add(c)
        if tag == "link" and "href" in attr_dict:
            self.links.append(attr_dict)
        if tag == "script" and "src" in attr_dict:
            self.scripts.append(attr_dict)


class TestM3LiveDeployment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with make_request("/") as resp:
            cls.root_status = resp.status
            cls.root_headers = dict(resp.getheaders())
            cls.root_html = resp.read().decode("utf-8")
        assert cls.root_status == 200, f"Root returned {cls.root_status}"
        cls.parser = SimpleHTMLParser()
        cls.parser.feed(cls.root_html)

    # --------------------------------------------------------------------------
    # 1. Root '/' Verification
    # --------------------------------------------------------------------------
    def test_01_root_http_headers(self):
        """Verify root returns 200 OK and text/html."""
        self.assertEqual(self.root_status, 200)
        content_type = self.root_headers.get("Content-Type", self.root_headers.get("content-type", ""))
        self.assertIn("text/html", content_type)
        self.assertGreater(len(self.root_html), 5000, "Root HTML should be substantial")

    def test_02_cache_busted_assets_in_root(self):
        """Verify cache-busting v=20261019-v2 on stylesheet and script."""
        css_found = False
        for link in self.parser.links:
            href = link.get("href", "")
            if "styles.css" in href:
                self.assertIn("v=20261019-v2", href, f"CSS link missing cache buster: {href}")
                css_found = True
        self.assertTrue(css_found, "styles.css link tag not found in root HTML")

        js_found = False
        for script in self.parser.scripts:
            src = script.get("src", "")
            if "app.js" in src:
                self.assertIn("v=20261019-v2", src, f"JS script tag missing cache buster: {src}")
                js_found = True
        self.assertTrue(js_found, "app.js script tag not found in root HTML")

    def test_03_top_command_bar_presence(self):
        """Verify presence of Top Command Bar and its required controls."""
        self.assertIn("md3-top-app-bar", self.parser.classes, "Top command bar class missing")
        self.assertIn("Armor Agent", self.root_html)
        self.assertIn("modelSelect", self.parser.ids, "modelSelect control missing")
        self.assertIn("presetSelect", self.parser.ids, "presetSelect control missing")
        self.assertIn("masterArmorToggle", self.parser.ids, "masterArmorToggle control missing")
        self.assertIn("armorStatusBadge", self.parser.ids, "armorStatusBadge missing")
        self.assertIn("themeDarkBtn", self.parser.ids, "themeDarkBtn missing")
        self.assertIn("themeLightBtn", self.parser.ids, "themeLightBtn missing")
        self.assertIn("clearChatBtn", self.parser.ids, "clearChatBtn missing")

    def test_04_four_tabs_buttons_and_panels(self):
        """Verify the 4 tabs (chat, audit, policies, logs) exist with appropriate controls."""
        required_tabs = ["Chat", "Audit", "Policies", "Logs"]
        for tab_name in required_tabs:
            btn_id = f"tabBtn{tab_name}"
            panel_id = f"tabPanel{tab_name}"
            self.assertIn(btn_id, self.parser.ids, f"Tab button #{btn_id} missing")
            self.assertIn(panel_id, self.parser.ids, f"Tab panel #{panel_id} missing")

            btn_attrs = self.parser.attrs_by_id[btn_id]
            self.assertEqual(btn_attrs.get("role"), "tab")
            self.assertEqual(btn_attrs.get("aria-controls"), panel_id)

            panel_attrs = self.parser.attrs_by_id[panel_id]
            self.assertEqual(panel_attrs.get("role"), "tabpanel")
            self.assertEqual(panel_attrs.get("aria-labelledby"), btn_id)

    def test_05_model_selector_strictness(self):
        """Verify model selector only contains gemini-4-argon and gemini-3.8-flash."""
        select_match = re.search(r'<select[^>]*id=["\']modelSelect["\'][^>]*>(.*?)</select>', self.root_html, re.DOTALL)
        self.assertIsNotNone(select_match, "modelSelect element not found")
        options = re.findall(r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>(.*?)</option>', select_match.group(1))
        model_values = [opt[0] for opt in options]
        self.assertEqual(model_values, ["gemini-4-argon", "gemini-3.8-flash"])

    # --------------------------------------------------------------------------
    # 2. Static Assets Verification
    # --------------------------------------------------------------------------
    def test_06_static_css_with_cache_buster(self):
        """Verify /static/styles.css?v=20261019-v2 returns HTTP 200 with text/css."""
        with make_request("/static/styles.css?v=20261019-v2") as resp:
            self.assertEqual(resp.status, 200)
            headers = dict(resp.getheaders())
            content_type = headers.get("Content-Type", headers.get("content-type", ""))
            self.assertIn("text/css", content_type)
            css_text = resp.read().decode("utf-8")
        self.assertGreater(len(css_text), 10000)

        # Verify Material Design 3 official palette tokens exist
        palette_hexes = ["#06141B", "#11212D", "#253745", "#4A5C6A", "#9BA8AB", "#CCD0CF"]
        for hex_code in palette_hexes:
            self.assertIn(hex_code.lower(), css_text.lower(), f"Palette hex {hex_code} missing from live styles.css")

    def test_07_static_js_with_cache_buster(self):
        """Verify /static/app.js?v=20261019-v2 returns HTTP 200 with application/javascript."""
        with make_request("/static/app.js?v=20261019-v2") as resp:
            self.assertEqual(resp.status, 200)
            headers = dict(resp.getheaders())
            content_type = headers.get("Content-Type", headers.get("content-type", ""))
            self.assertTrue(
                any(t in content_type for t in ["application/javascript", "text/javascript"]),
                f"Unexpected content-type for app.js: {content_type}"
            )
            js_text = resp.read().decode("utf-8")
        self.assertGreater(len(js_text), 10000)

        # Verify dual tab alias mapping in TABS_CONFIG
        self.assertIn("chat-tab", js_text)
        self.assertIn("audit-tab", js_text)
        self.assertIn("policies-tab", js_text)
        self.assertIn("logs-tab", js_text)

        # Verify models in JS
        self.assertIn("gemini-4-argon", js_text)
        self.assertIn("gemini-3.8-flash", js_text)

    # --------------------------------------------------------------------------
    # 3. API Endpoints Verification
    # --------------------------------------------------------------------------
    def test_08_api_templates_content(self):
        """Verify /api/templates returns HTTP 200 with 4+ attack presets and safe query."""
        with make_request("/api/templates") as resp:
            self.assertEqual(resp.status, 200)
            headers = dict(resp.getheaders())
            content_type = headers.get("Content-Type", headers.get("content-type", ""))
            self.assertIn("application/json", content_type)
            data = json.loads(resp.read().decode("utf-8"))

        self.assertIn("templates", data)
        self.assertIn("attack_presets", data)

        presets = data["attack_presets"]
        # Must have at least 5 presets (4 attack + 1 safe)
        self.assertGreaterEqual(len(presets), 5)

        titles = [p.get("title", "") for p in presets]
        # Check presence of the required attack presets + safe query
        has_injection = any("Inyecci" in t or "Jailbreak" in t for t in titles)
        has_credit_card = any("Tarjeta" in t for t in titles)
        has_rai = any("Peligrosa" in t for t in titles)
        has_malicious_uri = any("Enlace" in t or "Phishing" in t for t in titles)
        has_safe = any("Legítima" in t or "Segura" in t for t in titles)

        self.assertTrue(has_injection, f"Prompt injection preset missing in {titles}")
        self.assertTrue(has_credit_card, f"Credit card SDP preset missing in {titles}")
        self.assertTrue(has_rai, f"RAI dangerous preset missing in {titles}")
        self.assertTrue(has_malicious_uri, f"Malicious URI preset missing in {titles}")
        self.assertTrue(has_safe, f"Safe query preset missing in {titles}")

    def test_09_api_floor_setting_endpoint(self):
        """Verify /api/floor-setting returns HTTP 200 with inspectAndBlock boolean."""
        with make_request("/api/floor-setting") as resp:
            self.assertEqual(resp.status, 200)
            headers = dict(resp.getheaders())
            content_type = headers.get("Content-Type", headers.get("content-type", ""))
            self.assertIn("application/json", content_type)
            data = json.loads(resp.read().decode("utf-8"))

        # The floor setting object has aiPlatformFloorSetting with inspectAndBlock boolean
        ai_platform_setting = data.get("aiPlatformFloorSetting", {})
        self.assertIn("inspectAndBlock", ai_platform_setting, f"inspectAndBlock not found in {data}")
        self.assertIsInstance(ai_platform_setting["inspectAndBlock"], bool)

    def test_10_api_health_endpoint(self):
        """Verify /api/health returns 200 OK."""
        with make_request("/api/health") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "armor-agent-service")

    def test_11_api_config_endpoint(self):
        """Verify /api/config returns 200 OK and valid configuration."""
        with make_request("/api/config") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("gcp_project_id"), "armor-agent-demo-mau")
        self.assertEqual(data.get("gcp_location"), "us-central1")
        self.assertEqual(set(data.get("available_models", [])), {"gemini-4-argon", "gemini-3.8-flash"})

    # --------------------------------------------------------------------------
    # 4. Adversarial & Stress Probing
    # --------------------------------------------------------------------------
    def test_12_concurrent_burst_stress(self):
        """Stress-test live load balancer with 10 concurrent requests across endpoints."""
        endpoints = [
            "/",
            "/static/styles.css?v=20261019-v2",
            "/static/app.js?v=20261019-v2",
            "/api/templates",
            "/api/floor-setting",
            "/api/health",
            "/api/config",
            "/api/policies",
        ]
        # 10 requests across endpoints
        urls_to_request = [endpoints[i % len(endpoints)] for i in range(10)]

        def fetch_endpoint(url):
            try:
                start = time.perf_counter()
                with make_request(url) as r:
                    status = r.status
                duration = time.perf_counter() - start
                return url, status, duration
            except Exception as e:
                return url, str(e), 0.0

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(fetch_endpoint, urls_to_request))

        failures = [res for res in results if res[1] != 200]
        self.assertEqual(len(failures), 0, f"Encountered non-200 responses under burst: {failures}")

        durations = [res[2] for res in results]
        avg_lat = sum(durations) / len(durations)
        max_lat = max(durations)
        self.assertLess(avg_lat, 3.0, f"Average latency too high: {avg_lat:.3f}s")
        print(f"\n[Stress Test] 10 concurrent requests: 100% 200 OK. Avg: {avg_lat*1000:.1f}ms, Max: {max_lat*1000:.1f}ms")

    def test_13_negative_probing_nonexistent_and_invalid_methods(self):
        """Verify proper 404/405 responses for invalid requests."""
        # Non-existent static file -> 404
        try:
            with make_request("/static/nonexistent_file_xyz123.css") as resp:
                self.fail(f"Expected 404, got {resp.status}")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

        # Invalid method on GET-only /api/templates -> 405
        try:
            with make_request("/api/templates", method="POST", data=b"{}", headers={"Content-Type": "application/json"}) as resp:
                self.fail(f"Expected 405, got {resp.status}")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 405)

        # Invalid method on GET-only /api/health -> 405
        try:
            with make_request("/api/health", method="POST", data=b"{}", headers={"Content-Type": "application/json"}) as resp:
                self.fail(f"Expected 405, got {resp.status}")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 405)

    def test_14_api_policies_endpoint(self):
        """Verify /api/policies returns HTTP 200 with active security policies."""
        with make_request("/api/policies") as resp:
            self.assertEqual(resp.status, 200)
            headers = dict(resp.getheaders())
            content_type = headers.get("content-type", headers.get("Content-Type", ""))
            self.assertIn("application/json", content_type)
            data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("raw_floor_setting", data)
        self.assertIn("model_armor_rules", data)
        self.assertIn("cloud_armor_rules", data)

    def test_15_api_logs_endpoint(self):
        """Verify /api/logs returns HTTP 200 with gcloud command and console url."""
        with make_request("/api/logs?limit=4&vertex_only=true") as resp:
            self.assertEqual(resp.status, 200)
            headers = dict(resp.getheaders())
            content_type = headers.get("content-type", headers.get("Content-Type", ""))
            self.assertIn("application/json", content_type)
            data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("gcloud_command", data)
        self.assertIn("console_url", data)

    def test_16_api_chat_model_guard(self):
        """Verify /api/chat rejects disallowed models with HTTP 400."""
        payload = json.dumps({"message": "Hola", "model": "gpt-4-pro-unauthorized"}).encode("utf-8")
        try:
            with make_request("/api/chat", method="POST", data=payload, headers={"Content-Type": "application/json"}) as resp:
                self.fail(f"Expected 400 for unauthorized model, got {resp.status}")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            err_body = e.read().decode("utf-8")
            self.assertIn("Modelo no permitido", err_body)

    def test_17_api_chat_empty_prompt_guard(self):
        """Verify /api/chat rejects empty prompts with HTTP 400."""
        payload = json.dumps({"message": "   ", "model": "gemini-4-argon"}).encode("utf-8")
        try:
            with make_request("/api/chat", method="POST", data=payload, headers={"Content-Type": "application/json"}) as resp:
                self.fail(f"Expected 400 for empty prompt, got {resp.status}")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            err_body = e.read().decode("utf-8")
            self.assertIn("no puede estar vacío", err_body)

    def test_18_rapid_sequential_burst(self):
        """Run 10 rapid sequential requests against Load Balancer to check jitter and stability."""
        durations = []
        for _ in range(10):
            t0 = time.perf_counter()
            with make_request("/") as resp:
                self.assertEqual(resp.status, 200)
            durations.append(time.perf_counter() - t0)
        avg_seq = sum(durations) / len(durations)
        print(f"\n[Sequential Burst] 10 requests to root: Avg: {avg_seq*1000:.1f}ms, Min: {min(durations)*1000:.1f}ms, Max: {max(durations)*1000:.1f}ms")


if __name__ == "__main__":
    unittest.main()
