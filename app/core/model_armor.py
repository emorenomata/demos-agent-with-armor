import logging
import time
from typing import Dict, Any, Optional, List, Tuple
import google.auth
import google.auth.transport.requests
import requests
from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelArmorResult:
    def __init__(
        self,
        is_blocked: bool,
        action: str,  # "ALLOWED", "BLOCKED"
        message: Optional[str] = None,
        sanitized_content: Optional[str] = None,
        matched_filters: Optional[List[Dict[str, Any]]] = None,
        latency_ms: float = 0.0,
        raw_response: Optional[Dict[str, Any]] = None
    ):
        self.is_blocked = is_blocked
        self.action = action
        self.message = message
        self.sanitized_content = sanitized_content
        self.matched_filters = matched_filters or []
        self.latency_ms = latency_ms
        self.raw_response = raw_response or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_blocked": self.is_blocked,
            "action": self.action,
            "message": self.message,
            "sanitized_content": self.sanitized_content,
            "matched_filters": self.matched_filters,
            "latency_ms": round(self.latency_ms, 2),
            "raw_response": self.raw_response
        }


def translate_verdict_reason(reason: str) -> str:
    if not reason:
        return ""
    translations = {
        "Blocked by Model Armor Floor Setting: The prompt violated Prompt Injection and Jailbreak filters.": (
            "Bloqueado por Model Armor Floor Setting (Entrada): El prompt violó los filtros de Inyección de Prompt y Jailbreak."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated Sensitive Data Protection filters.": (
            "Bloqueado por Model Armor Floor Setting (Entrada): El prompt violó los filtros de Protección de Datos Sensibles (SDP / PII)."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated SDP/PII filters.": (
            "Bloqueado por Model Armor Floor Setting (Entrada): El prompt violó los filtros de Protección de Datos Sensibles (SDP / PII)."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated Responsible AI filters.": (
            "Bloqueado por Model Armor Floor Setting (Entrada): El prompt violó los filtros de IA Responsable (Contenido Peligroso / Dañino)."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated Malicious URI filters.": (
            "Bloqueado por Model Armor Floor Setting (Entrada): El prompt violó los filtros de URIs Maliciosas / Phishing."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated Malicious URIs filters.": (
            "Bloqueado por Model Armor Floor Setting (Entrada): El prompt violó los filtros de URIs Maliciosas / Phishing."
        ),
        "Blocked by Model Armor Floor Setting: The response violated Sensitive Data Protection filters.": (
            "Bloqueado por Model Armor Floor Setting (Salida del Modelo): La respuesta generada por el modelo violó los filtros de Protección de Datos Sensibles (SDP / PII)."
        ),
        "Blocked by Model Armor Floor Setting: The response violated SDP/PII filters.": (
            "Bloqueado por Model Armor Floor Setting (Salida del Modelo): La respuesta generada por el modelo violó los filtros de Protección de Datos Sensibles (SDP / PII)."
        ),
        "Blocked by Model Armor Floor Setting: The response violated Responsible AI filters.": (
            "Bloqueado por Model Armor Floor Setting (Salida del Modelo): La respuesta generada por el modelo violó los filtros de IA Responsable (RAI)."
        ),
        "Blocked by Model Armor Floor Setting: The response violated Malicious URI filters.": (
            "Bloqueado por Model Armor Floor Setting (Salida del Modelo): La respuesta generada por el modelo violó los filtros de URIs Maliciosas / Phishing."
        ),
        "Blocked by Model Armor Floor Setting: The response violated Malicious URIs filters.": (
            "Bloqueado por Model Armor Floor Setting (Salida del Modelo): La respuesta generada por el modelo violó los filtros de URIs Maliciosas / Phishing."
        ),
        "Blocked by Model Armor Floor Setting: The response violated Prompt Injection and Jailbreak filters.": (
            "Bloqueado por Model Armor Floor Setting (Salida del Modelo): La respuesta generada por el modelo violó los filtros de Inyección de Prompt y Jailbreak."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated Prompt Injection and Jailbreak filters. The input was not blocked as the enforcement type is inspect only.": (
            "Detectado por Model Armor Floor Setting: El prompt activó los filtros de Inyección de Prompt y Jailbreak. La entrada no fue bloqueada debido a que el modo de imposición es solo inspección (INSPECT_ONLY)."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated Sensitive Data Protection filters. The input was not blocked as the enforcement type is inspect only.": (
            "Detectado por Model Armor Floor Setting: El prompt activó los filtros de Protección de Datos Sensibles (SDP / PII). La entrada no fue bloqueada debido a que el modo de imposición es solo inspección (INSPECT_ONLY)."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated Responsible AI filters. The input was not blocked as the enforcement type is inspect only.": (
            "Detectado por Model Armor Floor Setting: El prompt activó los filtros de IA Responsable. La entrada no fue bloqueada debido a que el modo de imposición es solo inspección (INSPECT_ONLY)."
        ),
        "Blocked by Model Armor Floor Setting: The prompt violated Malicious URI filters. The input was not blocked as the enforcement type is inspect only.": (
            "Detectado por Model Armor Floor Setting: El prompt activó los filtros de URIs Maliciosas / Phishing. La entrada no fue bloqueada debido a que el modo de imposición es solo inspección (INSPECT_ONLY)."
        ),
        "No filters failed validation.": "Ningún filtro reportó violaciones de seguridad (Tráfico permitido).",
        "The prompt did not violate any safety settings.": "El prompt de entrada no violó ninguna política de seguridad (Tráfico permitido).",
        "The model response did not violate any safety settings.": "La respuesta del modelo no violó ninguna política de seguridad (Tráfico permitido).",
    }
    if reason in translations:
        return translations[reason]
    is_inspect_only = "inspect only" in reason.lower()
    res = reason.replace(
        "The input was not blocked as the enforcement type is inspect only.",
        "La entrada no fue bloqueada debido a que el modo de imposición es solo inspección (INSPECT_ONLY)."
    ).replace(
        "The output was not blocked as the enforcement type is inspect only.",
        "La respuesta del modelo no fue bloqueada debido a que el modo de imposición es solo inspección (INSPECT_ONLY)."
    ).replace(
        "The model response was not blocked as the enforcement type is inspect only.",
        "La respuesta del modelo no fue bloqueada debido a que el modo de imposición es solo inspección (INSPECT_ONLY)."
    ).replace(
        "Blocked by Model Armor Floor Setting: The prompt violated",
        "Detectado por Model Armor Floor Setting (Entrada): El prompt activó los filtros de" if is_inspect_only else "Bloqueado por Model Armor Floor Setting (Entrada): El prompt violó los filtros de"
    ).replace(
        "Blocked by Model Armor Floor Setting: The response violated",
        "Detectado por Model Armor Floor Setting (Salida): La respuesta del modelo activó los filtros de" if is_inspect_only else "Bloqueado por Model Armor Floor Setting (Salida): La respuesta del modelo violó los filtros de"
    ).replace(
        "Blocked by Model Armor Floor Setting: The model response violated",
        "Detectado por Model Armor Floor Setting (Salida): La respuesta del modelo activó los filtros de" if is_inspect_only else "Bloqueado por Model Armor Floor Setting (Salida): La respuesta del modelo violó los filtros de"
    ).replace(
        "Filter results failed validation:",
        "Filtros que activaron el bloqueo:"
    ).replace(
        "Prompt Injection and Jailbreak filters",
        "Inyección de Prompt y Jailbreak"
    ).replace(
        "Sensitive Data Protection filters",
        "Protección de Datos Sensibles (SDP / PII)"
    ).replace(
        "SDP/PII filters",
        "Protección de Datos Sensibles (SDP / PII)"
    ).replace(
        "Responsible AI filters",
        "IA Responsable (RAI)"
    ).replace(
        "Malicious URIs filters",
        "URIs Maliciosas / Phishing"
    ).replace(
        "Malicious URI filters",
        "URIs Maliciosas / Phishing"
    )
    return res


