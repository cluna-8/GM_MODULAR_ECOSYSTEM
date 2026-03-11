# 🚀 Guía de Despliegue - GoMedisys Orchestrator

Este repositorio/carpeta contiene todo lo necesario para desplegar la suite completa de GoMedisys en un servidor limpio.

## 📁 Estructura del Paquete
- `setup.sh`: Script de automatización (clonación de repos y verificación).
- `docker-compose.yml`: Orquestador de contenedores de producción.
- `docs/`: Manuales, diagrama y resumen ejecutivo.
- `SERVICES/`: Directorio donde se descargarán los módulos (Chat, Modular, Auditor).

## 🛠️ Requisitos Previos
1.  **Docker** y **Docker Compose** instalados.
2.  **Git** configurado.
3.  **Acceso SSH/Internet** para clonar los repositorios de GitHub.

> [!TIP]
> **Optimización CPU**: El sistema ha sido configurado para instalar versiones de `torch` optimizadas para CPU (sin CUDA), asegurando un rendimiento fluido y un menor consumo de recursos en servidores sin GPU.

## 🏗️ Instrucciones de Despligue

1.  **Preparar el Script**:
    Asegúrese de que el script tenga permisos de ejecución:
    ```bash
    chmod +x setup.sh
    ```

2.  **Ejecutar el Setup**:
    ```bash
    ./setup.sh
    ```
    *Este comando clonará automáticamente los repositorios necesarios en la carpeta `SERVICES/`.*

3.  **Configurar Variables de Entorno**:
    Edite el archivo `.env` en `SERVICES/GM_GENERAL_CHAT/.env` e incluya su `OPENAI_API_KEY`.

4.  **Lanzar el Sistema**:
    ```bash
    docker-compose up -d --build
    ```

## 🏁 Verificación
Una vez levantado:
- **API Gateway**: `http://localhost:8000/health`
- **IA Engine**: `http://localhost:7005/health`

Para más detalles sobre la integración, consulte `docs/MANUAL_API_CLIENTE.md`.
