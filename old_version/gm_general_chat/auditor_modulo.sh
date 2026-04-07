#!/bin/bash

echo "------------------------------------------------"
echo "🔍 AUDITORIA DE MODULO: GM_GENERAL_CHAT"
echo "------------------------------------------------"

# 1. Verificar Salud Local
echo -e "\n1. Verificando Salud del Motor..."
curl -s http://localhost:7005/health | grep -q "status" && echo "✅ Motor ONLINE" || echo "❌ Motor OFFLINE"

# 2. Verificar Inferencia e IA
echo -e "\n2. Probando respuesta de IA (Inferencia)..."
RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿cómo influye el paracetamol en el higado?", "prompt_mode": "medical"}' \
  http://localhost:7005/chat)

if echo "$RESPONSE" | grep -q "response"; then
    echo "✅ IA RESPONDIENDO"
    
    # 3. Verificar Política de Contabilidad (Usage)
    echo -e "\n3. Verificando Metadata de Consumo (Usage)..."
    if echo "$RESPONSE" | grep -q "usage"; then
        echo "✅ METADATA PRESENTE (Correcto para el Gateway)"
        # Extraer tokens para mostrar
        TOKENS=$(echo "$RESPONSE" | grep -o '"total_tokens":[0-9]*' | cut -d: -f2)
        echo "   Consumo detectado: $TOKENS tokens"
    else
        echo "⚠️ ALERTA: La respuesta no incluye 'usage'. El Gateway no podrá auditar costos."
    fi
else
    echo "❌ ERROR EN LA RESPUESTA DE IA"
    echo "$RESPONSE"
fi

echo -e "\n------------------------------------------------"
echo "🏁 AUDITORIA DE MODULO FINALIZADA"
echo "------------------------------------------------"
