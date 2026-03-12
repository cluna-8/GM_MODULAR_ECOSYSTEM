# GM_MODULAR_ECOSYSTEM 🚀
## Sistema Inteligente de Gestión Médica - GoMedisys

Bienvenido al ecosistema modular de GoMedisys. Este repositorio es un **Monorepo** que agrupa todos los microservicios necesarios para el funcionamiento de los agentes de IA médicos, auditoría clínica y resúmenes de historias clínicas.

---

## 🏗 Arquitectura del Sistema

El ecosistema está compuesto por los siguientes servicios (ubicados en `/SERVICES`):

1.  **`ADM_MODULAR`**: Gateway de API central. Maneja la seguridad (API Keys), el ruteo de peticiones y el registro de consumo de tokens.
2.  **`gm_general_chat` (Chat 1)**: Asistente médico general con acceso a herramientas de consulta (FDA, PubMed) y memoria de conversación.
3.  **`gm_ch_summary` (Chat 2)**: Especialista en **Resumen Clínico**. Limpia datos crudos (incluso HTML sucio) para generar resúmenes técnicos de ~1000 palabras y extraer entidades médicas.
4.  **`medical_auditor`**: Motor de validación clínica. Detecta discrepancias en tiempo real y gestiona una caché semántica para respuestas consistentes.

---

## 🚀 Inicio Rápido (Docker)

El sistema está completamente orquestado con Docker. Para levantar todo el ecosistema:

1.  **Configurar Variables de Entorno**:
    Crea archivos `.env` en las carpetas de los servicios o asegúrate de que el contenedor principal tenga acceso a tu `OPENAI_API_KEY`.
    
2.  **Levantar el Sistema**:
    ```bash
    docker-compose up -d --build
    ```

3.  **Puertos Principales**:
    - **Gateway Central**: `http://localhost:8000`
    - **Redis (Caché)**: `6379`

---

## 🧪 Pruebas y Validación

Hemos incluido scripts de automatización para validar el flujo completo (End-to-End):

- **`./test_flow.sh`**: Realiza una prueba completa: genera llave API, chatea con el Chat 1, pide un resumen al Chat 2 y verifica la traza en la base de datos de auditoría.
- **`./test_summary.sh`**: Prueba específica para el **Chat 2** usando datos crudos reales (`PromptA.txt`). Verifica la capacidad de limpieza y estructuración JSON del resumen.

---

## 📁 Estructura del Repositorio

```text
.
├── SERVICES/
│   ├── ADM_MODULAR/        # Seguridad y Ruteo
│   ├── gm_general_chat/    # Chat Médico General
│   ├── gm_ch_summary/      # NUEVO: Resúmenes de Historias Clínicas
│   └── medical_auditor/    # Auditoría Clínica (Optimizado)
├── docker-compose.yml      # Orquestador Maestro
├── test_flow.sh            # Script de prueba Integral
└── test_summary.sh         # Script de prueba de Resumen
```

---

## 🔒 Notas de Seguridad

- **API Keys**: Los archivos `.env` están ignorados por Git. Nunca subas tus llaves al repositorio.
- **Producción**: Para despliegue, asegúrate de configurar los volúmenes de persistencia para la base de datos SQLite del Gateway si es necesario.

---
*Desarrollado para la evolución del ecosistema profesional de GoMedisys.*
