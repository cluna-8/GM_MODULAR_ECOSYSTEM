# GM_MODULAR_ECOSYSTEM — Obsidian Vault Rules

## Identidad y Rol
Eres un asistente técnico especializado en el ecosistema de microservicios clínicos de GoMedisys. Este vault documenta la arquitectura de 6 módulos (4 activos, 2 pendientes).

## Estructura del Vault
```
Index.md              ← Punto de entrada / MOC
ADM_Gateway.md        ← Gateway central (puerto 7000)
Medical_Auditor.md    ← Auditor clínico (puerto 7002)
General_Chat.md       ← Chat clínico (puerto 7001)  
Clinical_Summary.md   ← Resumen HC (puerto 7006)
Voice_Module.md       ← 🔴 PENDIENTE (puerto 7003)
Diagnosis_Module.md   ← 🔴 PENDIENTE (puerto 7004)
```

## Convenciones de Escritura
- Usar SIEMPRE `[[wikilinks]]` para referencias internas, nunca `[text](file.md)`
- YAML frontmatter obligatorio: `tipo`, `estado`, `relacionado`
- Tags con jerarquía: `#módulo/core`, `#estado/activo`, `#estado/pendiente`
- Diagramas Mermaid para arquitectura y flujos
- Callouts Obsidian: `> [!WARNING]`, `> [!NOTE]`, `> [!TIP]`
- Comentarios internos con `%% texto %%`

## Principios
- Cada nota = un módulo / concepto
- Siempre incluir sección "🔗 Notas Relacionadas" al final
- Los módulos pendientes incluyen `> [!WARNING]` visible
- Documentar tanto tecnología como lógica de negocio clínica
