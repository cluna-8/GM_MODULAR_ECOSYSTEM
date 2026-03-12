# 🏥 Healthcare API Gateway

Sistema de autenticación y control de acceso para API médica con gestión de usuarios, tokens y monitoreo de costos.

## 🚀 Instalación Rápida (Un Solo Comando)

### Opción 1: Instalación Automática
```bash
curl -sSL https://raw.githubusercontent.com/cluna-8/gom-gateway/main/startup.sh | bash
```

### Opción 2: Instalación Manual
```bash
# Clonar repositorio
git clone https://github.com/cluna-8/gom-gateway.git
cd gom-gateway

# Configurar entorno (opcional)
cp .env.example .env
# Editar .env si necesitas Azure SQL

# Levantar servicios
docker-compose up --build
```

## ✅ Verificación

Después de la instalación, verifica que todo funcione:

```bash
# Health check
curl http://localhost:8000/health

# Prueba de API
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{"message": "¿Qué es la diabetes?", "session": "test"}'
```

## 🔑 Tokens Predefinidos

| Rol | Token | Descripción |
|-----|-------|-------------|
| **ADMIN** | `hcg_gomedisys_admin_9120B76F636BE172` | Gestión completa |
| **USER** | `hcg_gomedisys_user_demo_8025A4507BCBD1D1` | Uso médico |
| **MONITOR** | `hcg_gomedisys_monitor_32B581AA6DA7442D` | Solo visualización |

## 📋 URLs Importantes

- **Documentación API:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Admin Panel:** http://localhost:8000/admin/*
- **API Médica:** http://localhost:8000/medical/*

## 🗄️ Configuración de Base de Datos

### SQLite (Por Defecto)
```bash
DATABASE_URL=sqlite:///./data/healthcare_gateway.db
```

### Azure SQL
```bash
DATABASE_URL=mssql+pyodbc://usuario:password@servidor.database.windows.net/database?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
```

## 🛠️ Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f

# Reiniciar servicios
docker-compose restart

# Parar todo
docker-compose down

# Limpiar y reinstalar
docker-compose down
docker volume prune -f
docker-compose up --build
```

## 📖 Documentación Completa

- [Manual de Usuario](docs/user-manual.md)
- [Manual de Administración](docs/admin-guide.md)
- [API Reference](http://localhost:8000/docs)

## 🔧 Troubleshooting

### Error: "Cannot connect to database"
```bash
# Para SQLite
docker-compose down
docker volume rm gom-gateway_gateway_data
docker-compose up

# Para Azure SQL - verificar configuración en .env
```

### Error: "Port 8000 already in use"
```bash
# Cambiar puerto en docker-compose.yml
ports:
  - "8001:8000"  # Usar puerto 8001
```

### Ver logs detallados
```bash
docker-compose logs api-gateway
```

## 🌟 Características

- ✅ **Autenticación JWT** y tokens API
- ✅ **Gestión de usuarios** y roles (Admin/User/Monitor)
- ✅ **Monitoreo de costos** y uso de tokens
- ✅ **Proxy seguro** para API médica
- ✅ **Herramientas médicas** (FDA, PubMed, Clinical Trials, ICD-10)
- ✅ **Chat en tiempo real** con WebSocket
- ✅ **Base de datos** SQLite o Azure SQL
- ✅ **Documentación automática** con Swagger
- ✅ **Health checks** y métricas

## 🤝 Contribuir

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver [LICENSE](LICENSE) para detalles.

## 📞 Soporte

- **Issues:** https://github.com/cluna-8/gom-gateway/issues
- **Documentación:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health