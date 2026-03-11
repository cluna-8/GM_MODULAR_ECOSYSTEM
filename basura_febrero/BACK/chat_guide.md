# 🩺 Guía de Uso - Chat Médico Healthcare

## 📋 Información General

El Chat Médico Healthcare es un sistema inteligente que combina inteligencia artificial con bases de datos médicas especializadas para proporcionar información médica precisa y actualizada.

### Características Principales
- **5 Herramientas Médicas** especializadas
- **5 Modos de Prompt** para diferentes especialidades
- **Detección automática de idioma** (Español/Inglés)
- **Extracción inteligente** de términos médicos
- **Respuestas profesionales** con disclaimers médicos

---

## 🔑 Autenticación y Acceso

### Tokens de Acceso

Para usar el chat médico necesitas un **token USER**:

```
🔹 Token Demo: hcg_gomedisys_user_demo_8025A4507BCBD1D1
```

### Endpoint Principal

```
🌐 https://api.healthcare.com:8000/medical/chat
```

### Estructura de Request

```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {TOKEN_USER}" \
-d '{
  "message": "Tu pregunta médica aquí",
  "session": "mi-sesion-123",
  "tools": "fda",
  "prompt_mode": "medical", 
  "language": "es"
}'
```

---

## 🎯 Modos de Prompt Disponibles

### 1. **MEDICAL** (Por defecto)
**Uso**: Consultas médicas generales  
**Especialidad**: Medicina general con acceso a todas las herramientas  
**Características**:
- Información médica precisa y actualizada
- Tono profesional pero empático
- Disclaimers médicos apropiados
- Estructuración con markdown

**Ejemplo**:
```json
{
  "message": "¿Qué es la diabetes tipo 2?",
  "prompt_mode": "medical"
}
```

### 2. **PEDIATRIC**
**Uso**: Medicina pediátrica (0-18 años)  
**Especialidad**: Bebés, niños y adolescentes  
**Características**:
- Dosificación por edad y peso
- Lenguaje para padres/cuidadores
- Rangos normales por edad
- Derivación a pediatras

**Ejemplo**:
```json
{
  "message": "Dosis de paracetamol para niño de 5 años",
  "prompt_mode": "pediatric"
}
```

### 3. **EMERGENCY**
**Uso**: Situaciones de urgencia médica  
**Especialidad**: Medicina de urgencias  
**Características**:
- Respuestas BREVES y DIRECTAS
- Identificación de signos de alarma
- Recomendaciones de atención inmediata
- Lenguaje urgente pero controlado

**Ejemplo**:
```json
{
  "message": "Dolor de pecho intenso y dificultad para respirar",
  "prompt_mode": "emergency"
}
```

### 4. **PHARMACY**
**Uso**: Información farmacológica detallada  
**Especialidad**: Medicamentos y farmacología  
**Características**:
- Información detallada de medicamentos
- Interacciones medicamentosas
- Dosificación específica
- Efectos secundarios

**Ejemplo**:
```json
{
  "message": "Interacciones entre aspirina y warfarina",
  "prompt_mode": "pharmacy"
}
```

### 5. **GENERAL**
**Uso**: Salud general y bienestar  
**Especialidad**: Prevención y hábitos saludables  
**Características**:
- Tono amigable y accesible
- Lenguaje sencillo
- Enfoque en prevención
- Consejos prácticos

**Ejemplo**:
```json
{
  "message": "Consejos para una dieta saludable",
  "prompt_mode": "general"
}
```

---

## 🛠️ Herramientas Médicas Especializadas

### 1. **FDA** - Base de Datos de Medicamentos
**Qué hace**: Busca información oficial de medicamentos aprobados por la FDA  
**Información incluye**:
- Nombre genérico y comercial
- Fabricante y NDC numbers
- Efectos secundarios
- Contraindicaciones
- Dosificación aprobada
- Fecha de aprobación

**Ejemplo de uso**:
```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "¿Qué información hay sobre la aspirina?",
  "tools": "fda",
  "prompt_mode": "pharmacy"
}'
```

**Respuesta esperada**: Información completa de FDA sobre aspirina con detalles oficiales.

### 2. **PUBMED** - Literatura Científica
**Qué hace**: Busca artículos científicos revisados por pares  
**Información incluye**:
- Títulos de estudios recientes
- Autores principales
- Revistas científicas
- PMIDs para referencia
- Fechas de publicación
- Nivel de evidencia

**Ejemplo de uso**:
```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "¿Qué estudios hay sobre hipertensión arterial?",
  "tools": "pubmed",
  "prompt_mode": "medical"
}'
```

