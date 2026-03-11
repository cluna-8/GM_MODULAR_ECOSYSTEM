#!/bin/bash
API_URL="http://20.186.59.6:8000/medical/chat"
TOKEN="hcg_maestro_123"

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

echo "# Resultados Pruebas" > test_results_remoto.md

for p in "${PROMPTS[@]}"; do
  echo "---" >> test_results_remoto.md
  echo "**Prompt:** $p" >> test_results_remoto.md
  echo "Ejecutando: $p"
  
  RESP=$(curl -s -X POST "$API_URL" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"promptData\": \"$p\",
      \"IAType\": \"medical\"
    }")
    
  echo "$RESP" | jq -r '.data.response // .data.error // "No response data"' >> test_results_remoto.md
done
