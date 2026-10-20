"""
Adversarial Empirical Challenge Suite for Milestone 1
Teamwork Agent: teamwork_preview_m1_challenger_2

Validates:
1. set_floor_setting_mode cache transitions and rapid toggling between True and False.
2. Direct caching vs routes.py forced bypass.
3. Thread-safety under concurrent toggles.
4. Input validation and edge cases for /api/floor-setting.
5. Input validation and edge cases for /api/chat.
6. Strict model restriction:
   - gemini-4-argon and gemini-3.8-flash are permitted (200)
   - omitted model defaults to gemini-4-argon (200)
   - all other model identifiers (including empty string '') must be strictly rejected with HTTP 400.
"""

import sys
import unittest
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from starlette.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.model_armor import ModelArmorClient, model_armor_client


class TestFloorSettingCacheTransitions(unittest.TestCase):
    """
    Empirical challenge on set_floor_setting_mode cache transitions:
    - Verifies cache hits vs cache misses
    - Verifies force=True overrides cache
    - Verifies invalidate_cache clears state
    - Verifies rapid toggling between True and False
    """

    def setUp(self):
        self.client = ModelArmorClient()
        self.client.invalidate_cache()

    @patch("requests.patch")
    @patch.object(ModelArmorClient, "_get_auth_token", return_value="mock-token")
    def test_cache_hit_on_same_mode(self, mock_auth, mock_patch):
        mock_patch.return_value.status_code = 200
        mock_patch.return_value.json.return_value = {
            "name": "projects/test/locations/global/floorSetting",
            "enableFloorSettingEnforcement": True,
            "aiPlatformFloorSetting": {"inspectAndBlock": True, "enableCloudLogging": True}
        }

        # First call: cache miss -> network call made
        res1 = self.client.set_floor_setting_mode(inspect_and_block=True, force=False)
        self.assertFalse(res1.get("cached"))
        self.assertEqual(mock_patch.call_count, 1)

        # Second call with same mode: cache hit -> NO network call
        res2 = self.client.set_floor_setting_mode(inspect_and_block=True, force=False)
        self.assertTrue(res2.get("cached"))
        self.assertEqual(mock_patch.call_count, 1)

        # Third call with force=True: cache bypass -> network call made
        res3 = self.client.set_floor_setting_mode(inspect_and_block=True, force=True)
        self.assertFalse(res3.get("cached"))
        self.assertEqual(mock_patch.call_count, 2)

    @patch("requests.patch")
    @patch.object(ModelArmorClient, "_get_auth_token", return_value="mock-token")
    def test_rapid_alternating_toggles(self, mock_auth, mock_patch):
        mock_patch.return_value.status_code = 200
        mock_patch.return_value.json.return_value = {"status": "ok"}

        # Rapidly alternate 20 times between True and False
        expected_calls = 0
        for i in range(20):
            target = (i % 2 == 0)
            res = self.client.set_floor_setting_mode(inspect_and_block=target, force=False)
            expected_calls += 1
            self.assertFalse(res.get("cached"), f"Toggle {i} should be a cache miss")
            self.assertEqual(res.get("inspectAndBlock"), target)
            self.assertEqual(mock_patch.call_count, expected_calls)

    @patch("requests.patch")
    @patch.object(ModelArmorClient, "_get_auth_token", return_value="mock-token")
    def test_invalidate_cache_forces_refresh(self, mock_auth, mock_patch):
        mock_patch.return_value.status_code = 200
        mock_patch.return_value.json.return_value = {"status": "ok"}

        self.client.set_floor_setting_mode(inspect_and_block=True)
        self.assertEqual(mock_patch.call_count, 1)

        self.client.invalidate_cache()
        self.assertIsNone(self.client._current_mode)
        self.assertIsNone(self.client._current_inspect_and_block)

        res = self.client.set_floor_setting_mode(inspect_and_block=True)
        self.assertFalse(res.get("cached"))
        self.assertEqual(mock_patch.call_count, 2)

    @patch("requests.patch")
    @patch.object(ModelArmorClient, "_get_auth_token", return_value="mock-token")
    def test_concurrent_identical_toggles_leverage_cache(self, mock_auth, mock_patch):
        mock_patch.return_value.status_code = 200
        mock_patch.return_value.json.return_value = {"status": "ok"}

        # Prime cache
        self.client.set_floor_setting_mode(inspect_and_block=True, force=False)
        self.assertEqual(mock_patch.call_count, 1)

        cache_hits = []
        def worker():
            r = self.client.set_floor_setting_mode(inspect_and_block=True, force=False)
            if r.get("cached"):
                cache_hits.append(True)

        threads = [threading.Thread(target=worker) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(cache_hits), 30)
        self.assertEqual(mock_patch.call_count, 1)