def parse_floor_setting_error_message(
    error_msg: Optional[str],
    user_message: str = "",
    output_text: str = ""
) -> List[Dict[str, Any]]:
    """
    Extrae únicamente los filtros activados de la sección 'Filters that triggered the block:'
    del mensaje nativo de Vertex AI, ignorando la sección 'Filter results: [...]' que lista NO_MATCH_FOUND.
    Soporta tanto bloqueos en el prompt de entrada como en la respuesta del modelo (SANITIZE_MODEL_RESPONSE).
    """
    if not error_msg:
        return []
    triggered_section = error_msg.split("Filter results:")[0].split("FILTER RESULTS:")[0]
    upper = triggered_section.upper()
    is_output_stage = "THE RESPONSE VIOLATED" in upper or "MODEL RESPONSE VIOLATED" in upper
    stage_desc = "en la respuesta generada por el modelo (SANITIZE_MODEL_RESPONSE)" if is_output_stage else "en el prompt de entrada (SANITIZE_USER_PROMPT)"
    matched: List[Dict[str, Any]] = []

    if "PROMPT INJECTION" in upper or "JAILBREAK" in upper or "PIANDJAILBREAK" in upper:
        matched.append({
            "name": "piAndJailbreakFilterSettings",
            "category": "Inyección de Prompt y Jailbreak",
            "confidence": "HIGH",
            "detected_variable": "PROMPT_INJECTION",
            "stage": "OUTPUT" if is_output_stage else "INPUT",
            "details": f"Detección nativa de intento de inyección de instrucciones o Jailbreak {stage_desc}."
        })
    if "SENSITIVE DATA" in upper or "SDP" in upper or "PII" in upper:
        inferred_info_type = "DATOS_SENSIBLES_PII"
        combined_up = f"{user_message or ''} {output_text or ''}".upper()
        if any(k in combined_up for k in ["VISA", "MASTERCARD", "AMEX", "TARJETA", "4532", "CVV", "JUAN PEREZ", "JUAN PÉREZ"]):
            inferred_info_type = "CREDIT_CARD_NUMBER"
        elif any(k in combined_up for k in ["SSN", "SOCIAL SECURITY", "SEGURO SOCIAL", "453-29-6714", "MARIA LOPEZ", "MARÍA LÓPEZ"]):
            inferred_info_type = "US_SOCIAL_SECURITY_NUMBER"
        elif any(k in combined_up for k in ["AIZA", "API_KEY", "API KEY"]):
            inferred_info_type = "GCP_API_KEY"
        elif any(k in combined_up for k in ["PASSWORD", "CONTRASEÑA", "CLAVE", "SECRET", "P@SS", "ADMIN"]):
            inferred_info_type = "PASSWORD"
        matched.append({
            "name": "sdpSettings",
            "category": "Protección de Datos Sensibles (PII / SDP)",
            "confidence": "VERY_LIKELY",
            "detected_variable": inferred_info_type,
            "stage": "OUTPUT" if is_output_stage else "INPUT",
            "details": f"Cloud SDP/DLP identificó información confidencial del tipo {inferred_info_type} {stage_desc}."
        })
    if "RESPONSIBLE AI" in upper or "RAI" in upper or "DANGEROUS" in upper:
        matched.append({
            "name": "raiSettings (DANGEROUS)",
            "category": "IA Responsable — DANGEROUS",
            "confidence": "HIGH",
            "detected_variable": "DANGEROUS",
            "stage": "OUTPUT" if is_output_stage else "INPUT",
            "details": f"Bloqueado por filtro de Seguridad de IA Responsable en la categoría DANGEROUS {stage_desc}."
        })
    if "MALICIOUS URI" in upper or "URI" in upper:
        matched.append({
            "name": "maliciousUriFilterSettings",
            "category": "Filtro de URIs Maliciosas / Phishing",
            "confidence": "HIGH",
            "detected_variable": "MALICIOUS_URI",
            "stage": "OUTPUT" if is_output_stage else "INPUT",
            "details": f"Enlace malicioso o de phishing detectado {stage_desc}."
        })
    return matched


