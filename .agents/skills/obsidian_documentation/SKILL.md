---
name: obsidian_documentation
description: Skill para crear documentación interconectada compatible con Obsidian. Genera archivos .md con YAML frontmatter, wikilinks [[...]], callouts, bloques Mermaid y estructura de vault (MOC + notas atómicas). Diseñado para documentar el ecosistema GM_MODULAR_ECOSYSTEM.
---

# Obsidian Documentation Skill — GM_MODULAR_ECOSYSTEM

## Contexto del Proyecto
Este skill documenta el ecosistema de microservicios clínicos de **GoMedisys**. Los módulos a documentar viven en `SERVICES/` y la documentación generada va en `docs/obsidian/`.

## Vault Structure (Regla de Oro)
```
docs/obsidian/
  Index.md              ← MOC: punto de entrada obligatorio
  ADM_Gateway.md        ← Gateway central (puerto 7000) — activo
  Medical_Auditor.md    ← Auditor clínico (puerto 7002) — activo
  General_Chat.md       ← Chat clínico (puerto 7001) — activo
  Clinical_Summary.md   ← Resumen HC (puerto 7006) — activo
  Voice_Module.md       ← Transcripción audio (puerto 7003) — 🔴 PENDIENTE
  Diagnosis_Module.md   ← Diagnóstico IA (puerto 7004) — 🔴 PENDIENTE
```

## Reglas de Formato

### 1. YAML Frontmatter (obligatorio en CADA nota)
```yaml
---
tipo: módulo-core | módulo-clínico | concepto | referencia
estado: activo | pendiente | deprecado
puerto: 7000
stack: FastAPI, Redis, OpenAI
relacionado: [[Nota1]], [[Nota2]]
---
```

### 2. Internal Links — SIEMPRE wikilinks
- ✅ Correcto: `[[ADM_Gateway]]`
- ❌ Incorrecto: `[ADM Gateway](ADM_Gateway.md)`

### 3. Tags — Jerarquía con `/`
```
#módulo/core   #módulo/clínico   #estado/activo   #estado/pendiente
#seguridad/RBAC   #llm/openai   #llm/llamaindex
```

### 4. Módulos Pendientes — Siempre con callout
```markdown
> [!WARNING]
> Este módulo está registrado en el [[ADM_Gateway]] como `chatN` pero su implementación está **pendiente**.
```

### 5. Tipos de Diagramas Mermaid
- `graph LR` → Integración del módulo en el ecosistema
- `sequenceDiagram` → Flujos de petición HTTP entre servicios
- `flowchart TD` → Pipeline interno de pasos de un servicio

### 6. Callouts de Obsidian
```markdown
> [!NOTE] Información de contexto
> [!WARNING] Módulo pendiente o riesgo operacional
> [!TIP] Buenas prácticas o configuración recomendada
> [!IMPORTANT] Datos críticos de seguridad o producción
```

### 7. Comentarios Internos (visibles solo en edición)
```
%% TODO: pendiente a implementar %%
%% DISEÑO: decisión arquitectural a revisar %%
```

### 8. Sección Final Obligatoria
Cada nota termina con:
```markdown
---
## 🔗 Notas Relacionadas
- [[ModuloA]] — breve descripción del link
- [[ModuloB]] — breve descripción del link
```

## Workflow Completo para Documentar un Módulo

1. **Leer código fuente** → `SERVICES/<módulo>/main.py`, `TECHNICAL_REFERENCE.md`, `SYSTEM_LOGIC_ARCHITECTURE.md`
2. **YAML frontmatter** con `tipo`, `estado`, `puerto`, `stack`, `relacionado`
3. **Título + apertura** → blockquote `>` describiendo el rol del módulo en 1-2 frases
4. **Diagrama de integración** → `graph LR` mostrando cómo se conecta al ecosistema
5. **Secciones numeradas** de lógica interna (procesar, validar, almacenar)
6. **Tabla de Stack Tecnológico** (Tecnología | Uso)
7. **Sección de Notas Relacionadas** con `[[wikilinks]]`

## Archivos de Referencia del Proyecto
- `SERVICES/<módulo>/TECHNICAL_REFERENCE.md` → detalles técnicos
- `SERVICES/<módulo>/SYSTEM_LOGIC_ARCHITECTURE.md` → lógica interna
- `SERVICES/<módulo>/OPERATIONAL_INTEGRATION.md` → integración operacional
- `AI_CONTEXT.md` → contexto general del ecosistema
