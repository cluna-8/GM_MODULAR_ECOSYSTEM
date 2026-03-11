#!/bin/bash
SERVER_IP="localhost"
API_URL="http://$SERVER_IP:8000/medical/chat"
TOKEN="hcg_maestro_123"

# Array of prompts
PROMPTS=(
  "que es el asma"
  "protocolo par el asma"
  "necesito ayuda con las formulas de las curvas de crecimiento"
  "listame las curvas de crecimietno"
  "tipos de dolor de cabeza"
  "formula del indice de masa corporal"
  "Protocolos de cancer"
  "cual es el protocolo para el cancer de estomago"
  "necesito ayuda con la formula del indice de masa corporal"
  "formula para calcular la funcion del riñon"
  "que contraindicaciones tiene el sulfato de plata en un paciente con herida en el tobillo"
  "¿Cuáles son los diagnósticos diferenciales más probables para este conjunto de síntomas y resultados de laboratorio? dolor de cabeza, marea, vision borrosa"
  "¿Qué interacciones medicamentosas existen entre estos fármacos y cuál es su nivel de riesgo? acetaminofen y diclofenaco"
  "¿Cuál es la dosis ajustada recomendada de este medicamento en un paciente con insuficiencia renal o hepática? acetaminofen 500"
  "¿Cómo comunicar este diagnóstico complejo al paciente de manera clara y basada en evidencia? Paciente con dolor torácico. Tengo un hombre de 58 años, diabético e hipertenso, con dolor torácico opresivo de 40 minutos de evolución y troponina ligeramente elevada. ¿Cuáles son los diagnósticos diferenciales más probables y qué algoritmo diagnóstico debería seguir?"
  "Fiebre en niño pequeño. Niño de 18 meses con fiebre de 39 grados sin foco claro tras exploración inicial normal. Qué criterios clínicos me ayudan a decidir manejo ambulatorio versus hospitalización"
)

rm -f test_results.md
echo "# Resultados de Pruebas de Prompts" > test_results.md
echo "Fecha: $(date)" >> test_results.md
echo "---" >> test_results.md

for i in "${!PROMPTS[@]}"; do
  PROMPT="${PROMPTS[$i]}"
  echo "Probando prompt $((i+1))/${#PROMPTS[@]}: $PROMPT"
  
  RESPONSE=$(curl -s -X POST $API_URL \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"promptData\": \"$PROMPT\",
      \"IAType\": \"medical\",
      \"sessionId\": \"test_prompt_$i\"
    }")
    
  echo "## Prompt $((i+1))" >> test_results.md
  echo "**Pregunta:** $PROMPT" >> test_results.md
  
  ERROR_MSG=$(echo "$RESPONSE" | jq -r '.data.error // empty')
  if [ -n "$ERROR_MSG" ]; then
    echo "**Error:** $ERROR_MSG" >> test_results.md
  else
    RESP_TEXT=$(echo "$RESPONSE" | jq -r '.data.response // .message')
    echo "**Respuesta:**" >> test_results.md
    echo "> $RESP_TEXT" >> test_results.md
  fi
  echo "---" >> test_results.md
done
echo "Finalizado."
