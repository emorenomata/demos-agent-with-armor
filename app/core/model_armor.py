import logging
import time
from typing import Dict, Any, Optional, List
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


def format_block_message(matched_filters: List[Dict[str, Any]], template_id: str) -> str:
    if not matched_filters:
        return (
            f"🛡️ **Acceso Interceptado por Google Cloud Model Armor**\n\n"
            f"- **Template:** `{template_id}`\n"
            f"- **Estado:** Bloqueado por política de seguridad."
        )

    lines = [
        f"🛡️ **Acceso Interceptado por Google Cloud Model Armor (`{template_id}`)**\n"
    ]

    for m in matched_filters:
        rule_name = m.get("name", "SECURITY_RULE")
        category = m.get("category", "Seguridad")
        details = m.get("details", "")
        detected_var = m.get("detected_variable")
        confidence = m.get("confidence")

        lines.append(f"- **Regla Activada:** `{rule_name}` — *{category}*")
        if detected_var:
            lines.append(f"- **Variable / Tipo Identificado (PII/URI):** `{detected_var}`")
        if confidence:
            lines.append(f"- **Nivel de Confianza:** `{confidence}`")
        if details:
            lines.append(f"- **Detalle de Inspección:** {details}")
        lines.append("")

    return "\n".join(lines).strip()


def parse_gcp_sanitization_result(data: Dict[str, Any], template_id: str) -> List[Dict[str, Any]]:
    """
    Parses the official Google Cloud Model Armor v1 SanitizationResult schema:
    sanitizationResult.filterResults = {
      "pi_and_jailbreak": { "piAndJailbreakFilterResult": { "matchState": "MATCH_FOUND", "confidenceLevel": "..." } },
      "sdp": { "sdpFilterResult": { "inspectResult": { "matchState": "MATCH_FOUND", "findings": [{"infoType": "CREDIT_CARD_NUMBER", ...}] } } },
      "rai": { "raiFilterResult": { "matchState": "MATCH_FOUND", "raiFilterTypeResults": { "dangerous": { "matchState": "MATCH_FOUND", "filterType": "DANGEROUS" } } } },
      "malicious_uris": { "maliciousUriFilterResult": { "matchState": "MATCH_FOUND", "maliciousUriMatchedItems": [...] } }
    }
    """
    matched: List[Dict[str, Any]] = []
    sanitization_result = data.get("sanitizationResult") or data.get("sanitization_result") or {}
    filter_results = sanitization_result.get("filterResults") or sanitization_result.get("filter_results") or {}

    if not isinstance(filter_results, dict):
        return matched

    # Iterate through all filter entries in filterResults map
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
                    "category": "Prompt Injection & Jailbreak",
                    "confidence": confidence,
                    "detected_variable": None,
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

                unique_info_types = ", ".join(sorted(set(info_types))) if info_types else "SENSITIVE_DATA_PII"
                confidence_val = ", ".join(sorted(set(likelihoods))) if likelihoods else "HIGH"

                matched.append({
                    "name": "sdpSettings",
                    "category": "Sensitive Data Protection (PII)",
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

                sub_category = ", ".join(triggered_types) if triggered_types else "HARMFUL_CONTENT"
                conf_str = ", ".join(sorted(set(confidences))) if confidences else "HIGH"

                matched.append({
                    "name": f"raiSettings ({sub_category})",
                    "category": f"Responsible AI — {sub_category}",
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
                uri_str = ", ".join(uris) if uris else "MALICIOUS_URL_DETECTED"

                matched.append({
                    "name": "maliciousUriFilterSettings",
                    "category": "Malicious URI / Phishing Filter",
                    "confidence": "HIGH",
                    "detected_variable": uri_str,
                    "details": f"Enlace malicioso o de phishing detectado en el texto ({uri_str})."
                })

    return matched


class ModelArmorClient:
    """
    Native Google Cloud Model Armor v1 Client using Application Default Credentials (ADC) in Cloud Run.
    """

    def __init__(self):
        self.project_id = settings.GCP_PROJECT_ID
        self.location = settings.MODEL_ARMOR_LOCATION
        self.template_id = settings.MODEL_ARMOR_TEMPLATE_ID
        self._credentials = None
        self._auth_request = None

    def _get_auth_token(self) -> str:
        if not self._credentials:
            self._credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            self._auth_request = google.auth.transport.requests.Request()

        if not self._credentials.valid:
            self._credentials.refresh(self._auth_request)
        return self._credentials.token

    def sanitize_user_prompt(self, prompt: str, bypass: bool = False) -> ModelArmorResult:
        if bypass:
            return ModelArmorResult(
                is_blocked=False,
                action="ALLOWED",
                message="Model Armor en modo Bypass.",
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
                action="BLOCKED",
                message=block_msg,
                matched_filters=matched,
                latency_ms=latency_ms,
                raw_response=data
            )

        return ModelArmorResult(
            is_blocked=False,
            action="ALLOWED",
            sanitized_content=prompt,
            latency_ms=latency_ms,
            raw_response=data
        )

    def sanitize_model_response(self, response_text: str, bypass: bool = False) -> ModelArmorResult:
        if bypass:
            return ModelArmorResult(
                is_blocked=False,
                action="ALLOWED",
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
                action="BLOCKED",
                message=block_msg,
                matched_filters=matched,
                latency_ms=latency_ms,
                raw_response=data
            )

        return ModelArmorResult(
            is_blocked=False,
            action="ALLOWED",
            sanitized_content=response_text,
            latency_ms=latency_ms,
            raw_response=data
        )


model_armor_client = ModelArmorClient()