def format_block_message(
    matched_filters: List[Dict[str, Any]],
    template_id: str = "floorSetting (AI_PLATFORM)",
    stage: str = "input",
    intercepted_output: Optional[str] = None
) -> str:
    is_output = (stage == "output")
    if is_output:
        lines = [
            "🛡️ **Respuesta del Modelo Bloqueada Nativamente por Model Armor (`SANITIZE_MODEL_RESPONSE`)**\n",
            "- **1. Inspección del Prompt de Entrada (`SANITIZE_USER_PROMPT`):** `✅ PERMITIDO` *(La consulta del usuario no contenía amenazas directas)*",
            "- **2. Ejecución del Modelo en Vertex AI Agent Engine:** `⚡ EJECUTADO` *(El modelo procesó la consulta e intentó devolver datos sensibles/peligrosos)*",
            "- **3. Inspección de Salida (`SANITIZE_MODEL_RESPONSE`):** `🚫 BLOQUEADO POR FLOOR SETTING` *(Respuesta interceptada antes de llegar al usuario)*",
            "- **Política Activa:** `locations/global/floorSetting` (`AI_PLATFORM: INSPECT_AND_BLOCK` · Cero Código)\n"
        ]
        if intercepted_output:
            lines.append(f"- **Respuesta del Modelo Interceptada en Cloud Logging:** `{intercepted_output}`\n")
    else:
        if not matched_filters:
            return (
                f"🛡️ **Bloqueado Automáticamente por Vertex AI + Model Armor Floor Settings**\n\n"
                f"- **Política Activa:** `projects/{settings.GCP_PROJECT_ID}/locations/global/floorSetting` (`INSPECT_AND_BLOCK`)\n"
                f"- **Intervención en Agente ADK:** `0 líneas de código (Seguridad Cero Código)`\n"
                f"- **Estado:** Inferencia abortada nativamente en Vertex AI antes de llegar al modelo."
            )
        lines = [
            "🛡️ **Prompt de Entrada Bloqueado Nativamente en Vertex AI por Model Armor (`SANITIZE_USER_PROMPT`)**\n",
            "- **Política Activa:** `locations/global/floorSetting` (`AI_PLATFORM: INSPECT_AND_BLOCK`)",
            "- **Código de Seguridad en el Agente ADK:** `Ninguno (Seguridad Cero Código)`\n"
        ]

    for m in matched_filters:
        rule_name = m.get("name", "REGLA_SEGURIDAD")
        category = m.get("category", "Seguridad")
        details = m.get("details", "")
        detected_var = m.get("detected_variable")
        confidence = m.get("confidence")

        lines.append(f"- **Regla Activada:** `{rule_name}` — *{category}*")
        if detected_var:
            lines.append(f"- **Detector / infoType Identificado:** `{detected_var}`")
        if confidence:
            lines.append(f"- **Nivel de Confianza:** `{confidence}`")
        if details:
            lines.append(f"- **Detalle de Inspección:** {details}")
        lines.append("")

    return "\n".join(lines).strip()