**Nota**: PubMed requiere términos en inglés, el sistema traduce automáticamente.

### 3. **ICD-10** - Códigos Diagnósticos
**Qué hace**: Busca códigos ICD-10 para diagnósticos médicos  
**Información incluye**:
- Códigos específicos (ej: G44.81)
- Descripciones detalladas
- Categorías diagnósticas
- Uso para documentación médica

**Ejemplo de uso**:
```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "¿Qué códigos ICD-10 hay para dolor de cabeza?",
  "tools": "icd10",
  "prompt_mode": "medical"
}'
```

**Respuesta esperada**: Lista directa de códigos ICD-10 sin procesamiento adicional del LLM.

### 4. **SCRAPING** - Sitios Médicos Confiables
**Qué hace**: Extrae información de sitios médicos especializados  
**Información incluye**:
- Contenido de Mayo Clinic, WebMD, etc.
- Análisis de confiabilidad de fuentes
- Enlaces a recursos oficiales
- Resumen estructurado

**Ejemplo de uso**:
```bash
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "Información de https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444",
  "tools": "scraping",
  "prompt_mode": "medical"
}'
```

---

## 🎯 Flujo de Funcionamiento

### 1. **Chat Normal** (Sin herramientas)
```
Usuario pregunta → LLM responde con conocimiento base
```

**Ejemplo**:
```json
{
  "message": "¿Qué es la diabetes?",
  "prompt_mode": "medical"
}
```

### 2. **Chat con Herramienta**
```
Usuario pregunta → Extracción término médico → Búsqueda en herramienta → LLM formatea respuesta
```

**Ejemplo**:
```json
{
  "message": "¿Qué estudios hay sobre diabetes tipo 2?",
  "tools": "pubmed",
  "prompt_mode": "medical"
}
```

**Proceso interno**:
1. Extrae "type 2 diabetes" (traducido al inglés)
2. Busca en PubMed
3. Obtiene artículos científicos
4. LLM formatea en español con prompt médico

---

## 🌐 Idiomas y Detección Automática

### Idiomas Soportados
- **Español** (es) - Por defecto para usuarios hispanos
- **Inglés** (en) - Para usuarios angloparlantes
- **Auto** - Detección automática

### Detección Automática
El sistema detecta automáticamente el idioma basado en:
- Palabras indicadoras específicas
- Caracteres especiales (ñ, á, é, í, ó, ú, ü, ¿, ¡)
- Estructura de la pregunta

**Ejemplos**:
```json
// Detectado como Español
{"message": "¿Qué es la aspirina?"}

// Detectado como Inglés  
{"message": "What is aspirin?"}

// Forzar idioma específico
{"message": "What is aspirin?", "language": "es"}
```

---

## ⚡ Endpoints Directos de Herramientas

Para casos donde necesites acceso directo a herramientas sin el chat:

### FDA Directo
```bash
curl -X POST "http://localhost:8000/medical/tools/fda" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {TOKEN_USER}" \
-d '{
  "query": "aspirin",
  "max_results": 3,
  "format_response": true
}'
```

### PubMed Directo
```bash
curl -X POST "http://localhost:8000/medical/tools/pubmed" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {TOKEN_USER}" \
-d '{
  "query": "type 2 diabetes",
  "max_results": 5,
  "format_response": false
}'
```

### ICD-10 Directo
```bash
curl -X POST "http://localhost:8000/medical/tools/icd10" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer {TOKEN_USER}" \
-d '{
  "query": "headache",
  "max_results": 5
}'
```

---

## 🔄 Gestión de Sesiones

### Crear Sesión
```json
{
  "message": "Primera pregunta médica",
  "session": "consulta-paciente-123",
  "prompt_mode": "medical"
}
```

### Continuar Sesión
```json
{
  "message": "Pregunta de seguimiento",
  "session": "consulta-paciente-123",
  "prompt_mode": "medical"
}
```

### Ver Mis Sesiones
```bash
curl -X GET "http://localhost:8000/user/my-sessions" \
-H "Authorization: Bearer {TOKEN_USER}"
```

---

## 📊 Casos de Uso Prácticos

### 1. **Consulta General**
```bash
# Pregunta médica básica
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "¿Cuáles son los síntomas de la hipertensión?",
  "session": "consulta-general-001",
  "prompt_mode": "medical"
}'
```

### 2. **Investigación de Medicamento**
```bash
# Información completa de medicamento
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "Efectos secundarios del ibuprofeno",
  "session": "consulta-farmaco-001",
  "tools": "fda",
  "prompt_mode": "pharmacy"
}'
```

