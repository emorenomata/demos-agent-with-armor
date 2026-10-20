#!/usr/bin/env python3
"""
Script para desplegar los agentes ADK puros (`adk_agent/agent.py`) para
`gemini-4-argon` y `gemini-3.8-flash` en Google Cloud Vertex AI Agent Engine
(Reasoning Engine Runtime).
"""
import argparse
import json
import os
import sys
from typing import Dict

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import vertexai
from google.cloud import storage
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp
from adk_agent.agent import argon_agent, flash_agent


AGENTS_TO_DEPLOY = {
    "gemini-4-argon": {
        "display_name": "armor-demo-adk-gemini-4-argon",
        "agent": argon_agent,
    },
    "gemini-3.8-flash": {
        "display_name": "armor-demo-adk-gemini-3-8-flash",
        "agent": flash_agent,
    },
}


def ensure_staging_bucket(project_id: str, location: str, bucket_name: str) -> str:
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    if not bucket.exists():
        print(f"📦 Creando bucket de staging gs://{bucket_name} en {location}...")
        bucket = storage_client.create_bucket(bucket_name, location=location)
    else:
        print(f"📦 Bucket de staging existente: gs://{bucket_name}")
    return f"gs://{bucket_name}"


def deploy_or_get_agent_engines(
    project_id: str,
    location: str,
    force_new: bool = False
) -> Dict[str, str]:
    bucket_name = f"{project_id}-agent-staging"
    staging_bucket = ensure_staging_bucket(project_id, location, bucket_name)

    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
    )

    existing_by_name: Dict[str, str] = {}
    if not force_new:
        print(f"🔍 Consultando agentes existentes en Vertex AI Agent Engine ({location})...")
        for existing in agent_engines.list():
            d_name = getattr(existing, "display_name", "")
            if d_name:
                existing_by_name[d_name] = existing.resource_name

    deployed_map: Dict[str, str] = {}

    for model_key, cfg in AGENTS_TO_DEPLOY.items():
        display_name = cfg["display_name"]
        adk_agent_obj = cfg["agent"]

        if not force_new and display_name in existing_by_name:
            res_name = existing_by_name[display_name]
            print(f"✅ Agente existente para '{model_key}' ({display_name}): {res_name}")
            deployed_map[model_key] = res_name
            continue

        print(f"🚀 Desplegando agente ADK puro '{display_name}' ({model_key}) en Vertex AI Agent Engine...")
        adk_app = AdkApp(
            agent=adk_agent_obj,
            enable_tracing=True,
            env_vars={
                "GOOGLE_CLOUD_LOCATION": "global",
            },
        )

        remote_agent = agent_engines.create(
            adk_app,
            display_name=display_name,
            description=(
                f"Agente ADK puro ({model_key} - Zero-Code Security) protegido automáticamente por "
                f"Model Armor Floor Settings a nivel de proyecto en Vertex AI."
            ),
            requirements=[
                "google-adk==1.14.1",
                "google-cloud-aiplatform[adk,agent_engines]==1.148.1",
                "cloudpickle>=3.0.0",
            ],
            extra_packages=["./adk_agent"],
            env_vars={
                "GOOGLE_CLOUD_LOCATION": "global",
            },
        )

        print(f"🎉 Agente '{model_key}' desplegado exitosamente en Vertex AI Agent Engine:")
        print(f"   RESOURCE_NAME={remote_agent.resource_name}")
        deployed_map[model_key] = remote_agent.resource_name

    return deployed_map


if __name__ == "__main__":
    import google.auth

    default_project = os.getenv("GCP_PROJECT_ID", "")
    if not default_project:
        try:
            _, default_project = google.auth.default()
        except Exception:
            default_project = ""

    parser = argparse.ArgumentParser(description="Deploy ADK Agents to Vertex AI Agent Engine")
    parser.add_argument("--project-id", default=default_project, help="Google Cloud Project ID")
    parser.add_argument("--location", default=os.getenv("GCP_LOCATION", "us-central1"))
    parser.add_argument("--force-new", action="store_true", help="Create new Agent Engine instances")
    args = parser.parse_args()

    if not args.project_id:
        print("❌ Error: Debe especificar --project-id o definir GCP_PROJECT_ID.")
        sys.exit(1)

    deployed = deploy_or_get_agent_engines(args.project_id, args.location, args.force_new)

    with open(".agent_engine_ids.json", "w", encoding="utf-8") as f:
        json.dump(deployed, f, indent=2)

    primary_id = deployed.get("gemini-4-argon", "")
    if primary_id:
        with open(".agent_engine_id", "w", encoding="utf-8") as f:
            f.write(primary_id.strip() + "\n")

    print("\n📋 Mapa de Agentes en Vertex AI Agent Engine:")
    print(json.dumps(deployed, indent=2))