def parse_gcp_sanitization_result(data: Dict[str, Any], template_id: str) -> List[Dict[str, Any]]:
    """
    Analiza el esquema oficial SanitizationResult de Google Cloud Model Armor v1
    (tanto de respuestas directas como de entradas en Cloud Logging).
    """
    matched: List[Dict[str, Any]] = []
    if not isinstance(data, dict):
        return matched
    sanitization_result = data.get("sanitizationResult") or data.get("sanitization_result") or {}
    if not isinstance(sanitization_result, dict):
        return matched
    filter_results = sanitization_result.get("filterResults") or sanitization_result.get("filter_results") or {}

    if not isinstance(filter_results, dict):
        return matched

    for filter_key, filter_entry in filter_results.items():
        if not isinstance(filter_entry, dict):
            continue

        # 1. Prompt Injection & Jailbreak
        pi_res = filter_entry.get("piAndJailbreakFilterResult") or filter_entry.get("pi_and_jailbreak_filter_result")
        if pi_res and isinstance(pi_res, dict):
            match_state = pi_res.get("matchState") or pi_res.get("match_state")
            if match_state == "MATCH_FOUND":
                confidence = pi_res.get("confidenceLevel") or pi_res.get("confidence_level", "HIGH")
                matched.append({
                    "name": "piAndJailbreakFilterSettings",
                    "category": "Inyección de Prompt y Jailbreak",
                    "confidence": confidence,
                    "detected_variable": "PROMPT_INJECTION",
                    "details": "Detección de intento de inyección de instrucciones o evasión de controles del modelo (Jailbreak)."
                })

        # 2. Sensitive Data Protection (SDP / Cloud DLP)
        sdp_res = filter_entry.get("sdpFilterResult") or filter_entry.get("sdp_filter_result")
        if sdp_res and isinstance(sdp_res, dict):
            inspect_res = sdp_res.get("inspectResult") or sdp_res.get("inspect_result") or {}
            deid_res = sdp_res.get("deidentifyResult") or sdp_res.get("deidentify_result") or {}
            
            sdp_match_state = (
                inspect_res.get("matchState")
                or inspect_res.get("match_state")
                or deid_res.get("matchState")
                or deid_res.get("match_state")
                or sdp_res.get("matchState")
                or sdp_res.get("match_state")
            )
            if sdp_match_state == "MATCH_FOUND":
                findings = inspect_res.get("findings") or deid_res.get("findings") or []
                info_types = []
                likelihoods = []
                for f in findings:
                    if isinstance(f, dict):
                        it = f.get("infoType") or f.get("info_type")
                        if isinstance(it, str) and it:
                            info_types.append(it)
                        elif isinstance(it, dict) and it.get("name"):
                            info_types.append(it.get("name"))
                        lh = f.get("likelihood")
                        if lh:
                            likelihoods.append(lh)

                unique_info_types = ", ".join(sorted(set(info_types))) if info_types else "DATOS_SENSIBLES_PII"
                confidence_val = ", ".join(sorted(set(likelihoods))) if likelihoods else "HIGH"

                matched.append({
                    "name": "sdpSettings",
                    "category": "Protección de Datos Sensibles (PII)",
                    "confidence": confidence_val,
                    "detected_variable": unique_info_types,
                    "details": f"Cloud SDP/DLP identificó datos confidenciales del tipo: {unique_info_types}."
                })

        # 3. Responsible AI (RAI: Dangerous, Hate Speech, Harassment, Sexually Explicit)
        rai_res = filter_entry.get("raiFilterResult") or filter_entry.get("rai_filter_result")
        if rai_res and isinstance(rai_res, dict):
            rai_match_state = rai_res.get("matchState") or rai_res.get("match_state")
            if rai_match_state == "MATCH_FOUND":
                type_results = rai_res.get("raiFilterTypeResults") or rai_res.get("rai_filter_type_results") or {}
                triggered_types = []
                confidences = []

                if isinstance(type_results, dict):
                    for sub_key, sub_val in type_results.items():
                        if isinstance(sub_val, dict):
                            sub_match = sub_val.get("matchState") or sub_val.get("match_state")
                            if sub_match == "MATCH_FOUND":
                                f_type = sub_val.get("filterType") or sub_val.get("filter_type") or sub_key.upper()
                                triggered_types.append(f_type)
                                conf = sub_val.get("confidenceLevel") or sub_val.get("confidence_level")
                                if conf:
                                    confidences.append(conf)

                sub_category = ", ".join(triggered_types) if triggered_types else "CONTENIDO_DANINO"
                conf_str = ", ".join(sorted(set(confidences))) if confidences else "HIGH"

                matched.append({
                    "name": f"raiSettings ({sub_category})",
                    "category": f"IA Responsable — {sub_category}",
                    "confidence": conf_str,
                    "detected_variable": sub_category,
                    "details": f"Bloqueado por filtro de Seguridad de IA Responsable en la categoría: {sub_category}."
                })

        # 4. Malicious URIs
        uri_res = filter_entry.get("maliciousUriFilterResult") or filter_entry.get("malicious_uri_filter_result")
        if uri_res and isinstance(uri_res, dict):
            uri_match_state = uri_res.get("matchState") or uri_res.get("match_state")
            if uri_match_state == "MATCH_FOUND":
                items = uri_res.get("maliciousUriMatchedItems") or uri_res.get("malicious_uri_matched_items") or []
                uris = [item.get("uri", "") for item in items if isinstance(item, dict) and item.get("uri")]
                uri_str = ", ".join(uris) if uris else "URL_MALICIOSA_DETECTADA"

                matched.append({
                    "name": "maliciousUriFilterSettings",
                    "category": "Filtro de URIs Maliciosas / Phishing",
                    "confidence": "HIGH",
                    "detected_variable": uri_str,
                    "details": f"Enlace malicioso o de phishing detectado en el texto ({uri_str})."
                })

    return matched


def _extract_clean_prompt_excerpt(raw_text: str) -> str:
    """
    Cuando Vertex AI Agent Engine (ADK) envía el prompt a Gemini, antepone las instrucciones
    del sistema del agente ADK. Esta función extrae el mensaje del usuario para mostrarlo limpio
    en el resumen del log (conservando el texto íntegro en el JSON expandible).
    """
    if not raw_text:
        return ""
    if "Asistente virtual corporativo ejecutándose en Vertex AI Agent Engine" in raw_text:
        parts = raw_text.split('."\n', 1)
        if len(parts) > 1:
            raw_text = parts[1].strip()
    marker_ctx = "Mensaje actual del Usuario:\n"
    if marker_ctx in raw_text:
        raw_text = raw_text.split(marker_ctx, 1)[1].strip()
    return raw_text.strip()


