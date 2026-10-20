import json
from pathlib import Path
from typing import Dict, List
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_default_agent_engine() -> str:
    id_file = Path(__file__).resolve().parents[2] / ".agent_engine_id"
    if id_file.exists():
        return id_file.read_text(encoding="utf-8").strip()
    return ""


def _load_agent_engine_map() -> Dict[str, str]:
    ids_file = Path(__file__).resolve().parents[2] / ".agent_engine_ids.json"
    if ids_file.exists():
        try:
            data = json.loads(ids_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items() if v}
        except Exception:
            pass
    default_id = _load_default_agent_engine()
    if default_id:
        return {"gemini-4-argon": default_id}
    return {}


class Settings(BaseSettings):
    PROJECT_NAME: str = "Armor Agent - GCP Security Demo"
    PORT: int = 8080
    HOST: str = "0.0.0.0"

    # GCP Configuration (Cloud Run & Vertex AI)
    GCP_PROJECT_ID: str = "your-gcp-project-id"
    GCP_LOCATION: str = "us-central1"

    # Model Armor Configuration (Floor Settings + Diagnostic Template)
    MODEL_ARMOR_TEMPLATE_ID: str = "armor-agent-template"
    MODEL_ARMOR_LOCATION: str = "us-central1"

    # Vertex AI Agent Engine (Reasoning Engine Runtime)
    AGENT_ENGINE_RESOURCE_NAME: str = _load_default_agent_engine()
    AGENT_ENGINE_ARGON_RESOURCE_NAME: str = ""
    AGENT_ENGINE_FLASH_RESOURCE_NAME: str = ""
    AGENT_ENGINE_MAP: Dict[str, str] = _load_agent_engine_map()

    # Exclusivamente Gemini 4 Argon y Gemini 3.8 Flash desde Vertex AI Agent Platform (Agent Engine)
    DEFAULT_MODEL: str = "gemini-4-argon"
    AVAILABLE_MODELS: List[str] = [
        "gemini-4-argon",
        "gemini-3.8-flash",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

