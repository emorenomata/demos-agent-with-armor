from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Armor Agent - GCP Security Demo"
    PORT: int = 8080
    HOST: str = "0.0.0.0"

    # GCP Configuration (Cloud Run & Vertex AI)
    GCP_PROJECT_ID: str = "emm-aidominas-summit-mx"
    GCP_LOCATION: str = "us-central1"

    # Model Armor Configuration
    MODEL_ARMOR_TEMPLATE_ID: str = "armor-agent-template"
    MODEL_ARMOR_LOCATION: str = "us-central1"

    # Vertex AI Models (Gemini 2.5, Gemini 3 & Third-Party MaaS in Model Garden)
    DEFAULT_MODEL: str = "gemini-2.5-flash"
    AVAILABLE_MODELS: List[str] = [
        # Familia Google Gemini 2.5
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
        # Familia Google Gemini 3
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-lite",
        # Modelos Abiertos / Terceros en Vertex AI (Model Garden MaaS)
        "openai/gpt-oss-120b-maas",
        "meta/llama-3.3-70b-instruct-maas",
        "google/gemma-4-26b-a4b-it-maas",
        "deepseek-ai/deepseek-v4.1-flash-maas",
        "deepseek-ai/deepseek-r1-0528-maas"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
