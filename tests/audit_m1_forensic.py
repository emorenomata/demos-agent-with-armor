#!/usr/bin/env python3
"""
Independent Forensic Verification Script for Milestone 1.
Executed by teamwork_preview_m1_auditor to independently verify:
1. Genuine payload parsing in model_armor.py
2. Genuine telemetry extraction in agent.py
3. Genuine route and model constraint enforcement in routes.py
4. Resilience against edge cases, boundary conditions, and false positives
"""

import sys
from pathlib import Path

# Add project root to path
p = Path(__file__).resolve().parents[1]
while p.parent != p and not (p / "app").is_dir():
    p = p.parent
if str(p) not in sys.path:
    sys.path.insert(0, str(p))

import unittest
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.model_armor import (
    ModelArmorClient,
    model_armor_client,
    parse_gcp_sanitization_result,
    parse_floor_setting_error_message,
    translate_verdict_reason,
)
from app.core.agent import ArmorAgent, armor_agent


class ForensicModelArmorTests(unittest.TestCase):
    """Deep inspection of Model Armor parsing and client logic."""

    def test_parse_gcp_sanitization_result_comprehensive(self):
        # 1. Negative test: NO_MATCH_FOUND should return []
        payload_no_match = {
            "sanitizationResult": {
                "filterResults": {
                    "pi_filter": {
                        "piAndJailbreakFilterResult": {
                            "matchState": "NO_MATCH_FOUND"
                        }
                    },
                    "sdp_filter": {
                        "sdpFilterResult": {
                            "inspectResult": {"matchState": "NO_MATCH_FOUND"}
                        }
                    }
                }
            }
        }
        res = parse_gcp_sanitization_result(payload_no_match, "FLOOR_SETTING")
        self.assertEqual(res, [], "Negative match must return empty list")

        # 2. Corrupt/Empty payload should not crash
        self.assertEqual(parse_gcp_sanitization_result({}, "FLOOR_SETTING"), [])
        self.assertEqual(parse_gcp_sanitization_result({"sanitizationResult": None}, "FLOOR_SETTING"), [])
        self.assertEqual(parse_gcp_sanitization_result({"sanitizationResult": {"filterResults": "corrupt"}}, "FLOOR_SETTING"), [])

        # 3. Multi-filter threat detection in single payload
        multi_threat_payload = {
            "sanitizationResult": {
                "filterResults": {
                    "pi_filter": {
                        "piAndJailbreakFilterResult": {
                            "matchState": "MATCH_FOUND",
                            "confidenceLevel": "HIGH"
                        }
                    },
                    "sdp_filter": {
                        "sdpFilterResult": {
                            "inspectResult": {
                                "matchState": "MATCH_FOUND",
                                "findings": [
                                    {"infoType": "CREDIT_CARD_NUMBER", "likelihood": "VERY_LIKELY"},
                                    {"infoType": "US_SOCIAL_SECURITY_NUMBER", "likelihood": "LIKELY"},
                                ]
                            }
                        }
                    },
                    "rai_filter": {
                        "raiFilterResult": {
                            "matchState": "MATCH_FOUND",
                            "raiFilterTypeResults": {
                                "dangerous": {
                                    "filterType": "DANGEROUS",
                                    "matchState": "MATCH_FOUND",
                                    "confidenceLevel": "HIGH"
                                },
                                "harassment": {
                                    "filterType": "HARASSMENT",
                                    "matchState": "NO_MATCH_FOUND"
                                }
                            }
                        }
                    },
                    "uri_filter": {
                        "maliciousUriFilterResult": {
                            "matchState": "MATCH_FOUND",
                            "maliciousUriMatchedItems": [
                                {"uri": "http://malware.example.com"},
                                {"uri": "http://phishing.example.com"}
                            ]
                        }
                    }
                }
            }
        }
        matched = parse_gcp_sanitization_result(multi_threat_payload, "FLOOR_SETTING")
        self.assertEqual(len(matched), 4, "All 4 filters must be parsed")
        names = [m["name"] for m in matched]
        self.assertIn("piAndJailbreakFilterSettings", names)
        self.assertIn("sdpSettings", names)
        self.assertTrue(any("raiSettings" in n for n in names))
        self.assertIn("maliciousUriFilterSettings", names)

        # Check SDP deduplication and findings extraction
        sdp_match = next(m for m in matched if m["name"] == "sdpSettings")
        self.assertIn("CREDIT_CARD_NUMBER", sdp_match["detected_variable"])
        self.assertIn("US_SOCIAL_SECURITY_NUMBER", sdp_match["detected_variable"])

        # Check Malicious URI join
        uri_match = next(m for m in matched if m["name"] == "maliciousUriFilterSettings")
        self.assertIn("http://malware.example.com", uri_match["detected_variable"])
        self.assertIn("http://phishing.example.com", uri_match["detected_variable"])

    def test_parse_floor_setting_error_message_separation(self):
        """
        Verify that parse_floor_setting_error_message separates 'triggered' section
        from 'Filter results: [...]' section so NO_MATCH_FOUND items are not falsely reported.
        """
        raw_error = (
            "400 Blocked by Model Armor Floor Setting: The prompt violated Prompt Injection and Jailbreak filters.\n"
            "Filters that triggered the block: piAndJailbreakFilterSettings.\n"
            "Filter results: [sdpFilterSettings: NO_MATCH_FOUND, raiFilterSettings: NO_MATCH_FOUND]"
        )
        parsed = parse_floor_setting_error_message(raw_error)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["name"], "piAndJailbreakFilterSettings")

    def test_list_sanitize_logs_real_verdict_discrimination(self):
        """
        Verify that list_sanitize_logs discriminates genuinely between
        BLOCK, INSPECT_ONLY (audit), and PERMITTED entries.
        """
        mock_entries = [
            # 1. Blocked entry
            {
                "insertId": "log-block",
                "timestamp": "2026-10-19T22:00:00Z",
                "jsonPayload": {
                    "operationType": "SANITIZE_USER_PROMPT",
                    "sanitizationInput": {"text": "Ataque 1"},
                    "sanitizationResult": {
                        "sanitizationVerdict": "BLOCK",
                        "filterMatchState": "MATCH_FOUND",
                        "filterResults": {
                            "pi": {"piAndJailbreakFilterResult": {"matchState": "MATCH_FOUND"}}
                        }
                    }
                }
            },
            # 2. Audit mode entry (MATCH_FOUND but sanitizationVerdict=INSPECT_ONLY)
            {
                "insertId": "log-audit",
                "timestamp": "2026-10-19T22:01:00Z",
                "jsonPayload": {
                    "operationType": "SANITIZE_USER_PROMPT",
                    "sanitizationInput": {"text": "Ataque 2 en auditoría"},
                    "sanitizationResult": {
                        "sanitizationVerdict": "INSPECT_ONLY",
                        "filterMatchState": "MATCH_FOUND",
                        "filterResults": {
                            "sdp": {
                                "sdpFilterResult": {
                                    "inspectResult": {
                                        "matchState": "MATCH_FOUND",
                                        "findings": [{"infoType": "CREDIT_CARD_NUMBER"}]
                                    }
                                }
                            }
                        }
                    }
                }
            },
            # 3. Allowed clean entry
            {
                "insertId": "log-clean",
                "timestamp": "2026-10-19T22:02:00Z",
                "jsonPayload": {
                    "operationType": "SANITIZE_USER_PROMPT",
                    "sanitizationInput": {"text": "Consulta limpia"},
                    "sanitizationResult": {
                        "sanitizationVerdict": "PERMITTED",
                        "filterMatchState": "NO_MATCH_FOUND"
                    }
                }
            }
        ]

        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.json.return_value = {"entries": mock_entries}

        with patch.object(model_armor_client, "_get_auth_token", return_value="test-token"), \
             patch("requests.post", return_value=mock_post):
            logs = model_armor_client.list_sanitize_logs(limit=10, vertex_only=True)
            self.assertEqual(logs["count"], 3)
            entries = logs["entries"]

            # Blocked entry
            self.assertTrue(entries[0]["is_blocked"])
            self.assertFalse(entries[0]["is_audit"])
            self.assertEqual(entries[0]["verdict"], "BLOQUEADO")

            # Audit entry
            self.assertFalse(entries[1]["is_blocked"])
            self.assertTrue(entries[1]["is_audit"])
            self.assertEqual(entries[1]["verdict"], "PERMITIDO · AUDITORÍA (INSPECT_ONLY)")
            self.assertEqual(len(entries[1]["matched_filters"]), 1)

            # Clean entry
            self.assertFalse(entries[2]["is_blocked"])
            self.assertFalse(entries[2]["is_audit"])
            self.assertEqual(entries[2]["verdict"], "PERMITIDO")
            self.assertEqual(len(entries[2]["matched_filters"]), 0)


