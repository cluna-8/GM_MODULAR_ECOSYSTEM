# Documentación Técnica: Restricción Médica e Integración HIS
**Versión:** 2.1.0  
**Fecha:** 20 de Enero, 2026  
**Módulo:** `gm_general_chat` (Especialista Clínico General)

## 1. Visión General
Se ha implementado una capa de seguridad y personalización avanzada en el motor de chat para asegurar que el sistema actúe como un asistente médico puro y aproveche la información del paciente proveniente del Sistema de Información Hospitalaria (HIS).

## 2. Restricción Médica Estricta
El sistema ahora garantiza que el 100% de las interacciones se mantengan dentro del dominio de la salud.

### Mecanismo de Control
En el archivo `prompts.yml`, cada modo de prompt incluye una directiva de **RESTRICCIÓN CRÍTICA**.
- **Comportamiento**: Si el usuario pregunta sobre temas ajenos (deportes, clima, curiosidades), el LLM detiene la generación y responde con un mensaje predefinido: 
  > *"Lo siento, soy un asistente especializado de GoMedisys y solo puedo responder consultas relacionadas con la salud y medicina."*
- **Beneficio**: Evita el uso del sistema para fines no clínicos y reduce el riesgo de alucinaciones fuera de dominio.

## 3. Integración de Contexto HIS
El endpoint `/chat` ahora procesa el campo opcional `context`, diseñado para recibir un objeto clave-valor con datos del paciente.

### Flujo de Datos
1. **Recepción**: El API Gateway (o cliente directo) envía datos como `{"edad": "45", "antecedentes": "diabetes"}`.
2. **Procesamiento (`main.py`)**: El sistema extrae estos datos y los formatea en un bloque estructurado titulado `📋 INFORMACIÓN DEL PACIENTE (HIS)`.
3. **Inyección**: Este bloque se antepone a la consulta del usuario (`❓ CONSULTA MÉDICA`) antes de enviarlo al LLM.
4. **Respuesta Personalizada**: El LLM utiliza este contexto para validar contraindicaciones o priorizar recomendaciones (ej. "Dado que usted tiene X diagnóstico, le sugiero Y...").

## 4. Estructura de Prompts (`prompts.yml`)
El archivo de configuración se ha movido a una arquitectura modular:
- **Modes**: `medical`, `pediatric`, `emergency`, `pharmacy`, `general`.
- **Fields**: 
  - `system_prompt`: Instrucciones de rol y restricciones.
  - `temperature`: Ajustado para precisión clínica (0.0 - 0.2).
  - `max_tokens`: Límites de respuesta según el caso de uso.

## 5. Verificación
Se incluye el script `verify_medical.sh` en la carpeta de herramientas para realizar pruebas de regresión:
- Prueba 1: Intento de consulta no médica (Debe fallar/bloquear).
- Prueba 2: Consulta médica con contexto (Debe personalizar la respuesta).
- Prueba 3: Consulta en modo bienestar (Debe restringir a temas de salud).

---
*Propiedad de GoMedisys AI Team.*
