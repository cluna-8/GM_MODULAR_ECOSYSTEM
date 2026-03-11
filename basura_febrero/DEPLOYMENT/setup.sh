#!/bin/bash

# setup.sh - GoMedisys Orchestrator Setup Script
# Proposito: Automatizar el despliegue de los servicios de GoMedisys en servidor.

# Colores para la salida
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}       GoMedisys Orchestrator - Server Setup v2.0.0            ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. Verificar dependencias
echo -e "\n${YELLOW}[1/4] Verificando dependencias...${NC}"
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Error: Docker no esta instalado.${NC}" >&2; exit 1; }

# Verificar Docker Compose (hyphen or space)
if command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo -e "${RED}Error: Docker Compose no esta instalado.${NC}" >&2
    exit 1
fi

command -v git >/dev/null 2>&1 || { echo -e "${RED}Error: Git no esta instalado.${NC}" >&2; exit 1; }
echo -e "${GREEN}✓ Dependencias OK ($DOCKER_COMPOSE_CMD detected)${NC}"

# 2. Clonar / Actualizar Repositorios
echo -e "\n${YELLOW}[2/4] Configurando repositorios de servicios...${NC}"
mkdir -p SERVICES

# Definir repositorios
REPOS=(
    "GM_GENERAL_CHAT;https://github.com/cluna-8/GM_GENERAL_CHAT.git"
    "GM_ADM_MODULAR;https://github.com/cluna-8/GM_ADM_MODULAR.git"
    "GM_MEDICAL_AUDITOR;https://github.com/cluna-8/GM_MEDICAL_AUDITOR.git"
)

for repo_data in "${REPOS[@]}"; do
    IFS=";" read -r folder url <<< "$repo_data"
    if [ -d "SERVICES/$folder" ]; then
        echo -e "${BLUE}Actualizando $folder...${NC}"
        cd "SERVICES/$folder" && git pull && cd ../..
    else
        echo -e "${BLUE}Clonando $folder...${NC}"
        git clone "$url" "SERVICES/$folder"
    fi
done

# 3. Configuración de Entorno
echo -e "\n${YELLOW}[3/4] Inicializando entorno...${NC}"
# Crear redes de docker si no existen
docker network create gomedisys-net 2>/dev/null || true

# Asegurar archivos .env básicos si no existen (placeholder)
for folder in GM_GENERAL_CHAT GM_ADM_MODULAR GM_MEDICAL_AUDITOR; do
    if [ ! -f "SERVICES/$folder/.env" ] && [ -f "SERVICES/$folder/.env.example" ]; then
        cp "SERVICES/$folder/.env.example" "SERVICES/$folder/.env"
        echo -e "${YELLOW}Aviso: Se creo .env por defecto para $folder. Por favor revise las credenciales.${NC}"
    fi
done

# 4. Despliegue
echo -e "\n${YELLOW}[4/4] Preparado para lanzar contenedores...${NC}"
echo -e "Use el siguiente comando para iniciar el sistema:"
echo -e "${GREEN}$DOCKER_COMPOSE_CMD up -d --build${NC}"

echo -e "\n${BLUE}================================================================${NC}"
echo -e "${GREEN}Configuracion completada con exito.${NC}"
echo -e "Consulte README_DEPLOY.md para mas informacion."
echo -e "${BLUE}================================================================${NC}"