### 3. **Consulta Pediátrica**
```bash
# Consulta especializada en niños
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "Fiebre en niño de 3 años, ¿cuándo preocuparse?",
  "session": "consulta-pediatrica-001",
  "prompt_mode": "pediatric"
}'
```

### 4. **Urgencia Médica**
```bash
# Situación de emergencia
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "Dolor de pecho intenso y dificultad para respirar",
  "session": "urgencia-001",
  "prompt_mode": "emergency"
}'
```

### 5. **Investigación Científica**
```bash
# Búsqueda de literatura médica
curl -X POST "http://localhost:8000/medical/chat" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer hcg_gomedisys_user_demo_8025A4507BCBD1D1" \
-d '{
  "message": "Últimos estudios sobre tratamiento de la diabetes",
  "session": "investigacion-001",
  "tools": "pubmed",
  "prompt_mode": "medical"
}'
```

---

## 🚨 Disclaimers y Consideraciones Médicas

### ⚠️ Importante
- Esta información es **solo para fines educativos**
- **NO reemplaza** la consulta con profesionales de la salud
- Siempre consulte con su médico para decisiones médicas específicas
- En emergencias, contacte servicios de urgencia inmediatamente

### 🏥 Cuándo Buscar Atención Médica
- Síntomas graves o que empeoran
- Reacciones adversas a medicamentos
- Dudas sobre dosificación
- Condiciones crónicas sin control
- Cualquier emergencia médica

---

## 📞 WebSocket (Chat en Tiempo Real)

Para aplicaciones que requieren chat en tiempo real:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat/hcg_gomedisys_user_demo_8025A4507BCBD1D1');

ws.onopen = function() {
    // Enviar mensaje
    ws.send(JSON.stringify({
        message: "¿Qué es la aspirina?",
        tools: "fda",
        prompt_mode: "pharmacy"
    }));
};

ws.onmessage = function(event) {
    const response = JSON.parse(event.data);
    console.log('Respuesta:', response);
};
```

---

## 🔍 Ejemplos de Respuestas

### Respuesta con FDA
```json
{
  "status": "success",
  "data": {
    "response": "La **Aspirina** es un medicamento ampliamente conocido... [información detallada de FDA]"
  },
  "tool_used": "fda",
  "language_detected": "es",
  "prompt_mode_used": "pharmacy"
}
```

### Respuesta con PubMed
```json
{
  "status": "success", 
  "data": {
    "response": "### Estudios sobre Diabetes Tipo 2\n\n#### 1. **Type 2 diabetes: a multifaceted disease**\n- *Autores:* Pearson ER..."
  },
  "tool_used": "pubmed",
  "language_detected": "es"
}
```

### Respuesta con ICD-10
```json
{
  "status": "success",
  "data": {
    "response": "**ICD-10 codes for 'headache':**\n• **G44.81**: Hypnic headache\n• **G44.86**: Cervicogenic headache..."
  },
  "tool_used": "icd10"
}
```

---

## 🔧 Resolución de Problemas

### Errores Comunes

**401 - Token requerido**
```json
{"detail": "User token required for this endpoint"}
```
**Solución**: Usar token con rol USER, no ADMIN

**503 - API médica no disponible**
```json
{"detail": "Medical API unavailable"}
```
**Solución**: Verificar que el servicio médico esté funcionando

**400 - Herramienta inválida**
```json
{"detail": "Invalid tool. Available: ['fda', 'pubmed', 'icd10', 'scraping']"}
```
**Solución**: Usar nombres de herramientas válidos

---

## 📈 Mejores Prácticas

### 1. **Optimización de Consultas**
- Ser específico en las preguntas
- Usar términos médicos precisos
- Especificar el contexto cuando sea necesario

### 2. **Uso de Herramientas**
- **FDA**: Para información oficial de medicamentos
- **PubMed**: Para evidencia científica
- **ICD-10**: Para códigos diagnósticos
- **Scraping**: Para información complementaria

### 3. **Gestión de Sesiones**
- Usar sesiones descriptivas: `"consulta-paciente-001"`
- Mantener contexto en la misma sesión
- Limpiar sesiones antiguas regularmente

### 4. **Idiomas**
- Dejar en "auto" para detección automática
- Especificar idioma solo cuando sea necesario
- Las herramientas buscan en inglés automáticamente

---

*Guía actualizada: Julio 2025 | Versión Chat Médico: 2.0.0*