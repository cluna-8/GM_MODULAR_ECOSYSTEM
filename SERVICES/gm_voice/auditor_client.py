import httpx
import logging
import os

logger = logging.getLogger(__name__)

AUDITOR_URL = os.getenv("AUDITOR_URL", "http://medical-auditor:8001")


async def validate_suggestions(documento: dict) -> list:
    """
    Send clinical suggestions to Medical Auditor for safety validation.
    Returns list of alerts. On auditor unavailability, returns empty list (fail-open).
    """
    suggestions_text = _build_suggestions_text(documento)
    if not suggestions_text:
        return []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{AUDITOR_URL}/audit/validate-safety",
                json={
                    "text": suggestions_text,
                    "context": {
                        "medicacion_actual": documento.get("medicacion_actual", []),
                        "diagnostico": documento.get("diagnostico_sugerido", [])
                    }
                }
            )
            data = response.json()

            if data.get("status") == "ALERT":
                return [data.get("verdict", "Alerta clínica detectada")]
            return []

    except Exception as e:
        logger.warning(f"Medical Auditor unavailable, skipping validation: {e}")
        return []


def _build_suggestions_text(documento: dict) -> str:
    parts = []
    if documento.get("diagnostico_sugerido"):
        parts.append("Diagnósticos: " + ", ".join(documento["diagnostico_sugerido"]))
    if documento.get("medicamentos_sugeridos"):
        parts.append("Medicamentos sugeridos: " + ", ".join(documento["medicamentos_sugeridos"]))
    if documento.get("medicacion_actual"):
        parts.append("Medicación actual: " + ", ".join(documento["medicacion_actual"]))
    return ". ".join(parts)
