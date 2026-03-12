#!/bin/bash
# startup.sh - Healthcare API Gateway - Instalación Automática
# Ejecutar con: curl -sSL https://raw.githubusercontent.com/cluna-8/gom-gateway/main/startup.sh | bash

set -e

echo "🏥 Healthcare API Gateway - Instalación Automática"
echo "=================================================="

# Verificar requisitos
echo "🔍 Verificando requisitos..."

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado. Instálalo desde: https://docs.docker.com/get-docker/"
    exit 1
fi

# Verificar Docker Compose y determinar comando
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ Docker Compose no está instalado."
    exit 1
fi

# Verificar Git
if ! command -v git &> /dev/null; then
    echo "❌ Git no está instalado."
    exit 1
fi

echo "✅ Todos los requisitos están instalados"

# Configuración
REPO_URL="https://github.com/cluna-8/gom-gateway.git"
PROJECT_DIR="healthcare-api-gateway"
DB_TYPE="sqlite"  # Por defecto SQLite

# Preguntar tipo de base de datos
echo ""
echo "💾 Configuración de Base de Datos:"
echo "1) SQLite (Desarrollo/Testing) - Recomendado"
echo "2) Azure SQL (Producción)"
echo ""
read -p "Selecciona tipo de base de datos (1 o 2) [1]: " db_choice

case $db_choice in
    2)
        DB_TYPE="azure"
        echo ""
        echo "📋 Configuración Azure SQL:"
        read -p "Servidor (sin .database.windows.net): " azure_server
        read -p "Base de datos: " azure_database
        read -p "Usuario: " azure_username
        read -s -p "Contraseña: " azure_password
        echo ""
        ;;
    *)
        DB_TYPE="sqlite"
        echo "✅ Usando SQLite para desarrollo"
        ;;
esac

# Limpiar instalación anterior si existe
if [ -d "$PROJECT_DIR" ]; then
    echo "🗑️ Limpiando instalación anterior..."
    rm -rf "$PROJECT_DIR"
fi

# Clonar repositorio
echo "📥 Clonando repositorio..."
git clone "$REPO_URL" "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Crear archivo .env
echo "⚙️ Configurando entorno..."
if [ "$DB_TYPE" = "azure" ]; then
    cat > .env << EOF
# Healthcare API Gateway - Configuración
DATABASE_URL=mssql+pyodbc://${azure_username}:${azure_password}@${azure_server}.database.windows.net/${azure_database}?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
ENVIRONMENT=production
JWT_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || date +%s | sha256sum | base64 | head -c 32)
MEDICAL_API_URL=http://healthcare-chat-api:7005
LOG_LEVEL=INFO
CORS_ORIGINS=*
EOF
    echo "✅ Configuración Azure SQL creada"
else
    cat > .env << EOF
# Healthcare API Gateway - Configuración
DATABASE_URL=sqlite:///./data/healthcare_gateway.db
ENVIRONMENT=development
JWT_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || date +%s | sha256sum | base64 | head -c 32)
MEDICAL_API_URL=http://healthcare-chat-api:7005
LOG_LEVEL=INFO
CORS_ORIGINS=*
EOF
    echo "✅ Configuración SQLite creada"
fi

# Verificar estructura de archivos
echo "📋 Verificando archivos del proyecto..."
required_files=(
    "docker-compose.yml"
    "api-gateway/main.py"
    "api-gateway/requirements.txt"
    "api-gateway/Dockerfile"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Archivo faltante: $file"
        exit 1
    fi
done

echo "✅ Todos los archivos están presentes"

# Construir y levantar servicios
echo ""
echo "🐳 Construyendo e iniciando servicios..."
echo "Esto puede tomar unos minutos la primera vez..."

# Detener servicios existentes si están corriendo
$DOCKER_COMPOSE down 2>/dev/null || true

# Construir y levantar
if $DOCKER_COMPOSE up --build -d; then
    echo "✅ Servicios iniciados correctamente"
else
    echo "❌ Error iniciando servicios"
    echo "📋 Logs de error:"
    $DOCKER_COMPOSE logs --tail=50
    exit 1
fi

# Esperar a que el servicio esté listo
echo "⏳ Esperando a que el servicio esté listo..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        break
    fi
    echo "   Intento $((attempt + 1))/$max_attempts..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ El servicio no respondió después de 60 segundos"
    echo "📋 Logs:"
    docker-compose logs --tail=20 api-gateway
    exit 1
fi

# Verificar instalación
echo ""
echo "🔍 Verificando instalación..."

# Health check
health_response=$(curl -s http://localhost:8000/health)
if echo "$health_response" | grep -q "healthy"; then
    echo "✅ Health check: OK"
else
    echo "⚠️ Health check: Warning"
fi

# Obtener tokens
echo ""
echo "🔑 Obteniendo tokens de acceso..."
tokens_response=$(curl -s -X GET "http://localhost:8000/admin/tokens" \
    -H "Authorization: Bearer hcg_gomedisys_admin_9120B76F636BE172" 2>/dev/null)

if [ $? -eq 0 ] && echo "$tokens_response" | grep -q "hcg_"; then
    echo "✅ Tokens creados correctamente"
else
    echo "⚠️ Advertencia: No se pudieron verificar los tokens"
fi

# Mostrar información final
echo ""
echo "🎉 ¡INSTALACIÓN COMPLETADA!"
echo "=========================="
echo ""
echo "🌐 URLs de Acceso:"
echo "   • API Gateway: http://localhost:8000"
echo "   • Documentación: http://localhost:8000/docs"
echo "   • Health Check: http://localhost:8000/health"
echo ""
echo "🔑 Tokens Predefinidos:"
echo "   • ADMIN:   hcg_gomedisys_admin_9120B76F636BE172"
echo "   • USER:    hcg_gomedisys_user_demo_8025A4507BCBD1D1"
echo "   • MONITOR: hcg_gomedisys_monitor_32B581AA6DA7442D"
echo ""
echo "📋 Comandos Útiles:"
echo "   • Ver logs:        $DOCKER_COMPOSE logs -f"
echo "   • Parar servicios: $DOCKER_COMPOSE down"
echo "   • Reiniciar:       $DOCKER_COMPOSE restart"
echo ""
echo "📖 Para más información, consulta:"
echo "   • Manual de usuario: http://localhost:8000/docs"
echo "   • Repositorio: https://github.com/cluna-8/gom-gateway"
echo ""

# Prueba rápida
echo "🧪 Prueba rápida de la API:"
test_response=$(curl -s -X POST "http://localhost:8000/medical/chat" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
    -d '{"message": "Hello", "session": "test"}' 2>/dev/null)

if [ $? -eq 0 ]; then
    echo "✅ API médica respondiendo correctamente"
else
    echo "⚠️ API médica no disponible (normal si healthcare-chat-api no está corriendo)"
fi

echo ""
echo "🚀 Sistema listo para usar!"

# Opcional: abrir navegador
if command -v xdg-open &> /dev/null; then
    read -p "¿Abrir documentación en el navegador? (y/N): " open_browser
    if [[ $open_browser =~ ^[Yy]$ ]]; then
        xdg-open http://localhost:8000/docs
    fi
elif command -v open &> /dev/null; then
    read -p "¿Abrir documentación en el navegador? (y/N): " open_browser
    if [[ $open_browser =~ ^[Yy]$ ]]; then
        open http://localhost:8000/docs
    fi
fi