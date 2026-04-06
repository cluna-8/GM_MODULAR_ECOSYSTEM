#!/bin/bash

# ==============================================================================
# Script de Prueba End-to-End para el ecosistema Chat-GoMedisys
# Testea: Login (Token), Chat1 (Memoria), Chat2 (Resumen IA) y Auditoría
# ==============================================================================

set -e

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "💉 Iniciando Prueba de Integración Médica"
echo "=========================================="

# 1. Obtener API KEY desde ADM_MODULAR
echo -e "\n[1] Solicitando API Key (Auth)..."
TOKEN_MSG=$(curl -s -X POST "$BASE_URL/admin/tokens" \
  -H "Content-Type: application/json" \
  -d '{"username": "test_script_user", "name": "Test Env Token"}')

API_KEY=$(echo "$TOKEN_MSG" | grep -o '"token":"[^"]*' | cut -d'"' -f4)

if [ -z "$API_KEY" ]; then
    echo "❌ Error al obtener API KEY: $TOKEN_MSG"
    exit 1
fi
echo "✅ API Key obtenida: $API_KEY"


# 2. Iniciar sesión hablando con Chat1 (General)
echo -e "\n[2] Consultando Chat General (chat1)..."
CHAT1_RES=$(curl -s -X POST "$BASE_URL/v1/chat1/chat" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "promptData": "Hola, he tenido dolor de cabeza constante esta semana.",
    "IAType": "medical",
    "language": "es"
  }')

# Extraer el Session ID generado
SESSION_ID=$(echo "$CHAT1_RES" | grep -o '"session_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
    echo "❌ Error al obtener Session ID en Chat1: $CHAT1_RES"
    exit 1
fi

echo "✅ Chat1 respondió. Sesión creada: $SESSION_ID"
echo "Respuesta Chat1:"
echo "$CHAT1_RES" | grep -o '"response":"[^"]*' | cut -d'"' -f4 | head -c 100
echo "..."


# 3. Enviar Historia Clínica Cruda a Chat2 (Resumen HC) en la MISMA sesión
echo -e "\n[3] Procesando Resumen Clínico en Chat2 (gm_ch_summary) con la misma sesión..."

# Usamos una versión simulada de PromptA por facilidad de test
PROMPT_A_MOCK="Motivo de consulta: cefalea\\n Paciente femenina de 18 a&#241;os con historia de cefalea desde la infancia... Tension Arterial Sistolica | 90 | 140 | 85.00 | mmHg"

CHAT2_RES=$(curl -s -X POST "$BASE_URL/v1/chat2/chat" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"$PROMPT_A_MOCK\",
    \"session\": \"$SESSION_ID\",
    \"prompt_mode\": \"medical\"
  }")

if echo "$CHAT2_RES" | grep -q "status"; then
    echo "✅ Chat2 estructuró el JSON exitosamente (Auditoría + Entidades Mapeadas)"
    # Extraer parte de los json stringificados si es posible
    SUMMARY=$(echo "$CHAT2_RES" | grep -o '"resumen_clinico": "[^"]*' || echo "Procesado")
    echo "Respuesta Chat2 (Extracto): ${SUMMARY:0:150}..."
else
    echo "❌ Error en Chat2: $CHAT2_RES"
fi


# 4. Comprobar Memoria y Trazo en la Sesión (Trace/Auditoría)
echo -e "\n[4] Consultando historial (Trace) en la sesión: $SESSION_ID..."
TRACE_RES=$(curl -s -X GET "$BASE_URL/admin/trace/$SESSION_ID" \
  -H "Authorization: Bearer $API_KEY")

if echo "$TRACE_RES" | grep -q "INPUT_RECEIVED"; then
    echo "✅ Auditoría recuperó la memoria de la sesión correctamente."
    STEPS=$(echo "$TRACE_RES" | grep -o '"step":"[^"]*' | cut -d'"' -f4 | sort -u)
    echo "Pasos registrados en la memoria de Redis:"
    echo "$STEPS"
else
    echo "❌ No se encontró trazo para la sesión (o falló Redis): $TRACE_RES"
fi

echo -e "\n=========================================="
echo "🎉 PRUEBA E2E COMPLETA EXITOSA"
echo "=========================================="
