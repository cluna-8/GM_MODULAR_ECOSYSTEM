#!/bin/bash

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "📄 Solicitando Resumen Clínico a Chat2..."
echo "=========================================="

# 1. Autenticación automática para pruebas
TOKEN_MSG=$(curl -s -X POST "$BASE_URL/admin/tokens" \
  -H "Content-Type: application/json" \
  -d '{"username": "test_viewer", "name": "Summary Viewer Token"}')

API_KEY=$(echo "$TOKEN_MSG" | grep -o '"token":"[^"]*' | cut -d'"' -f4)

# 2. Historia clínica de prueba real (Desde docs/Chat2/PromptA.txt)
echo "Leyendo el archivo crudo original docs/Chat2/PromptA.txt..."
# Usamos jq para escapar todo el texto peligroso (comillas, saltos de línea) de forma segura
PROMPT_A_REAL=$(cat docs/Chat2/PromptA.txt | jq -Rs .)

# 3. Llamada al endpoint
echo "Enviando texto a la Inteligencia Artificial (puede tardar un momento)..."
echo "------------------------------------------"

# Inyectamos el payload json a mano agregando el string escapado por jq
RES=$(curl -s -X POST "$BASE_URL/v1/chat2/chat" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": $PROMPT_A_REAL,
    \"prompt_mode\": \"medical\"
  }")

# 4. Formatear la salida para que sea 100% legible
echo "$RES" > .raw_res.json

# Verificamos si la herramienta jq está instalada para imprimir bonito a color
if command -v jq &> /dev/null; then
    echo -e "\n🏥 OUTPUT ENRIQUECIDO (JSON):\n"
    # El campo response viene como un JSON stringificado, así que usamos fromjson si jq soporta o lo imprimimos parseando
    # Imprimos toda la data limpia
    cat .raw_res.json | jq -r '.data.response' | jq .
else
    # Si no tiene jq en la máquina, usamos python integrado
    echo -e "\n🏥 OUTPUT ENRIQUECIDO (JSON):\n"
    python3 -c "import sys, json;
data=json.load(open('.raw_res.json'))
try:
    inner = json.loads(data['data']['response'])
    print(json.dumps(inner, indent=4, ensure_ascii=False))
except:
    print(data)
"
fi

rm -f .raw_res.json
echo -e "\n=========================================="
