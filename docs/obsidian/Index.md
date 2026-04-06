# 🗺️ Map of Content: GM_MODULAR_ECOSYSTEM
#tipo/MOC #estado/activo

Bienvenido al vault del **GM Modular Ecosystem**. Este vault documenta la arquitectura de microservicios clínicos de GoMedisys.

## 🏁 NÚCLEO DEL ECOSISTEMA
| Módulo | Rol |
|---|---|
| [[ADM_Gateway]] | Portero Central — Autenticación, Routing y Contabilidad de Tokens |
| [[Medical_Auditor]] | Cerebro de Seguridad — Prevención de Errores Clínicos |

## 💬 MÓDULOS CLÍNICOS
| Módulo | Rol |
|---|---|
| [[General_Chat]] | Agente de Interacción Clínica con Pipeline de 5 Pasos |
| [[Clinical_Summary]] | Motor de Extracción Estructurada de Historias Clínicas |

## 🚧 MÓDULOS EN DESARROLLO
| Módulo | Estado |
|---|---|
| [[Voice_Module]] | 🟡 En Desarrollo — Transcripción Clínica Progresiva por Chunks |

## 🛠️ MÓDULOS PENDIENTES
| Módulo | Estado |
|---|---|
| [[Diagnosis_Module]] | 🔴 Pendiente — Agente de Soporte Diagnóstico |

## 📐 ARQUITECTURA GENERAL

```mermaid
graph TD
    User((Usuario / HIS)) -->|API Key hcg_| ADM["ADM Gateway\n(Portero / Proxy)"]

    ADM -->|chat1| GC["General Chat\ngm-general-chat"]
    ADM -->|chat2| CS["Clinical Summary\ngm-ch-summary"]
    ADM -->|chat3 🟡| VM["Voice Module\ngm-voice"]
    ADM -->|chat4 🔴| DM["Diagnosis Agent\ngm-diagnosis"]

    GC <-->|Pre & Post Audit| MA["Medical Auditor"]
    CS <-->|Pre & Post Audit| MA

    MA <-->|Vector Search| Redis[(Redis\nSemantic Cache)]
    ADM <-->|Logging & Billing| SQL[(SQLite\nmodular_gateway.db)]
```

## 🔗 FLUJO DE UNA PETICIÓN COMPLETA

```mermaid
sequenceDiagram
    participant U as Usuario/HIS
    participant ADM as ADM Gateway
    participant GC as General Chat
    participant MA as Medical Auditor
    participant LLM as OpenAI GPT-4o-mini

    U->>ADM: POST /proxy/chat1 + Bearer hcg_xxx
    ADM->>ADM: Validar API Key (RBAC)
    ADM->>GC: Proxy de la petición
    GC->>MA: Pre-Audit (Intent Check)
    MA-->>GC: APPROVED / REJECTED
    GC->>LLM: Generar respuesta (si APPROVED)
    LLM-->>GC: Respuesta Raw
    GC->>MA: Post-Audit (Safety Check)
    MA-->>GC: APPROVED / WARNING
    GC-->>ADM: Respuesta + Token Usage
    ADM->>ADM: Registrar consumo en DB
    ADM-->>U: Respuesta Final
```

> [!NOTE]
> Cada módulo tiene su propia nota de documentación detallada. Usa los links `[[...]]` para navegar entre ellos.
