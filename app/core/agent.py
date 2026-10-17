import asyncio
import logging
import re
import time
from typing import Dict, Any, List, Optional
import google.auth
import google.auth.transport.requests
import requests
from google import genai
from google.genai import types
from app.core.config import settings
from app.core.model_armor import model_armor_client, ModelArmorResult

logger = logging.getLogger(__name__)

# Models in Vertex AI that require the 'global' endpoint instead of regional 'us-central1'
GLOBAL_ENDPOINT_MODELS = {
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
    "google/gemma-4-26b-a4b-it-maas",
    "deepseek-ai/deepseek-v4.1-flash-maas",
}


class ArmorAgent:
    """
    Production Agent Core running on Google Cloud Run.
    Uses Application Default Credentials (ADC) to invoke:
      1. Google Cloud Model Armor API (v1)
      2. Google Cloud Vertex AI (Gemini 2.5, Gemini 3, and Third-Party Model Garden MaaS)
    """

    def __init__(self):
        self._clients: Dict[str, genai.Client] = {}
        self._credentials = None

    def _get_vertex_client(self, location: str) -> genai.Client:
        if location not in self._clients:
            self._clients[location] = genai.Client(
                vertexai=True,
                project=settings.GCP_PROJECT_ID,
                location=location
            )
        return self._clients[location]

    def _get_adc_token(self) -> str:
        if self._credentials is None:
            self._credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        if not self._credentials.valid:
            auth_req = google.auth.transport.requests.Request()
            self._credentials.refresh(auth_req)
        return self._credentials.token

    @staticmethod
    def _clean_response_text(text: str) -> str:
        if not text:
            return ""
        # Strip internal <think>...</think> reasoning blocks from DeepSeek R1 / Thinking models
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        return cleaned or text.strip()

    def _call_vertex_openai_maas(
        self,
        model_name: str,
        system_instruction: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        locations: Optional[List[str]] = None
    ) -> str:
        """
        Invokes Vertex AI Model Garden Serverless MaaS via the native OpenAI-compatible
        Chat Completions endpoint (/endpoints/openapi/chat/completions).
        Used for third-party models like meta/llama-3.3-70b-instruct-maas.
        """
        token = self._get_adc_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        messages = [{"role": "system", "content": system_instruction}]
        if conversation_history:
            for turn in conversation_history[-6:]:
                role = "user" if turn.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": turn.get("content", "")})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1600
        }

        target_locations = locations or [settings.GCP_LOCATION, "global", "us-east5"]
        last_error = ""

        for loc in target_locations:
            host = "aiplatform.googleapis.com" if loc == "global" else f"{loc}-aiplatform.googleapis.com"
            url = (
                f"https://{host}/v1beta1/projects/{settings.GCP_PROJECT_ID}"
                f"/locations/{loc}/endpoints/openapi/chat/completions"
            )
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        return self._clean_response_text(content)
                last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
            except Exception as e:
                last_error = str(e)

        raise RuntimeError(f"Error invocando modelo MaaS '{model_name}': {last_error}")

    def _call_vertex_llm(
        self,
        model_name: str,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        system_instruction = (
            "Eres un asistente virtual útil y directo. "
            "Responde siempre en español de forma breve, clara y concisa "
            "(máximo 2 párrafos cortos o de 3 a 5 viñetas puntuales), "
            "evitando introducciones extensas o texto de relleno."
        )

        # Determine preferred location order for this model
        if model_name in GLOBAL_ENDPOINT_MODELS or model_name.startswith("gemini-3"):
            locations_to_try = ["global", settings.GCP_LOCATION]
        else:
            locations_to_try = [settings.GCP_LOCATION, "global"]

        contents = []
        if conversation_history:
            for turn in conversation_history[-6:]:
                role = "user" if turn.get("role") == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=turn.get("content", ""))]
                ))

        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        ))

        last_exc: Optional[Exception] = None
        for loc in locations_to_try:
            try:
                client = self._get_vertex_client(loc)
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        max_output_tokens=1600
                    )
                )
                return self._clean_response_text(response.text or "")
            except Exception as exc:
                last_exc = exc
                logger.warning(f"generate_content failed for {model_name} in {loc}: {exc}")

        # If it's a third-party publisher model (e.g. meta/llama-3.3-70b-instruct-maas),
        # try the Vertex AI OpenAI-compatible MaaS endpoint before failing
        if "/" in model_name:
            try:
                return self._call_vertex_openai_maas(
                    model_name=model_name,
                    system_instruction=system_instruction,
                    user_message=user_message,
                    conversation_history=conversation_history,
                    locations=locations_to_try + ["us-east5"]
                )
            except Exception as maas_exc:
                logger.warning(f"OpenAI MaaS fallback failed for {model_name}: {maas_exc}")

        raise last_exc

    async def process_message(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        model_name: Optional[str] = None,
        bypass_armor: bool = False
    ) -> Dict[str, Any]:
        selected_model = model_name or settings.DEFAULT_MODEL
        turn_start = time.time()

        # ---------------------------------------------------------
        # ETAPA 1: Inspección de Entrada en GCP Model Armor
        # ---------------------------------------------------------
        input_inspection: ModelArmorResult = await asyncio.to_thread(
            model_armor_client.sanitize_user_prompt,
            user_message,
            bypass_armor
        )

        if input_inspection.is_blocked:
            total_time = (time.time() - turn_start) * 1000
            return {
                "success": False,
                "role": "model",
                "content": input_inspection.message,
                "blocked": True,
                "model_used": selected_model,
                "telemetry": {
                    "total_latency_ms": round(total_time, 2),
                    "input_inspection": input_inspection.to_dict(),
                    "output_inspection": {
                        "action": "SKIPPED",
                        "latency_ms": 0.0,
                        "matched_filters": []
                    },
                    "llm_executed": False
                }
            }

        # ---------------------------------------------------------
        # ETAPA 2: Inferencia en Vertex AI (Gemini / Model Garden)
        # ---------------------------------------------------------
        llm_start = time.time()
        raw_llm_response = await asyncio.to_thread(
            self._call_vertex_llm,
            selected_model,
            user_message,
            conversation_history
        )
        llm_latency = (time.time() - llm_start) * 1000

        # ---------------------------------------------------------
        # ETAPA 3: Inspección de Salida en GCP Model Armor
        # ---------------------------------------------------------
        output_inspection: ModelArmorResult = await asyncio.to_thread(
            model_armor_client.sanitize_model_response,
            raw_llm_response,
            bypass_armor
        )

        final_content = output_inspection.sanitized_content or raw_llm_response
        if output_inspection.is_blocked:
            final_content = output_inspection.message

        total_time = (time.time() - turn_start) * 1000

        return {
            "success": True,
            "role": "model",
            "content": final_content,
            "blocked": output_inspection.is_blocked,
            "model_used": selected_model,
            "telemetry": {
                "total_latency_ms": round(total_time, 2),
                "llm_latency_ms": round(llm_latency, 2),
                "input_inspection": input_inspection.to_dict(),
                "output_inspection": output_inspection.to_dict(),
                "llm_executed": True
            }
        }


armor_agent = ArmorAgent()
