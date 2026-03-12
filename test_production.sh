#!/bin/bash
# ======================================================
# 🏥 GM_MODULAR_ECOSYSTEM - Suite de Pruebas PRODUCCIÓN
# Servidor: http://20.186.59.6:8000
# Token fijo del cliente: hcg_maestro_123
# ======================================================

BASE_URL="http://localhost:8000"
ADMIN_TOKEN="hcg_maestro_123"
SESSION_ID="test_session_$(date +%s)"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       🏥 GoMedisys - Suite de Pruebas Completa          ║"
echo "║       Servidor: $BASE_URL                               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── PASO 0: Crear un Token de prueba nuevo (dinámico) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 PASO 0: Generando un nuevo API Token de prueba..."
TOKEN_RES=$(curl -s -X POST "$BASE_URL/admin/tokens" \
  -H "Content-Type: application/json" \
  -d '{"username": "tester_pruebas", "name": "Token de Pruebas QA"}')
echo "Respuesta JSON: $TOKEN_RES"
API_KEY=$(echo "$TOKEN_RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('token','ERROR'))")
echo "🔑 API Key generada: $API_KEY"
echo ""

# ── PASO 1: Health Check ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🟢 PASO 1: Health Check del Sistema..."
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""

# ── PASO 2: Listar tokens registrados ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 PASO 2: Tokens registrados en el sistema..."
curl -s "$BASE_URL/admin/tokens" | python3 -m json.tool
echo ""

# ── PASO 3: Chat 1 - Asistente Médico General ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💬 PASO 3: Chat 1 - Consulta médica general..."
echo "   URL: $BASE_URL/medical/chat"
CHAT1_RES=$(curl -s -X POST "$BASE_URL/medical/chat" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"promptData\": \"¿Cuáles son los síntomas de la migraña con aura?\",
    \"IAType\": \"medical\",
    \"session\": \"$SESSION_ID\"
  }")
echo "$CHAT1_RES" | python3 -m json.tool

# Capturamos el session_id REAL que devuelve el sistema para usar en los pasos siguientes
REAL_SESSION=$(echo "$CHAT1_RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id', ''))" 2>/dev/null)
if [ -n "$REAL_SESSION" ]; then
  echo "🔑 Session ID capturado: $REAL_SESSION"
  SESSION_ID="$REAL_SESSION"
fi
echo ""

# ── PASO 4: Chat 1 - Prueba de Persistencia (misma sesión real) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 PASO 4: Chat 1 - Prueba de PERSISTENCIA..."
echo "   Usando sesión: $SESSION_ID"
CHAT1_MEM=$(curl -s -X POST "$BASE_URL/medical/chat" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"promptData\": \"¿Y cuál es el tratamiento de primera línea para lo que me dijiste?\",
    \"IAType\": \"medical\",
    \"session\": \"$SESSION_ID\"
  }")
RESPUESTA=$(echo "$CHAT1_MEM" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('response','Sin respuesta'))")
COUNT=$(echo "$CHAT1_MEM" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('conversation_count', 'N/A'))")
echo "✅ conversation_count: $COUNT  (si es > 1, la memoria funciona)"
echo "Respuesta (truncada): ${RESPUESTA:0:300}..."
echo ""

# ── PASO 5: Chat 2 - Resumen Clínico (URL amigable nueva) ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📄 PASO 5: Chat 2 - Resumen Clínico Estructurado..."
echo "   URL: $BASE_URL/medical/summary  ← NUEVA URL DEL CLIENTE"
HISTORIA="Paciente femenina 18 años. Cefalea biparietal pulsátil desde infancia. Intensidad 8/10. Fotofobia, sonofobia. Episodios de síncope en bipedestación. TAC normal. Eco normal. Dx: Migraña sin aura + síncope vasovagal. Tratamiento: Enoxaparina + Naproxeno + Dexametasona. Alta con seguimiento neurología."

SUMMARY_RES=$(curl -s -X POST "$BASE_URL/medical/summary" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"$HISTORIA\",
    \"prompt_mode\": \"medical\",
    \"session\": \"$SESSION_ID\"
  }")

echo ""
echo "🔬 JSON Estructurado del Resumen:"
echo "$SUMMARY_RES" | python3 -c "
import sys, json
try:
    outer = json.load(sys.stdin)
    data = outer.get('data', {})
    # El campo puede ser 'response' o 'final_response' segun la version del servicio
    inner_str = data.get('response') or data.get('final_response', '{}')
    if isinstance(inner_str, str):
        inner = json.loads(inner_str)
    else:
        inner = inner_str
    print(json.dumps(inner, indent=2, ensure_ascii=False))
except Exception as e:
    print('Respuesta cruda (error de parsing):', str(e))
    print(json.dumps(outer if 'outer' in dir() else {}, indent=2, ensure_ascii=False))
"
echo ""

# ── PASO 6: Tokens consumidos ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 PASO 6: Consumo de tokens del cliente (hcg_maestro_123)..."
curl -s "$BASE_URL/admin/usage/$ADMIN_TOKEN" | python3 -m json.tool
echo ""

# ── PASO 7: Persistencia - Traza de sesión ──
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 PASO 7: Traza de sesión: $SESSION_ID"
curl -s "$BASE_URL/admin/trace/$SESSION_ID" | python3 -m json.tool

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              ✅ Suite de Pruebas Completada              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "📌 Resumen de Endpoints para el Cliente:"
echo "   🗨  Chat General:  POST $BASE_URL/medical/chat"
echo "   📄 Resumen HC:    POST $BASE_URL/medical/summary  ← NUEVO"
echo "   🔑 Token cliente: Bearer hcg_maestro_123"
echo "   🧠 Persistencia:  7 días por sessionId"
echo ""
