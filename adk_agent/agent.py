import os
from google.adk.agents import Agent

# ============================================================================
# AGENTES PUROS EN GOOGLE ADK (Desplegados en Vertex AI Agent Engine)
# ============================================================================
# Nota para la Demo:
# Estos agentes NO contienen ninguna librería, importación ni configuración de
# Google Cloud Model Armor. La protección ocurre de forma 100% transparente
# y obligatoria a nivel de proyecto en GCP mediante el Floor Setting de
# Model Armor integrado con Vertex AI (integratedServices: ["AI_PLATFORM"]).
#
# Los modelos de última generación (gemini-4-argon y gemini-3.8-flash) operan
# sobre el endpoint global de Vertex AI (GOOGLE_CLOUD_LOCATION="global").
# ============================================================================
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

COMMON_INSTRUCTION = (
    "Eres un asistente virtual corporativo útil y directo desplegado en "
    "Google Cloud Vertex AI Agent Engine (ADK). "
    "Responde siempre en español de forma breve, clara y concisa "
    "(máximo 2 párrafos cortos o de 3 a 5 viñetas puntuales), "
    "evitando introducciones extensas o texto de relleno."
)


def create_adk_agent(model_name: str = "gemini-4-argon") -> Agent:
    safe_suffix = model_name.replace("-", "_").replace(".", "_")
    return Agent(
        name=f"armor_demo_{safe_suffix}",
        model=model_name,
        description=(
            f"Asistente virtual corporativo ejecutándose en Vertex AI Agent Engine ({model_name})."
        ),
        instruction=COMMON_INSTRUCTION,
    )


argon_agent = create_adk_agent("gemini-4-argon")
flash_agent = create_adk_agent("gemini-3.8-flash")

# Por defecto, root_agent apunta a gemini-4-argon
root_agent = argon_agent

