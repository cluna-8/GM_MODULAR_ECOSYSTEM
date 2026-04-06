# 🏥 GM_ADM_MODULAR - Gateway de Seguridad y Control

Este módulo es la "Aduana" de toda la plataforma GoMedisys. Centraliza la seguridad y la contabilidad de uso de todos los chats.

## 💼 Resumen Ejecutivo
El Gateway protege la inversión en IA de la empresa. Su función es:
*   **Seguridad**: Garantizar que solo usuarios autorizados accedan a los modelos de lenguaje.
*   **Gestión de Clientes**: Permitir la creación o revocación instantánea de acceso (Tokens).
*   **Contabilidad (Tokens)**: Registrar el consumo exacto de cada cliente para auditoría de costos y facturación.
*   **Orquestación**: Dirigir las peticiones al chat correspondiente (Médico, Diagnóstico, etc.) de forma invisible para el usuario.

---

## 🛠️ Especificación Técnica
*   **Core**: FastAPI (Python 3.11).
*   **Base de Datos**: SQLite (compatible con PostgreSQL) para persistencia de tokens y logs.
*   **Seguridad**: 
    *   `auth.py`: Implementa el estándar **HTTP Bearer**. No guarda contraseñas en texto plano (usa Bcrypt).
    *   Genera llaves con prefijo corporativo `hcg_` para fácil identificación.
*   **Proxy Modular**: Utiliza `httpx` para re-enviar peticiones a los backends de chat sin perder el contexto ni la velocidad.

---

## 🔍 Guía de Auditoría
Este módulo cuenta con un script de auditoría automatizado para verificar su integridad.

**Cómo probar este módulo:**
1.  Asegúrate de que el contenedor esté corriendo: `docker-compose up -d`
2.  Ejecuta el auditor: `bash auditor_pruebas.sh`

**Resultados esperados:**
*   **Health Check**: Debe responder `ONLINE`.
*   **Blindaje**: Una llamada sin token debe devolver `401/405`.
*   **Validación**: Una llamada con `hcg_maestro_123` debe ser aceptada (devolver `502` si el chat está apagado o `200` si está encendido).
*   **Libro Contable**: El auditor mostrará el último registro guardado en la Base de Datos.