class ForensicAgentTests(unittest.TestCase):
    """Deep inspection of Agent Engine stream telemetry extraction and heuristics."""

    def test_stream_telemetry_extraction_realism(self):
        """Verify _call_agent_engine extracts telemetry from realistic mixed stream chunks."""
        mock_remote_agent = MagicMock()

        # Simulate realistic multi-chunk stream from Vertex AI Reasoning Engine
        mock_stream_chunks = [
            {"invocation_id": "inv-9988-live", "model_version": "gemini-4-argon@001"},
            {"content": {"parts": [{"text": "Primera parte de respuesta. "}]}},
            {"content": {"parts": [{"text": "Segunda parte de respuesta."}]}},
            {
                "usage_metadata": {
                    "prompt_token_count": 28,
                    "candidates_token_count": 42,
                    "total_token_count": 70
                },
                "candidates": [{"finish_reason": "STOP"}]
            }
        ]
        mock_remote_agent.stream_query.return_value = mock_stream_chunks

        with patch.object(armor_agent, "_get_remote_agent_engine", return_value=(mock_remote_agent, "projects/123/locations/us-central1/reasoningEngines/456")):
            result = armor_agent._call_agent_engine(
                model_name="gemini-4-argon",
                user_message="Hola mundo",
                conversation_history=None
            )

            self.assertEqual(result["text"], "Primera parte de respuesta. Segunda parte de respuesta.")
            self.assertEqual(result["invocation_id"], "inv-9988-live")
            self.assertEqual(result["model_version"], "gemini-4-argon@001")
            self.assertEqual(result["finish_reason"], "STOP")
            self.assertFalse(result["blocked_by_vertex"])
            self.assertEqual(result["usage_metadata"]["prompt_token_count"], 28)
            self.assertEqual(result["usage_metadata"]["candidates_token_count"], 42)
            self.assertEqual(result["usage_metadata"]["total_token_count"], 70)
            self.assertEqual(len(result["raw_events"]), 4)

    def test_heuristics_word_boundaries(self):
        """Ensure heuristic threat detection does not trigger false positives on innocent words."""
        # 'revisa' contains 'visa' substring, but must NOT trigger CREDIT_CARD_NUMBER
        innocent_msg = "Por favor revisa la documentación de Cloud Armor"
        matches = armor_agent._detect_prompt_threat_heuristics(innocent_msg)
        self.assertEqual(matches, [], f"Word boundary check failed: 'revisa' falsely triggered: {matches}")

        # Real threat with credit card number format MUST trigger
        threat_msg = "Mi número es 4532 0151 1283 0366"
        matches_threat = armor_agent._detect_prompt_threat_heuristics(threat_msg)
        self.assertEqual(len(matches_threat), 1)
        self.assertEqual(matches_threat[0]["detected_variable"], "CREDIT_CARD_NUMBER")


