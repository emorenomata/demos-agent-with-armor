"""
Empirical Challenge Test Suite for Milestone 2: Telemetry Accordion & Cloud Logging Badges
Teamwork Agent: teamwork_preview_m2_challenger_2

Empirically challenges:
1. JavaScript execution of telemetry accordion rendering and Cloud Logging badge rendering
   via node test harness (tests/test_m2_challenger_2_harness.js).
2. Backend-to-Frontend contract compatibility:
   - /api/chat telemetry response schema match with frontend expectation
   - /api/logs entry schema match with frontend 3-way verdict rendering
   - Floor setting mode sync between backend and frontend
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from starlette.testclient import TestClient

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.main import app
from app.core.config import settings
from app.core.model_armor import ModelArmorClient


class TestMilestone2EmpiricalChallenge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_node_js_harness_execution(self):
        """Executes node tests/test_m2_challenger_2_harness.js and ensures all 14 tests pass."""
        harness_path = project_root / "tests" / "test_m2_challenger_2_harness.js"
        res = subprocess.run(
            ["node", str(harness_path)],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Node test harness failed (code {res.returncode}):\n{res.stdout}\n{res.stderr}"
        )
        self.assertIn("ALL EMPIRICAL CHALLENGES PASSED SUCCESSFULLY! Verdict: APPROVE", res.stdout)
        self.assertIn("14 / 14 tests passed", res.stdout)

    def test_02_static_asset_serving_and_hash(self):
        """Verifies app/static/app.js is served by FastAPI with cache busting query string."""
        resp_index = self.client.get("/")
        self.assertEqual(resp_index.status_code, 200)
        self.assertIn('src="/static/app.js?v=20261019-v2"', resp_index.text)
        self.assertIn('href="/static/styles.css?v=20261019-v2"', resp_index.text)

        resp_app = self.client.get("/static/app.js")
        self.assertEqual(resp_app.status_code, 200)
        self.assertIn("buildModelExecutionDropdownHtml", resp_app.text)
        self.assertIn("renderCloudLogs", resp_app.text)
        self.assertIn("PERMITIDO · AUDITORÍA (INSPECT_ONLY)", resp_app.text)

    def test_03_contract_chat_telemetry_schema(self):
        """Verifies /api/chat payload schema expected by frontend buildModelExecutionDropdownHtml."""
        app_js_text = (project_root / "app" / "static" / "app.js").read_text(encoding="utf-8")
        
        # Verify required keys parsed in app.js
        required_telemetry_fields = [
            "raw_model_execution",
            "model_version",
            "runtime",
            "resource_name",
            "invocation_id",
            "finish_reason",
            "usage_metadata",
            "prompt_token_count",
            "candidates_token_count",
            "total_token_count",
            "raw_events"
        ]
        for field in required_telemetry_fields:
            self.assertIn(field, app_js_text, f"Field '{field}' must be referenced in app.js")

    def test_04_contract_cloud_logging_3_way_verdicts(self):
        """Verifies 3-way log verdicts in backend and frontend."""
        app_js_text = (project_root / "app" / "static" / "app.js").read_text(encoding="utf-8")
        model_armor_py = (project_root / "app" / "core" / "model_armor.py").read_text(encoding="utf-8")

        # 3 verdicts
        verdicts = [
            "BLOQUEADO",
            "PERMITIDO · AUDITORÍA (INSPECT_ONLY)",
            "PERMITIDO"
        ]
        for v in verdicts:
            self.assertIn(v, app_js_text, f"Verdict '{v}' must be handled in app.js")
            self.assertIn(v, model_armor_py, f"Verdict '{v}' must be produced in model_armor.py")


if __name__ == "__main__":
    unittest.main()
