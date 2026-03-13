# 🩺 Guía de Auditoría Médica Profesional - GM_MODULAR_ECOSYSTEM

Este documento describe las herramientas disponibles para el equipo médico profesional para supervisar y mejorar la seguridad clínica del sistema.

## 1. Monitoreo de Consultas de Riesgo
El sistema cuenta con un endpoint de administración que filtra automáticamente las consultas donde el Auditor de IA detectó un posible riesgo (interacciones, dosis excesivas o consultas de autolesión).

**Endpoint:** `GET /admin/flagged-queries`
**Descripción:** Devuelve una lista de las llamadas que activaron las alarmas del auditor (`auditor_alert` o `auditor_intercept`).

### Ejemplo de uso:
```bash
curl -H "Authorization: Bearer hcg_maestro_123" http://localhost:8000/admin/flagged-queries
```

## 2. Investigación de Trazas (Traceability)
Para cada consulta marcada, el auditor profesional puede ver el "paso a paso" de lo que pensó el sistema y el auditor.

**Endpoint:** `GET /admin/trace/{session_id}`
**Contenido de la traza:**
- **INPUT_RECEIVED**: Lo que el usuario preguntó.
- **AUDITOR_PRE_PROCESS**: La primera barrera. Si aquí se bloquea, el usuario recibe una respuesta de seguridad inmediata.
- **LLM_RAW_OUTPUT**: Lo que la IA generó antes de ser auditado.
- **AUDITOR_SAFETY_VALIDATION**: El análisis del Auditor sobre la respuesta de la IA, comparándola con el contexto médico.
- **FINAL_RESPONSE_SERVED**: Lo que finalmente vio el usuario.

## 3. Circuito de Retroalimentación (Feedback & RLHF)
Como profesional, puedes "corregir" al sistema. Si ves una respuesta que no es óptima o es peligrosa y no fue detectada, puedes enviar feedback.

**Endpoint:** `POST /audit/feedback`
**Payload:**
```json
{
  "session_id": "ID_DE_LA_SESION",
  "rating": 1, // 1 a 5
  "is_dangerous": true,
  "comment": "Sugirió una dosis de AINEs que no es segura para un paciente con falla renal.",
  "suggested_response": "Debe consultar a su nefrólogo antes de ingerir Ibuprofeno.",
  "expert_name": "Dr. Smith"
}
```

## 4. Configuración del Auditor (clinical_prompts.yml)
Las reglas de negocio médico residen en [SERVICES/medical_auditor/src/clinical_prompts.yml](file:///home/drexgen/Documents/CHAT-GOMedisys/SERVICES/medical_auditor/src/clinical_prompts.yml). 
Se han configurado 5 reglas maestras:
1. **Contraindicaciones**: Choque con diagnósticos previos.
2. **Conflictos de Medicación**: Interacciones entre fármacos.
3. **Errores de Dosificación**: Dosis fuera de rango para la condición del paciente.
4. **Calidad Clínica**: Respuestas incompletas o erróneas.
5. **Seguridad General**: Riesgos de toxicidad.

---
*Este sistema está diseñado para asistir, no para reemplazar, el juicio de un profesional de la salud.*
