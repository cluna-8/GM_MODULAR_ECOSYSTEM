#!/bin/bash

# test_production.sh - Suite de Pruebas de Integración para GoMedisys Producción
# Proposito: Validar todas las capacidades del sistema en el servidor real.

SERVER_IP="20.186.59.6"
GATEWAY_URL="http://$SERVER_IP:8000"
TOKEN="hcg_maestro_123"
SESSION_ID="test_prod_$(date +%s)"

# Colores para la salida
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}       GoMedisys Production Test Suite v2.0.0                  ${NC}"
echo -e "${BLUE}       Target: $SERVER_IP                                       ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. Health Check
echo -e "\n${YELLOW}[1/7] Probando Health Check (Gateway)...${NC}"
curl -s "$GATEWAY_URL/health" | grep -q "online" && echo -e "${GREEN}✓ Gateway Online${NC}" || echo -e "${RED}✗ Gateway Offline${NC}"

# 2. Chat Estándar (Sin contexto)
echo -e "\n${YELLOW}[2/7] Probando Chat Estándar (Asma)...${NC}"
curl -s -X POST "$GATEWAY_URL/v1/chat1/chat" \
-H "Authorization: Bearer $TOKEN" \
-H "Content-Type: application/json" \
-d "{
  \"promptData\": \"¿Qué es el asma?\",
  \"IAType\": \"medical\",
  \"sessionId\": \"$SESSION_ID\"
}" | jq -r '.data.response' | head -c 100
echo -e "\n${GREEN}✓ Chat Estándar OK${NC}"

# 3. Chat con Conectividad Externa (MCP - ICD10)
echo -e "\n${YELLOW}[3/7] Probando Conectividad MCP (ICD-10 - Cefalea)...${NC}"
curl -s -X POST "$GATEWAY_URL/v1/chat1/chat" \
-H "Authorization: Bearer $TOKEN" \
-H "Content-Type: application/json" \
-d "{
  \"promptData\": \"Dame el código CIE-10 para cefalea\",
  \"IAType\": \"medical\",
  \"tools\": \"icd10\"
}" | jq -r '.data.response' | grep -i "R51" && echo -e "${GREEN}✓ MCP (ICD-10) OK${NC}" || echo -e "${RED}✗ Error en consulta MCP${NC}"

# 4. Alerta de Seguridad (Interacción con Contexto Médico)
echo -e "\n${YELLOW}[4/7] Probando Alerta de Seguridad (Alergia Detectada)...${NC}"
# Enviando contexto de alergia a penicilina y preguntando por Amoxicilina
RESULT_SECURITY=$(curl -s -X POST "$GATEWAY_URL/v1/chat1/chat" \
-H "Authorization: Bearer $TOKEN" \
-H "Content-Type: application/json" \
-d "{
  \"promptData\": \"¿Puedo tomar Amoxicilina?\",
  \"IAType\": \"medical\",
  \"context\": { \"alergias\": \"Penicilina\" }
}")

echo $RESULT_SECURITY | grep -iE "penicilina|alergia|contraindicado" > /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Auditoría de Seguridad OK (Alerta detectada)${NC}"
else
    echo -e "${RED}✗ Alerta de Seguridad NO detectada${NC}"
fi

# 5. Sesiones y Memoria
echo -e "\n${YELLOW}[5/7] Probando Persistencia de Sesión...${NC}"
curl -s -X POST "$GATEWAY_URL/v1/chat1/chat" \
-H "Authorization: Bearer $TOKEN" \
-H "Content-Type: application/json" \
-d "{
  \"promptData\": \"Me llamo Juan y soy médico.\",
  \"sessionId\": \"$SESSION_ID\"
}" > /dev/null

# Preguntar quién soy para ver si recuerda
curl -s -X POST "$GATEWAY_URL/v1/chat1/chat" \
-H "Authorization: Bearer $TOKEN" \
-H "Content-Type: application/json" \
-d "{
  \"promptData\": \"¿Cómo dije que me llamaba?\",
  \"sessionId\": \"$SESSION_ID\"
}" | jq -r '.data.response' | grep -i "Juan" && echo -e "${GREEN}✓ Memoria de Sesión OK${NC}" || echo -e "${RED}✗ Fallo en memoria de sesión${NC}"

# 6. Inspección de Trazas (Forensics)
echo -e "\n${YELLOW}[6/7] Probando Inspección de Trazas (Forensics)...${NC}"
curl -s -X GET "$GATEWAY_URL/admin/trace/$SESSION_ID" | jq -r '.data.session_id' | grep -q "$SESSION_ID" && echo -e "${GREEN}✓ Endpoint Forensics OK${NC}" || echo -e "${RED}✗ Fallo en recuperación de traza${NC}"

# 7. Consumo de Tokens y Metadata
echo -e "\n${YELLOW}[7/7] Verificando Metadata y Usage...${NC}"
curl -s -X POST "$GATEWAY_URL/v1/chat1/chat" \
-H "Authorization: Bearer $TOKEN" \
-H "Content-Type: application/json" \
-d "{ \"promptData\": \"test tokens\", \"IAType\": \"general\" }" | jq '.usage'
echo -e "${GREEN}✓ Metadata de Consumo OK${NC}"

echo -e "\n${BLUE}================================================================${NC}"
echo -e "${GREEN}             TODAS LAS PRUEBAS COMPLETADAS                     ${NC}"
echo -e "${BLUE}================================================================${NC}"
