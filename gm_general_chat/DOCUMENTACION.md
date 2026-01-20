# 🩺 GM_GENERAL_CHAT - Módulo de Chat Médico General

Este módulo es el "Especialista Médico" de la plataforma GoMedisys. Procesa lenguaje natural con contexto clínico y herramientas de búsqueda médica.

## 💼 Resumen Ejecutivo
Este servicio actúa como el motor de inteligencia clínica. Su función principal es:
*   **Consulta Médica**: Responder dudas de pacientes y profesionales usando modelos LLM avanzados.
*   **Investigación**: Acceder a fuentes de datos externas (FDA, PubMed) para validar información médica.
*   **Memoria de Contexto**: Recordar la conversación previa del paciente para dar respuestas coherentes.
*   **Multilingüe**: Detección automática de idioma del paciente.

---

## 🛠️ Especificación Técnica
*   **Framework**: FastAPI (Python 3.11).
*   **Cerebro (RAG/LLM)**: LlamaIndex para la gestión de motores de chat y prompts.
*   **Memoria**: Redis (cache) para almacenar el historial de sesiones de forma volátil y ultra-rápida.
*   **Seguridad**: Delegada al Gateway (ADM). Este módulo solo acepta peticiones en la red interna de Docker.
*   **Herramientas (MCP)**:
    *   `fda`: Consulta sobre aprobación de medicamentos.
    *   `pubmed`: Búsqueda en literatura científica.
    *   `icd10`: Códigos de diagnóstico internacional.

---

## 🔍 Guía de Auditoría
Este módulo se puede auditar de forma independiente sin pasar por el Gateway para verificar su motor de IA.

**Cómo probar este módulo:**
1.  Asegúrate de que Redis y el Chat estén corriendo: `docker-compose up -d`
2.  Ejecuta el auditor local: `bash auditor_modulo.sh`

**Resultados esperados:**
*   **Conectividad Redis**: El auditor verificará que la memoria esté disponible.
*   **Inferencia**: El bot deberá responder una pregunta médica simple.
*   **Uso (Metadata)**: La respuesta debe incluir obligatoriamente el campo `usage` con el conteo de tokens.