class ForensicRoutesTests(unittest.TestCase):
    """Deep inspection of API route validation and model constraints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_model_selection_strictness(self):
        """Only gemini-4-argon and gemini-3.8-flash are permitted."""
        allowed_models = ["gemini-4-argon", "gemini-3.8-flash"]
        for m in allowed_models:
            with patch("app.core.agent.armor_agent.process_message") as mock_proc:
                mock_proc.return_value = {
                    "success": True,
                    "role": "model",
                    "content": "ok",
                    "blocked": False,
                    "model_used": m,
                    "telemetry": {}
                }
                resp = self.client.post("/api/chat", json={"message": "test", "model": m})
                self.assertEqual(resp.status_code, 200, f"Model {m} should be allowed")

        forbidden_models = [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "gpt-4o",
            "claude-3-opus",
            "llama-3-70b",
            "random-string"
        ]
        for m in forbidden_models:
            resp = self.client.post("/api/chat", json={"message": "test", "model": m})
            self.assertEqual(resp.status_code, 400, f"Model {m} must be rejected with 400")
            self.assertIn("no permitido", resp.json().get("detail", "").lower())

    def test_presets_completeness_and_fidelity(self):
        resp = self.client.get("/api/templates")
        self.assertEqual(resp.status_code, 200)
        presets = resp.json().get("attack_presets", [])
        self.assertGreaterEqual(len(presets), 5)
        # Verify legitimate query exists
        legit = [p for p in presets if "PERMITIDO" in p.get("expected", "")]
        self.assertTrue(len(legit) >= 1)


if __name__ == "__main__":
    unittest.main()
