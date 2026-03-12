#!/bin/bash

# ============================================================================
# AUDITOR DE PRUEBAS CLÍNICAS - GOMEDISYS HYBRID
# ============================================================================

echo "------------------------------------------------"
echo "🔍 INICIANDO AUDITORÍA INTEGRAL DE CAPACIDADES"
echo "------------------------------------------------"

# Configuración
BASE_URL="http://localhost:8000/medical/chat"
AUTH_HEADER="Authorization: Bearer hcg_maestro_123"
CONTENT_TYPE="Content-Type: application/json"

# Función para ejecutar pruebas
ejecutar_prueba() {
    local TITULO=$1
    local JSON_BODY=$2
    
    echo -e "\n🧪 PRUEBA: $TITULO"
    
    RESPONSE=$(curl -s -X POST \
      -H "$AUTH_HEADER" \
      -H "$CONTENT_TYPE" \
      -d "$JSON_BODY" \
      "$BASE_URL")
    
    # Verificar éxito
    SUCCESS=$(echo "$RESPONSE" | jq -r '.status' 2>/dev/null)
    
    if [ "$SUCCESS" == "success" ]; then
        echo "✅ ÉXITO"
        
        # Extraer info
        MSG_COUNT=$(echo "$RESPONSE" | jq -r '.conversation_count' 2>/dev/null)
        PROVIDER=$(echo "$RESPONSE" | jq -r '.provider' 2>/dev/null)
        TOKENS=$(echo "$RESPONSE" | jq -r '.usage.total_tokens' 2>/dev/null)
        RESPONSE_TEXT=$(echo "$RESPONSE" | jq -r '.data.response' 2>/dev/null | head -c 100)
        TOOL=$(echo "$RESPONSE" | jq -r '.tool_used // "Ninguna"' 2>/dev/null)
        
        echo "   Módulo: $PROVIDER | Herramienta: $TOOL | Mensaje: #$MSG_COUNT"
        echo "   Contabilidad: $TOKENS tokens"
        echo "   Respuesta (preview): ${RESPONSE_TEXT}..."
    else
        echo "❌ ERROR"
        echo "   Detalle: $(echo "$RESPONSE" | jq -r '.message // "Error desconocido"') "
    fi
}

# 1. Prueba de Salud General
echo -e "\n1. Verificando Salud del Gateway..."
curl -s http://localhost:8000/health | grep -q "online" && echo "✅ Gateway ONLINE" || echo "❌ Gateway OFFLINE"

# 2. BATERÍA DE PRUEBAS DE CAPACIDADES
# ------------------------------------------------

# Prueba A: Especialista Clínico General (Modo Médico)
ejecutar_prueba "Consulta Clínica General (GPT-4o)" \
'{"message": "¿Cuáles son los síntomas de la diabetes tipo 2?", "prompt_mode": "medical", "session": "test_medical_'"$RANDOM"'"}'

# Prueba B: Herramienta FDA (Medicamentos)
# Esto prueba: Extracción -> API FDA -> Integración LLM
ejecutar_prueba "Consulta FDA (Búsqueda de Medicamento: Metformina)" \
'{"message": "Dime usos aprobados de la Metformina según la FDA", "tools": "fda", "session": "test_fda_'"$RANDOM"'"}'

# Prueba C: Herramienta PubMed (Investigación)
# Esto prueba: Búsqueda Científica -> Resumen LLM
ejecutar_prueba "Consulta PubMed (Investigación: Inmunoterapia)" \
'{"message": "Busca estudios recientes sobre inmunoterapia en cáncer de pulmón", "tools": "pubmed", "session": "test_pubmed_'"$RANDOM"'"}'

# Prueba D: Herramienta ICD-10 (Directa)
# Esto prueba: Búsqueda de códigos (Respuesta directa sin LLM para rapidez)
ejecutar_prueba "Consulta ICD-10 (Codificación: Hipertensión)" \
'{"message": "Código para hipertensión esencial", "tools": "icd10", "session": "test_icd_'"$RANDOM"'"}'

# Prueba E: Especialista Pediátrico
ejecutar_prueba "Cambio de Modo (Pediatría)" \
'{"message": "¿Qué dosis de paracetamol se recomienda para un niño de 12kg?", "prompt_mode": "pediatric", "session": "test_pedia_'"$RANDOM"'"}'

# 3. VERIFICACIÓN DE CONTABILIDAD FINAL
# ------------------------------------------------
echo -e "\n------------------------------------------------"
echo "📊 REPORTE DE CONTABILIDAD EN BASE DE DATOS"
echo "------------------------------------------------"

# Mostrar los últimos 5 registros de la base de datos
sqlite3 modular_gateway.db <<EOF
.headers on
.mode column
SELECT id, endpoint, total_tokens, timestamp FROM api_logs ORDER BY id DESC LIMIT 5;
EOF

echo -e "\n------------------------------------------------"
echo "🏁 AUDITORÍA FINALIZADA"
echo "------------------------------------------------"
