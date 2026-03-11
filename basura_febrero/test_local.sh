#!/bin/bash

# Test Suite Local para GoMedisys
# Verifica: Chat estándar, MCP (ICD-10), y Auditoría de Seguridad

API_URL="http://localhost:8000"
TOKEN="hcg_maestro_123"

echo "================================================================"
echo "       GoMedisys Local Test Suite                              "
echo "       Target: localhost:8000                                   "
echo "================================================================"
echo ""

# Test 1: Health Check
echo "[1/4] Probando Health Check (Gateway)..."
HEALTH=$(curl -s ${API_URL}/health)
if echo "$HEALTH" | grep -q "online"; then
    echo "✓ Gateway Online"
else
    echo "✗ Gateway Offline"
    exit 1
fi
echo ""

# Test 2: Chat Estándar
echo "[2/4] Probando Chat Estándar (Asma)..."
RESPONSE=$(curl -s -X POST ${API_URL}/medical/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "promptData": "¿Qué es el asma?",
    "sessionId": "test_local_std",
    "IAType": "medical"
  }')

if echo "$RESPONSE" | jq -e '.data.response' > /dev/null 2>&1; then
    echo "$RESPONSE" | jq -r '.data.response' | head -c 100
    echo ""
    echo "✓ Chat Estándar OK"
else
    echo "✗ Chat Estándar FALLÓ"
    echo "$RESPONSE" | jq '.'
fi
echo ""

# Test 3: MCP (ICD-10)
echo "[3/4] Probando Conectividad MCP (ICD-10 - Cefalea)..."
RESPONSE=$(curl -s -X POST ${API_URL}/medical/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "promptData": "Dame el código CIE-10 para cefalea",
    "sessionId": "test_local_icd",
    "IAType": "medical"
  }')

if echo "$RESPONSE" | jq -e '.data.response' > /dev/null 2>&1; then
    RESP_TEXT=$(echo "$RESPONSE" | jq -r '.data.response')
    echo "$RESP_TEXT" | head -c 150
    echo ""
    if echo "$RESP_TEXT" | grep -qi "R51\|cefalea"; then
        echo "✓ MCP (ICD-10) OK"
    else
        echo "✗ MCP (ICD-10) - Respuesta inesperada"
    fi
else
    echo "✗ Error en consulta MCP"
    echo "$RESPONSE" | jq '.'
fi
echo ""

# Test 4: Auditoría de Seguridad
echo "[4/4] Probando Alerta de Seguridad (Alergia Detectada)..."
RESPONSE=$(curl -s -X POST ${API_URL}/medical/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "promptData": "¿Puedo tomar Amoxicilina?",
    "sessionId": "test_local_audit",
    "IAType": "medical",
    "context": {"alergias": "Penicilina"}
  }')

if echo "$RESPONSE" | jq -e '.data.response' > /dev/null 2>&1; then
    RESP_TEXT=$(echo "$RESPONSE" | jq -r '.data.response')
    echo "$RESP_TEXT" | head -c 200
    echo ""
    if echo "$RESP_TEXT" | grep -qi "alergia\|penicilina\|evitar\|riesgo"; then
        echo "✓ Auditoría de Seguridad OK (Alerta detectada)"
    else
        echo "✗ Alerta de Seguridad NO detectada"
    fi
else
    echo "✗ Error en auditoría"
    echo "$RESPONSE" | jq '.'
fi
echo ""

echo "================================================================"
echo "             TODAS LAS PRUEBAS COMPLETADAS                     "
echo "================================================================"
