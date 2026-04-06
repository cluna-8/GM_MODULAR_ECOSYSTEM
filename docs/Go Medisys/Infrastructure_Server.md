---
tipo: infraestructura
estado: activo
relacionado: [[Index]]
---

# 🖥️ Infrastructure_Server — Servidor de Producción
#infraestructura/produccion #estado/activo

> **Rol**: Documentación de los recursos computacionales y especificaciones del servidor de producción (`vmEast2Aivini`) que aloja los agentes y microservicios del ecosistema.

## 📌 Especificaciones del Servidor

**Hostname**: `vmEast2Aivini`
**Usuario**: `sysadmins`

### Informe de Recursos (Snapshot)

| Recurso | Capacidad Total | Uso Actual | Disponible | Porcentaje de Uso |
| :--- | :--- | :--- | :--- | :--- |
| **Memoria RAM** | 7.8 GiB | 2.0 GiB | 5.8 GiB (Available) | ~25.6% |
| **Almacenamiento (Disco `/`)** | 495 GB | 22 GB | 474 GB | 5% |
| **Swap** | 0 B | 0 B | 0 B | 0% |
| **GPU** | N/A | N/A | N/A | Sin GPU NVIDIA detectada |

---

## 🔬 Análisis de Capacidad y Restricciones

1. **Memoria RAM Limitada (8GB Clase)**: Con 7.8 GiB totales y 2 GiB en uso actualmente, el sistema tiene holgura, pero cargas pesadas simultáneas de múltiples contenedores de agentes podrían causar asfixia si exceden los ~5.8 GiB disponibles. 
   - **Recomendación**: Mantener un monitoreo estricto sobre el uso de memoria de Redis y FastAPI. Es crucial asegurar que las ventanas de contexto de la memoria del LLM (Sliding Window truncations) se gestionen agresivamente para evitar picos.

2. **Ausencia de Swap**: Al no haber archivo Swap configurado, si el sistema agota la memoria RAM física en un pico de carga, el OOM (Out Of Memory) Killer intervendrá destruyendo procesos inmediatamente (muy probablemente contenedores de Docker en ejecución).
   - **Recomendación**: Evaluar la activación prudente de Swap (ej. 2GB) para prevenir crasheos severos bajo picos inesperados, aunque idealmente las aplicaciones deben optimizarse para no depender de él.

3. **Sin GPU Aceleradora Local**: Como no hay GPU NVIDIA, el procesamiento LLM pesado (si fuera local) recaería completamente en la CPU o dependerá enteramente de APIs externas (como OpenAI).
   - **Estado Actual**: Alineado con el diseño actual, ya que el sistema utiliza la API de OpenAI (GPT-4o-mini / GPT-4o) para el razonamiento pesado en lugar de cargar modelos locales. El vector embedding (`sentence-transformers` en `Medical_Auditor`) correrá por CPU; esta tarea suele ser manejable, pero amerita monitoreo bajo alta concurrencia.

4. **Almacenamiento Amplio**: Los 495 GB de disco con solo un 5% usado garantizan espacio de sobra para logs extensos (`audit_log.jsonl`), volcados de bases de datos de sesión persistidas, y expansión de contenedores/repositorios sin fricción a medio/largo plazo.

---

## 🔗 Notas Relacionadas
- [[Index]] — Volver al mapa de contenido principal
- [[Medical_Auditor]] — Proceso dependiente de embebidos (CPU based sin GPU).
- [[ADM_Gateway]] — Maneja logs y SQLite DB local.