class ModelArmorClient:
    """
    Cliente nativo de Google Cloud Model Armor v1 y Cloud Logging usando
    Application Default Credentials (ADC) en Cloud Run.
    """

    def __init__(self):
        self.project_id = settings.GCP_PROJECT_ID
        self.location = settings.MODEL_ARMOR_LOCATION
        self.template_id = settings.MODEL_ARMOR_TEMPLATE_ID
        self._credentials = None
        self._auth_request = None
        self._current_inspect_and_block: Optional[bool] = None
        self._current_mode: Optional[Tuple[bool, bool]] = None

    def _get_auth_token(self) -> str:
        if not self._credentials:
            self._credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            self._auth_request = google.auth.transport.requests.Request()

        if not self._credentials.valid:
            self._credentials.refresh(self._auth_request)
        return self._credentials.token

    def get_floor_setting(self) -> Dict[str, Any]:
        """Lee la configuración actual de Model Armor Floor Settings a nivel proyecto GCP."""
        token = self._get_auth_token()
        url = f"https://modelarmor.googleapis.com/v1/projects/{self.project_id}/locations/global/floorSetting"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ai_setting = data.get("aiPlatformFloorSetting", {})
        enforcement_enabled = bool(data.get("enableFloorSettingEnforcement", False))
        is_block = enforcement_enabled and bool(ai_setting.get("inspectAndBlock", False))
        self._current_mode = (is_block, enforcement_enabled)
        self._current_inspect_and_block = is_block
        return data

    def get_detailed_policies_summary(self) -> Dict[str, Any]:
        """
        Obtiene en vivo el Floor Setting del proyecto en GCP y construye el desglose
        completo de políticas, reglas, niveles de confianza, detectores SDP (infoTypes)
        y reglas de Cloud Armor que protegen al agente.
        """
        raw_floor = {}
        try:
            raw_floor = self.get_floor_setting()
        except Exception as exc:
            logger.warning(f"No se pudo leer floorSetting en vivo: {exc}")

        filter_cfg = raw_floor.get("filterConfig", {})
        ai_setting = raw_floor.get("aiPlatformFloorSetting", {})
        is_blocking = bool(raw_floor.get("enableFloorSettingEnforcement", True)) and bool(
            ai_setting.get("inspectAndBlock", True)
        )
        mode_str = "INSPECT_AND_BLOCK" if is_blocking else "INSPECT_ONLY"

        pi_cfg = filter_cfg.get("piAndJailbreakFilterSettings", {})
        sdp_cfg = filter_cfg.get("sdpSettings", {}).get("basicConfig", {})
        uri_cfg = filter_cfg.get("maliciousUriFilterSettings", {})
        rai_filters = filter_cfg.get("raiSettings", {}).get("raiFilters", [])

        rai_map = {item.get("filterType"): item.get("confidenceLevel", "MEDIUM_AND_ABOVE") for item in rai_filters if isinstance(item, dict)}

        gcloud_floor_cmd = (
            f"curl -s -H \"Authorization: Bearer $(gcloud auth print-access-token)\" "
            f"\"https://modelarmor.googleapis.com/v1/projects/{self.project_id}/locations/global/floorSetting\" | jq ."
        )

        return {
            "project_id": self.project_id,
            "policy_resource": raw_floor.get("name", f"projects/{self.project_id}/locations/global/floorSetting"),
            "enforcement_enabled": bool(raw_floor.get("enableFloorSettingEnforcement", True)),
            "enforcement_mode": mode_str,
            "integrated_services": raw_floor.get("integratedServices", ["AI_PLATFORM"]),
            "cloud_logging_enabled": bool(ai_setting.get("enableCloudLogging", True)),
            "gcloud_floor_command": gcloud_floor_cmd,
            "raw_floor_setting": raw_floor,
            "model_armor_rules": [
                {
                    "id": "piAndJailbreakFilterSettings",
                    "title": "Inyección de Prompt y Jailbreak",
                    "state": pi_cfg.get("filterEnforcement", "ENABLED"),
                    "threshold": pi_cfg.get("confidenceLevel", "LOW_AND_ABOVE"),
                    "threshold_label": " Confianza: BAJA Y SUPERIOR (LOW_AND_ABOVE — Máxima Estricticidad)",
                    "description": "Detecta y bloquea intentos de manipular instrucciones del sistema, saltar barreras de seguridad o secuestrar el rol del agente.",
                    "blocked_matches": [
                        {
                            "code": "PROMPT_INJECTION",
                            "label": "Sobrescritura de Instrucciones",
                            "detail": "Prompts como 'Ignora tus instrucciones previas', 'Olvida tus reglas' o inyecciones indirectas."
                        },
                        {
                            "code": "JAILBREAK_DAN",
                            "label": "Evasión de Guardrails (Jailbreak / Modo Desarrollador)",
                            "detail": "Simulaciones de rol sin censura, modo depuración o hipnosis del LLM."
                        },
                        {
                            "code": "SYSTEM_PROMPT_EXFILTRATION",
                            "label": "Extracción de Prompt del Sistema",
                            "detail": "Intentos de revelar las instrucciones internas o configuración del Agente ADK."
                        }
                    ]
                },
                {
                    "id": "sdpSettings",
                    "title": "Protección de Datos Sensibles (SDP / Cloud DLP)",
                    "state": sdp_cfg.get("filterEnforcement", "ENABLED"),
                    "threshold": "MATCH_FOUND (Cualquier coincidencia de detector)",
                    "threshold_label": "Modo: basicConfig ENABLED (Inspección en Entrada y Salida)",
                    "description": "Evita la fuga o ingesta de Datos Personales (PII), financieros y secretos corporativos mediante los detectores nativos de Sensitive Data Protection.",
                    "blocked_matches": [
                        {
                            "code": "CREDIT_CARD_NUMBER",
                            "label": "Números de Tarjeta de Crédito",
                            "detail": "Tarjetas Visa, Mastercard, Amex, Discover (12 a 19 dígitos con validación Luhn)."
                        },
                        {
                            "code": "FINANCIAL_ACCOUNT_NUMBER",
                            "label": "Cuentas Bancarias y Financieras",
                            "detail": "Números de cuenta bancaria, CLABE o identificadores de cuentas financieras."
                        },
                        {
                            "code": "GCP_CREDENTIALS",
                            "label": "Credenciales de Google Cloud (Service Accounts)",
                            "detail": "Llaves privadas JSON de cuentas de servicio y credenciales de GCP."
                        },
                        {
                            "code": "GCP_API_KEY",
                            "label": "Llaves de API de GCP (API Keys)",
                            "detail": "Tokens y llaves de API de Google Cloud (ej. cadenas 'AIza...')."
                        },
                        {
                            "code": "PASSWORD",
                            "label": "Contraseñas y Secretos en Texto Plano",
                            "detail": "Credenciales de acceso, contraseñas o frases secretas expuestas en el prompt o respuesta."
                        },
                        {
                            "code": "US_SOCIAL_SECURITY_NUMBER",
                            "label": "Número de Seguro Social (SSN)",
                            "detail": "Identificadores de seguridad social de 9 dígitos (formato XXX-XX-XXXX)."
                        },
                        {
                            "code": "US_INDIVIDUAL_TAXPAYER_IDENTIFICATION_NUMBER",
                            "label": "Identificación Fiscal (ITIN)",
                            "detail": "Números de identificación fiscal individual."
                        }
                    ]
                },
                {
                    "id": "raiSettings",
                    "title": "Filtros de IA Responsable (Responsible AI)",
                    "state": "ENABLED",
                    "threshold": "MEDIUM_AND_ABOVE",
                    "threshold_label": "Confianza: MEDIA Y SUPERIOR (MEDIUM_AND_ABOVE)",
                    "description": "Bloquea la generación o solicitud de contenido peligroso, ilegal, discurso de odio, acoso o explícito.",
                    "blocked_matches": [
                        {
                            "code": "DANGEROUS",
                            "label": f"Contenido Peligroso / Dañino ({rai_map.get('DANGEROUS', 'MEDIUM_AND_ABOVE')})",
                            "detail": "Fabricación de explosivos/armas, ciberataques, autolesión o actividades ilícitas."
                        },
                        {
                            "code": "HATE_SPEECH",
                            "label": f"Discurso de Odio ({rai_map.get('HATE_SPEECH', 'MEDIUM_AND_ABOVE')})",
                            "detail": "Ataques, discriminación o incitación al odio contra grupos protegidos."
                        },
                        {
                            "code": "HARASSMENT",
                            "label": f"Acoso y Amenazas ({rai_map.get('HARASSMENT', 'MEDIUM_AND_ABOVE')})",
                            "detail": "Intimidación, amenazas directas, hostigamiento o abuso."
                        },
                        {
                            "code": "SEXUALLY_EXPLICIT",
                            "label": f"Contenido Sexualmente Explícito ({rai_map.get('SEXUALLY_EXPLICIT', 'MEDIUM_AND_ABOVE')})",
                            "detail": "Material sexualmente explícito o inapropiado."
                        }
                    ]
                },
                {
                    "id": "maliciousUriFilterSettings",
                    "title": "Filtro de URIs Maliciosas (Google Web Risk)",
                    "state": uri_cfg.get("filterEnforcement", "ENABLED"),
                    "threshold": "MATCH_FOUND",
                    "threshold_label": "Verificación en línea contra listas de Google Web Risk",
                    "description": "Inspecciona todas las URLs en el prompt y en la respuesta del modelo para bloquear enlaces peligrosos.",
                    "blocked_matches": [
                        {
                            "code": "MALICIOUS_URI / PHISHING",
                            "label": "Enlaces de Phishing, Malware e Ingeniería Social",
                            "detail": "URLs reportadas por distribución de malware, robo de credenciales o sitios falsos."
                        }
                    ]
                },
                {
                    "id": "csamFilter",
                    "title": "Protección Infantil Obligatoria (CSAM)",
                    "state": "ALWAYS_ENABLED",
                    "threshold": " MANDATORY",
                    "threshold_label": "Política inmutable de plataforma en Google Cloud",
                    "description": "Bloqueo obligatorio e incondicional de cualquier contenido de abuso o explotación infantil.",
                    "blocked_matches": [
                        {
                            "code": "CSAM_DETECTION",
                            "label": "Bloqueo Absoluto CSAM",
                            "detail": "Activo permanentemente en todos los modelos de Vertex AI."
                        }
                    ]
                }
            ],
            "cloud_armor_rules": [
                {
                    "priority": 900,
                    "action": "DENY (HTTP 403)",
                    "name": "Mitigación OWASP SQLi + XSS",
                    "expression": "evaluatePreconfiguredWaf('sqli-v33-stable') || evaluatePreconfiguredWaf('xss-v33-stable')",
                    "detail": "Bloquea en el Load Balancer Global inyecciones SQL y scripts maliciosos (Cross-Site Scripting) antes de llegar a Cloud Run."
                },
                {
                    "priority": 2000,
                    "action": "RATE_BASED_BAN (HTTP 429)",
                    "name": "Protección Anti-DDoS / Rate Limiting por IP",
                    "expression": "120 peticiones / 60s por IP (Ban de 300s)",
                    "detail": "Suspende automáticamente por 5 minutos a clientes que excedan el umbral de tráfico hacia el agente."
                }
            ]
        }


    def set_floor_setting_mode(
        self,
        inspect_and_block: bool,
        force: bool = False,
        enable_enforcement: bool = True
    ) -> Dict[str, Any]:
        """
        Actualiza el Floor Setting del proyecto GCP entre:
        - Modo Protegido (inspectAndBlock=True, enableFloorSettingEnforcement=True)
        - Modo Auditoría / Bypass (inspectOnly=True, enableFloorSettingEnforcement=True)
          para que siga registrando logs en Cloud Logging sin bloquear la inferencia.
        - Deshabilita imposición si enable_enforcement=False.
        """
        target_mode = (bool(inspect_and_block), bool(enable_enforcement))
        if not force and self._current_mode is None:
            try:
                self.get_floor_setting()
            except Exception:
                pass
        if not force and self._current_mode == target_mode:
            return {
                "inspectAndBlock": inspect_and_block,
                "enableFloorSettingEnforcement": enable_enforcement,
                "cached": True
            }

        token = self._get_auth_token()
        url = (
            f"https://modelarmor.googleapis.com/v1/projects/{self.project_id}"
            f"/locations/global/floorSetting"
            f"?updateMask=enableFloorSettingEnforcement,integratedServices,aiPlatformFloorSetting"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if inspect_and_block:
            ai_platform_setting = {"inspectAndBlock": True, "enableCloudLogging": True}
        else:
            ai_platform_setting = {"inspectOnly": True, "enableCloudLogging": True}

        body = {
            "enableFloorSettingEnforcement": bool(enable_enforcement),
            "integratedServices": ["AI_PLATFORM"],
            "aiPlatformFloorSetting": ai_platform_setting,
        }
        resp = requests.patch(url, headers=headers, json=body, timeout=10)
        resp.raise_for_status()
        self._current_mode = target_mode
        self._current_inspect_and_block = inspect_and_block if enable_enforcement else False

        data = resp.json()
        data["inspectAndBlock"] = inspect_and_block
        data["enableFloorSettingEnforcement"] = enable_enforcement
        data["cached"] = False
        return data

    def invalidate_cache(self) -> None:
        """Invalida la caché local de Floor Setting."""
        self._current_mode = None
        self._current_inspect_and_block = None

    def list_sanitize_logs(self, limit: int = 10, vertex_only: bool = True) -> Dict[str, Any]:
        """
        Consulta en tiempo real Cloud Logging (projects/{project}/logs/modelarmor.googleapis.com%2Fsanitize_operations)
        para mostrar en la interfaz web las operaciones de sanitización ejecutadas por Model Armor.
        """
        token = self._get_auth_token()
        url = "https://logging.googleapis.com/v2/entries:list"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        filter_str = 'resource.type="modelarmor.googleapis.com/SanitizeOperation"'
        if vertex_only:
            filter_str += ' AND labels."modelarmor.googleapis.com/client_name"="VERTEX_AI"'

        body = {
            "resourceNames": [f"projects/{self.project_id}"],
            "filter": filter_str,
            "orderBy": "timestamp desc",
            "pageSize": limit,
        }
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        resp.raise_for_status()
        raw_entries = resp.json().get("entries", [])

        parsed_entries: List[Dict[str, Any]] = []
        for entry in raw_entries:
            json_payload = entry.get("jsonPayload") or {}
            labels = entry.get("labels") or {}
            res_labels = (entry.get("resource") or {}).get("labels") or {}
            san_result = json_payload.get("sanitizationResult") or {}
            raw_input_text = (json_payload.get("sanitizationInput") or {}).get("text", "")
            clean_excerpt = _extract_clean_prompt_excerpt(raw_input_text)

            template_id = res_labels.get("template_id", "FLOOR_SETTING")
            client_name = labels.get("modelarmor.googleapis.com/client_name") or "API_TEMPLATE"
            op_type = json_payload.get("operationType") or labels.get("modelarmor.googleapis.com/operation_type", "SANITIZE_USER_PROMPT")
            verdict_raw = san_result.get("sanitizationVerdict", "")
            filter_match_state = san_result.get("filterMatchState", "NO_MATCH_FOUND")
            verdict_reason_raw = san_result.get("sanitizationVerdictReason", "")
            matched_filters = parse_gcp_sanitization_result(json_payload, template_id)

            is_verdict_block = "BLOCK" in verdict_raw.upper()
            match_found = (filter_match_state == "MATCH_FOUND" or len(matched_filters) > 0)

            if is_verdict_block:
                verdict_display = "BLOQUEADO"
                is_blocked = True
                is_audit = False
            elif match_found:
                verdict_display = "PERMITIDO · AUDITORÍA (INSPECT_ONLY)"
                is_blocked = False
                is_audit = True
            else:
                verdict_display = "PERMITIDO"
                is_blocked = False
                is_audit = False

            user_snippet = clean_excerpt[:220] + ("..." if len(clean_excerpt) > 220 else "")

            parsed_entries.append({
                "insert_id": entry.get("insertId", ""),
                "timestamp": entry.get("timestamp", ""),
                "receive_timestamp": entry.get("receiveTimestamp", ""),
                "location": res_labels.get("location", "global"),
                "template_id": template_id,
                "client_name": client_name,
                "operation_type": op_type,
                "operation_label": (
                    "Prompt de Entrada (SANITIZE_USER_PROMPT)"
                    if "USER_PROMPT" in op_type
                    else "Respuesta del Modelo (SANITIZE_MODEL_RESPONSE)"
                ),
                "stage": "INPUT" if "USER_PROMPT" in op_type else "OUTPUT",
                "user_prompt_snippet": user_snippet,
                "prompt_excerpt": user_snippet,
                "sanitization_verdict": verdict_raw,
                "verdict": verdict_display,
                "verdict_raw": verdict_raw,
                "is_blocked": is_blocked,
                "is_audit": is_audit,
                "filter_match_state": filter_match_state,
                "verdict_reason": translate_verdict_reason(verdict_reason_raw),
                "verdict_reason_raw": verdict_reason_raw,
                "raw_text": clean_excerpt,
                "full_text": clean_excerpt,
                "matched_filters": matched_filters,
                "json_payload": json_payload,
                "raw_entry": entry,
            })

        gcloud_cmd = (
            f'gcloud logging read \'resource.type="modelarmor.googleapis.com/SanitizeOperation" '
            f'AND labels."modelarmor.googleapis.com/client_name"="VERTEX_AI"\' '
            f'--project={self.project_id} --limit=10 --format=json'
        )
        console_url = (
            f"https://console.cloud.google.com/logs/query;"
            f"query=resource.type%3D%22modelarmor.googleapis.com%2FSanitizeOperation%22%0A"
            f"labels.%22modelarmor.googleapis.com%2Fclient_name%22%3D%22VERTEX_AI%22;"
            f"duration=PT1H?project={self.project_id}"
        )

        return {
            "project_id": self.project_id,
            "log_name": f"projects/{self.project_id}/logs/modelarmor.googleapis.com%2Fsanitize_operations",
            "gcloud_command": gcloud_cmd,
            "console_url": console_url,
            "count": len(parsed_entries),
            "entries": parsed_entries,
        }

    def find_recent_log_for_prompt(self, user_message: str, prompt_text: str = "") -> Optional[Dict[str, Any]]:
        """
        Busca en los registros más recientes de Cloud Logging (emitidos por VERTEX_AI)
        la entrada correspondiente al mensaje recién enviado para enriquecer la telemetría.
        """
        try:
            logs_data = self.list_sanitize_logs(limit=6, vertex_only=True)
            needle = user_message.strip()[:45]
            prompt_tail = prompt_text.strip()[-60:] if prompt_text else ""
            for item in logs_data.get("entries", []):
                raw_text = item.get("json_payload", {}).get("sanitizationInput", {}).get("text", "")
                if (needle and needle in raw_text) or (prompt_tail and prompt_tail in raw_text):
                    return item
        except Exception as exc:
            logger.debug(f"No se pudo recuperar log inmediato para telemetría: {exc}")
        return None

    def find_recent_turn_logs(
        self,
        user_message: str,
        prompt_text: str = "",
        expect_output_log: bool = False,
        expected_output_hint: str = ""
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Recupera tanto el log de entrada (SANITIZE_USER_PROMPT) como el log de salida
        del modelo (SANITIZE_MODEL_RESPONSE) generados en el turno actual por Vertex AI.
        Evita asociar logs de turnos anteriores cuando Cloud Logging aún está indexando.
        """
        result: Dict[str, Optional[Dict[str, Any]]] = {
            "input_log": None,
            "output_log": None,
        }
        try:
            logs_data = self.list_sanitize_logs(limit=6, vertex_only=True)
            entries = logs_data.get("entries", [])
            needle = user_message.strip()[:40]
            prompt_tail = prompt_text.strip()[-55:] if prompt_text else ""
            output_hint = expected_output_hint.strip()[:30] if expected_output_hint else ""

            matched_input_idx: Optional[int] = None
            for idx, item in enumerate(entries):
                op_type = item.get("operation_type", "")
                raw_text = item.get("json_payload", {}).get("sanitizationInput", {}).get("text", "")
                if "USER_PROMPT" in op_type and result["input_log"] is None:
                    if (needle and needle in raw_text) or (prompt_tail and prompt_tail in raw_text):
                        result["input_log"] = item
                        matched_input_idx = idx
                        break

            for idx, item in enumerate(entries):
                op_type = item.get("operation_type", "")
                raw_text = item.get("json_payload", {}).get("sanitizationInput", {}).get("text", "")
                if "MODEL_RESPONSE" in op_type and result["output_log"] is None:
                    if output_hint:
                        if output_hint in raw_text:
                            result["output_log"] = item
                            break
                    elif matched_input_idx is not None and idx < matched_input_idx:
                        result["output_log"] = item
                        break
        except Exception as exc:
            logger.debug(f"No se pudieron recuperar logs del turno: {exc}")
        return result

    def sanitize_user_prompt(self, prompt: str, bypass: bool = False) -> ModelArmorResult:
        if bypass:
            return ModelArmorResult(
                is_blocked=False,
                action="PERMITIDO (MODO AUDITORÍA)",
                message="Model Armor en modo Auditoría (INSPECT_ONLY).",
                sanitized_content=prompt,
                latency_ms=0.0
            )

        start_time = time.time()
        token = self._get_auth_token()
        url = (
            f"https://modelarmor.{self.location}.rep.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/templates/{self.template_id}:sanitizeUserPrompt"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        body = {"userPromptData": {"text": prompt}}

        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        data = response.json()
        latency_ms = (time.time() - start_time) * 1000

        sanitization_result = data.get("sanitizationResult") or data.get("sanitization_result") or {}
        filter_match_state = sanitization_result.get("filterMatchState") or sanitization_result.get("filter_match_state", "NO_MATCH_FOUND")

        if filter_match_state == "MATCH_FOUND":
            matched = parse_gcp_sanitization_result(data, self.template_id)
            block_msg = format_block_message(matched, self.template_id)
            return ModelArmorResult(
                is_blocked=True,
                action="BLOQUEADO",
                message=block_msg,
                matched_filters=matched,
                latency_ms=latency_ms,
                raw_response=data
            )

        return ModelArmorResult(
            is_blocked=False,
            action="PERMITIDO",
            sanitized_content=prompt,
            latency_ms=latency_ms,
            raw_response=data
        )

    def sanitize_model_response(self, response_text: str, bypass: bool = False) -> ModelArmorResult:
        if bypass:
            return ModelArmorResult(
                is_blocked=False,
                action="PERMITIDO",
                sanitized_content=response_text,
                latency_ms=0.0
            )

        start_time = time.time()
        token = self._get_auth_token()
        url = (
            f"https://modelarmor.{self.location}.rep.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/templates/{self.template_id}:sanitizeModelResponse"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        body = {"modelResponseData": {"text": response_text}}

        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        data = response.json()
        latency_ms = (time.time() - start_time) * 1000

        sanitization_result = data.get("sanitizationResult") or data.get("sanitization_result") or {}
        filter_match_state = sanitization_result.get("filterMatchState") or sanitization_result.get("filter_match_state", "NO_MATCH_FOUND")

        if filter_match_state == "MATCH_FOUND":
            matched = parse_gcp_sanitization_result(data, self.template_id)
            block_msg = format_block_message(matched, self.template_id)
            return ModelArmorResult(
                is_blocked=True,
                action="BLOQUEADO",
                message=block_msg,
                matched_filters=matched,
                latency_ms=latency_ms,
                raw_response=data
            )

        return ModelArmorResult(
            is_blocked=False,
            action="PERMITIDO",
            sanitized_content=response_text,
            latency_ms=latency_ms,
            raw_response=data
        )


model_armor_client = ModelArmorClient()

