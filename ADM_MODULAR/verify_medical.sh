#!/bin/bash

# ============================================================================
# VERIFICADOR DE RESTRICCIÓN MÉDICA Y CONTEXTO HIS
# ============================================================================

echo "------------------------------------------------"
echo "🔍 VERIFICANDO NUEVAS RESTRICCIONES Y CONTEXTO"
echo "------------------------------------------------"

# Configuración
BASE_URL="http://localhost:8000/medical/chat"
AUTH_HEADER="Authorization: Bearer hcg_maestro_123"
CONTENT_TYPE="Content-Type: application/json"

ejecutar_consulta() {
    local TITULO=$1
    local JSON_BODY=$2
    
    echo -e "\n🧪 PRUEBA: $TITULO"
    
    RESPONSE=$(curl -s -X POST \
      -H "$AUTH_HEADER" \
      -H "$CONTENT_TYPE" \
      -d "$JSON_BODY" \
      "$BASE_URL")
    
    STATUS=$(echo "$RESPONSE" | jq -r '.status' 2>/dev/null)
    
    if [ "$STATUS" == "success" ]; then
        TEXT=$(echo "$RESPONSE" | jq -r '.data.response' 2>/dev/null)
        echo "✅ RESPUESTA RECIBIDA:"
        echo "------------------------------------------------"
        echo "$TEXT"
        echo "------------------------------------------------"
    else
        echo "❌ ERROR: $(echo "$RESPONSE" | jq -r '.message' 2>/dev/null)"
    fi
}

# 1. PRUEBA DE RESTRICCIÓN (No médico)
ejecutar_consulta "Pregunta No Médica (Cultura General)" \
'{
    "message": "¿Quién ganó el mundial de Qatar 2022?",
    "prompt_mode": "medical"
}'

# 2. PRUEBA DE CONTEXTO HIS (Médico con datos del paciente)
ejecutar_consulta "Pregunta Médica con Contexto HIS" \
'{
    "message": "¿Qué recomendaciones me das para mi dieta?",
    "prompt_mode": "medical",
    "context": {
        "paciente": "Carlos García",
        "edad": "52 años",
        "antecedentes": "Hipertensión arterial, Diabetes Tipo 2",
        "ultimo_peso": "95kg",
        "alergias": "Ninguna conocida"
    }
}'

# 3. PRUEBA DE RESTRICCIÓN (Pregunta banal)
ejecutar_consulta "Pregunta Banal (Clima)" \
'{
    "message": "¿Qué tiempo hace hoy en Madrid?",
    "prompt_mode": "general"
}'

echo -e "\n------------------------------------------------"
echo "🏁 VERIFICACIÓN FINALIZADA"
echo "------------------------------------------------"