class TestFloorSettingEndpointEdgeCases(unittest.TestCase):
    """
    Empirical challenge on /api/floor-setting HTTP endpoint.
    """

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_post_floor_setting_missing_body(self):
        response = self.client.post("/api/floor-setting", json={})
        self.assertEqual(response.status_code, 422)

    def test_post_floor_setting_invalid_type_string(self):
        response = self.client.post("/api/floor-setting", json={"inspect_and_block": "not_a_bool"})
        self.assertEqual(response.status_code, 422)

    def test_post_floor_setting_invalid_type_null(self):
        response = self.client.post("/api/floor-setting", json={"inspect_and_block": None})
        self.assertEqual(response.status_code, 422)

    def test_unsupported_http_methods(self):
        del_resp = self.client.delete("/api/floor-setting")
        self.assertEqual(del_resp.status_code, 405)

        put_resp = self.client.put("/api/floor-setting", json={"inspect_and_block": True})
        self.assertEqual(put_resp.status_code, 405)

    @patch("requests.patch")
    @patch.object(ModelArmorClient, "_get_auth_token", return_value="mock-token")
    def test_post_floor_setting_caches_subsequent_identical_requests(self, mock_auth, mock_patch):
        """
        Verifies that routes.py passes force=False, so subsequent identical requests
        hit the cache and avoid redundant GCP network calls.
        """
        mock_patch.return_value.status_code = 200
        mock_patch.return_value.json.return_value = {"status": "ok"}
        model_armor_client.invalidate_cache()

        resp1 = self.client.post("/api/floor-setting", json={"inspect_and_block": True})
        self.assertEqual(resp1.status_code, 200)
        self.assertFalse(resp1.json()["cached"])
        self.assertEqual(mock_patch.call_count, 1)

        # Second identical request: in routes.py force=False is passed, so cached is True
        resp2 = self.client.post("/api/floor-setting", json={"inspect_and_block": True})
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()["cached"], "Subsequent identical request should hit cache")
        self.assertEqual(mock_patch.call_count, 1, "Should not trigger unnecessary second GCP call")


class TestChatEndpointModelRestriction(unittest.TestCase):
    """
    Empirical challenge on model restrictions:
    - ONLY gemini-4-argon and gemini-3.8-flash are permitted
    - Anything else MUST be strictly rejected with HTTP 400
    """

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    @patch("app.api.routes.armor_agent.process_message")
    def test_permitted_models_argon_and_flash(self, mock_process):
        mock_process.return_value = {
            "success": True,
            "role": "model",
            "content": "ok",
            "blocked": False,
            "model_used": "gemini-4-argon",
            "telemetry": {}
        }

        resp_argon = self.client.post("/api/chat", json={
            "message": "Hola",
            "model": "gemini-4-argon"
        })
        self.assertEqual(resp_argon.status_code, 200)

        resp_flash = self.client.post("/api/chat", json={
            "message": "Hola",
            "model": "gemini-3.8-flash"
        })
        self.assertEqual(resp_flash.status_code, 200)

        # Omitted model defaults to gemini-4-argon
        resp_omitted = self.client.post("/api/chat", json={
            "message": "Hola"
        })
        self.assertEqual(resp_omitted.status_code, 200)

    def test_rejected_unsupported_models_400(self):
        forbidden_models = [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "gemini-pro",
            "gpt-4",
            "gpt-4o",
            "claude-3-5-sonnet",
            "llama-3-70b",
            "GEMINI-4-ARGON",
            "gemini-4-argon ",
            " gemini-4-argon",
            "   ",
        ]

        for model_name in forbidden_models:
            with self.subTest(model=model_name):
                resp = self.client.post("/api/chat", json={
                    "message": "Hola",
                    "model": model_name
                })
                self.assertEqual(
                    resp.status_code,
                    400,
                    f"Model '{model_name}' was NOT rejected with 400! Got {resp.status_code}"
                )
                self.assertIn("Modelo no permitido", resp.json().get("detail", ""))

    @patch("app.api.routes.armor_agent.process_message")
    def test_empty_string_model_rejected_400(self, mock_process):
        """
        Verifies that when model is empty string '', routes.py strictly rejects it
        with HTTP 400 Bad Request instead of bypassing validation.
        """
        resp = self.client.post("/api/chat", json={
            "message": "Hola",
            "model": ""
        })
        self.assertEqual(
            resp.status_code,
            400,
            "model='' must be rejected with 400!"
        )
        self.assertIn("Modelo no permitido", resp.json().get("detail", ""))


class TestChatEndpointEdgeCases(unittest.TestCase):
    """
    Empirical challenge on /api/chat input validation.
    """

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_empty_message_400(self):
        resp = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("El mensaje no puede estar vacío", resp.json().get("detail", ""))

    def test_whitespace_message_400(self):
        for whitespace_sample in ["   ", "\n\t  \r", "    \n    "]:
            with self.subTest(msg=repr(whitespace_sample)):
                resp = self.client.post("/api/chat", json={"message": whitespace_sample})
                self.assertEqual(resp.status_code, 400)
                self.assertIn("El mensaje no puede estar vacío", resp.json().get("detail", ""))

    def test_missing_message_field_422(self):
        resp = self.client.post("/api/chat", json={})
        self.assertEqual(resp.status_code, 422)

    def test_malformed_history_items_422(self):
        resp = self.client.post("/api/chat", json={
            "message": "Hola",
            "history": ["string instead of dict"]
        })
        self.assertEqual(resp.status_code, 422)

    def test_invalid_bypass_armor_field_422(self):
        resp = self.client.post("/api/chat", json={
            "message": "Hola",
            "bypass_model_armor": "invalid_boolean_string"
        })
        self.assertEqual(resp.status_code, 422)

    def test_chat_get_method_not_allowed_405(self):
        resp = self.client.get("/api/chat")
        self.assertEqual(resp.status_code, 405)


if __name__ == "__main__":
    unittest.main()
