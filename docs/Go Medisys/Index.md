---
tipo: MOC
estado: activo
---

# 🗺️ Map of Content: GoMedisys Ecosystem
#tipo/MOC #estado/activo

Bienvenido al vault del **GoMedisys Modular Ecosystem**. Documenta la arquitectura de microservicios clínicos desplegados desde `SERVICES/docker-compose.yml`.

## 🏁 NÚCLEO DEL ECOSISTEMA
| Módulo | Puerto | Rol |
|---|---|---|
| [[ADM_Gateway]] | `:8000` | Portero Central — Auth, Routing, Billing |
| [[Medical_Auditor]] | `:8001` | Seguridad Clínica — Pre/Post Audit |

## 💬 MÓDULOS CLÍNICOS
| Módulo | Puerto | Rol |
|---|---|---|
| [[General_Chat]] | `:7005` | Agente de Interacción Clínica |
| [[Clinical_Summary]] | `:7006` | Motor de Extracción de Historias Clínicas |
| [[Voice_Module]] | `:7003` | 🟡 Transcripción Clínica Progresiva por Chunks |

## 🛠️ MÓDULOS PENDIENTES
| Módulo | Puerto | Estado |
|---|---|---|
| [[Diagnosis_Module]] | `:7004` | 🔴 Pendiente — Agente de Soporte Diagnóstico |

## 📐 ARQUITECTURA GENERAL

```mermaid
graph TD
    User((Usuario / HIS)) -->|"Bearer hcg_xxx"| ADM["ADM Gateway :8000"]

    ADM -->|"/medical/chat"| GC["General Chat :7005"]
    ADM -->|"/medical/summary"| CS["Clinical Summary :7006"]
    ADM -->|"/medical/voice/*"| VM["Voice Module :7003"]
    ADM -->|"chat4 🔴"| DM["Diagnosis :7004"]

    GC <-->|Pre & Post Audit| MA["Medical Auditor :8001"]
    CS <-->|Pre & Post Audit| MA
    VM -->|"validate-safety"| MA

    MA <--> Redis[(redis-general db=0\nSemantic Cache)]
    VM <--> RedisV[(redis-general db=1\nVoice Sessions TTL 2h)]
    ADM <--> SQL[(SQLite\nhealthcare_gateway.db)]
```

## 🚀 Levantar el ecosistema

```bash
docker network create gomedisys-net   # una sola vez
cd SERVICES/
docker compose up -d --build
```

## 🔗 FLUJO DE UNA PETICIÓN CLÍNICA

```mermaid
sequenceDiagram
    participant U as Cliente/HIS
    participant ADM as ADM Gateway :8000
    participant SVC as Módulo Clínico
    participant MA as Medical Auditor :8001
    participant LLM as OpenAI GPT-4o-mini

    U->>ADM: POST /medical/chat + Bearer hcg_xxx
    ADM->>ADM: Validar token (SQLite lookup)
    ADM->>SVC: Proxy request
    SVC->>MA: Pre-Audit (intent check)
    MA-->>SVC: APPROVED / REJECTED
    SVC->>LLM: Generar respuesta
    LLM-->>SVC: Respuesta raw
    SVC->>MA: Post-Audit (safety check)
    MA-->>SVC: APPROVED / WARNING
    SVC-->>ADM: Respuesta + token usage
    ADM->>ADM: log api_requests, update billing
    ADM-->>U: Respuesta final
```

> [!NOTE]
> Cada módulo tiene su propia nota. Usa los links `[[...]]` para navegar.
