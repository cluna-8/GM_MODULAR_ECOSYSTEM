# GoMedisys — Obsidian Vault Rules

## Identidad y Rol
Asistente técnico del ecosistema de microservicios clínicos de GoMedisys.

## Puertos actuales (v0.1.0-dev)
```
ADM Gateway     :8000   SERVICES/ADM_MODULAR/
Medical Auditor :8001   SERVICES/medical_auditor/
General Chat    :7005   SERVICES/gm_general_chat/
Clinical Summary:7006   SERVICES/gm_ch_summary/
Voice Module    :7003   SERVICES/gm_voice/
Redis           :6379   db=0 chat/auditor | db=1 voice
```

## Estructura del Vault
```
Index.md              ← Punto de entrada / MOC
ADM_Gateway.md        ← Gateway central (puerto 8000)
Medical_Auditor.md    ← Auditor clínico (puerto 8001)
General_Chat.md       ← Chat clínico (puerto 7005)
Clinical_Summary.md   ← Resumen HC (puerto 7006)
Voice_Module.md       ← Transcripción clínica (puerto 7003) 🟡
Diagnosis_Module.md   ← 🔴 PENDIENTE (puerto 7004)
Infrastructure_Server.md ← Specs servidor producción
```

## Convenciones de Escritura
- Usar SIEMPRE `[[wikilinks]]` para referencias internas
- YAML frontmatter obligatorio: `tipo`, `estado`, `puerto`, `relacionado`
- Tags con jerarquía: `#módulo/core`, `#estado/activo`, `#estado/en-desarrollo`
- Diagramas Mermaid para arquitectura y flujos
- Callouts Obsidian: `> [!WARNING]`, `> [!NOTE]`, `> [!TIP]`

## Estado de módulos
- ✅ activo = en producción, testeado
- 🟡 en-desarrollo = implementado, pendiente pruebas con usuarios reales
- 🔴 pendiente = no implementado
