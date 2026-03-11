import streamlit as st
import openai
from bs4 import BeautifulSoup
import chardet
import re
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class GomedisysClinicSummarizer:
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)
    
    def clean_html_content(self, html_content):
        """Limpia HTML y extrae texto"""
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ')
        
        # Correcciones de encoding básicas
        text = text.replace('ÃƒÂ¡', 'á').replace('ÃƒÂ©', 'é').replace('ÃƒÂ­', 'í')
        text = text.replace('ÃƒÂ³', 'ó').replace('ÃƒÂº', 'ú').replace('ÃƒÂ±', 'ñ')
        
        # Normalizar espacios
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def extract_key_medical_info(self, medical_text):
        """Extrae información médica clave para mostrar en el procesamiento"""
        
        key_info = {
            'microorganismos': [],
            'resistencias': [],
            'antibioticos': [],
            'fechas_importantes': []
        }
        
        # Buscar microorganismos
        microorganisms = re.findall(r'(E\.\s*coli|Klebsiella\s+pneumoniae|Pseudomonas|Enterococcus)', medical_text, re.IGNORECASE)
        key_info['microorganismos'] = list(set(microorganisms))
        
        # Buscar resistencias
        if 'NDM' in medical_text:
            key_info['resistencias'].append('NDM carbapenemasa')
        if 'BLEE' in medical_text:
            key_info['resistencias'].append('BLEE')
        if 'carbapenemasa' in medical_text.lower():
            key_info['resistencias'].append('Carbapenemasa')
        
        # Buscar antibióticos
        antibiotics = re.findall(r'(meropenem|ertapenem|gentamicina|tigeciclina|ceftazidima|vancomicina|cefalexina)', medical_text, re.IGNORECASE)
        key_info['antibioticos'] = list(set([ab.lower() for ab in antibiotics]))
        
        # Buscar fechas
        dates = re.findall(r'\d{1,2}[-/]\d{1,2}[-/]\d{4}', medical_text)
        key_info['fechas_importantes'] = dates[-3:] if dates else []
        
        return key_info
    
    def generate_ultra_concise_summary(self, medical_text):
        """Genera resumen ultra-conciso usando el prompt original que funcionaba"""
        
        if len(medical_text) > 20000:
            medical_text = medical_text[:20000]
        
        prompt = f"""Eres un médico de urgencias creando un resumen ULTRA-CONCISO para emergencia inmediata.

RESTRICCIÓN ABSOLUTA: MÁXIMO 100 PALABRAS TOTAL.

FORMATO: Párrafo narrativo corrido con secciones marcadas.

ESTRUCTURA:
**SITUACIÓN:** [Diagnóstico, ubicación, soporte] **ESTADO:** [PA, conciencia, lab críticos] **MICROBIOLOGÍA:** [Resistencia crítica] **DECISIONES:** [2-3 urgentes] **Ver historial completo.**

EJEMPLO (55 palabras):
**SITUACIÓN:** M 80a shock séptico urinario UCI con noradrenalina. **ESTADO:** PA 86/57, desorientado, Hb 9.75. **MICROBIOLOGÍA:** K. pneumoniae NDM+ resistente a meropenem actual. **DECISIONES:** Cambio antibiótico urgente, evaluar destete vasopresor. **Ver historial completo.**

INFORMACIÓN MÉDICA:
{medical_text}

Crear resumen ULTRA-CONCISO (máximo 100 palabras):"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": "Eres un médico de urgencias. Creas resúmenes ULTRA-CONCISOS de máximo 100 palabras para urgencias médicas inmediatas. Solo información crítica para decisiones hoy. Formato párrafo narrativo con secciones. Conecta resistencia antimicrobiana con tratamiento actual."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def generate_structured_summary(self, medical_text):
        """Genera resumen estructurado mejorado"""
        
        if len(medical_text) > 20000:
            medical_text = medical_text[:20000]
        
        prompt = f"""Eres un médico especialista creando un resumen ESTRUCTURADO para interconsulta detallada.

REGLAS CRÍTICAS:
- Si el microorganismo es resistente al antibiótico actual, indica "CAMBIO INMEDIATO", nunca "evaluar respuesta"
- Usar información más reciente disponible
- Si un procedimiento ya se realizó según fechas, no sugerir "evaluar necesidad"
- Valores numéricos exactos con unidades

OBJETIVO: 150-250 palabras organizadas para toma de decisiones precisa.

ESTRUCTURA OBLIGATORIA:

**SITUACIÓN CLÍNICA:**
[Diagnóstico principal, días evolución si calculable, ubicación actual, soporte requerido]

**ESTADO ACTUAL:**
[Signos vitales más recientes con valores exactos, estado neurológico, laboratorios relevantes]

**MICROBIOLOGÍA:**
[Organismos identificados, resistencias específicas, impacto DIRECTO en tratamiento actual]

**TRATAMIENTO ACTUAL:**
[Antibióticos actuales, efectividad según resistencias, vasopresores, otros medicamentos]

**DECISIONES CRÍTICAS:**
[Acciones médicas URGENTES basadas en resistencias confirmadas y estado actual]

**CONTEXTO:**
[Antecedentes relevantes, procedimientos YA realizados con fechas]

**DETALLES COMPLETOS:** Ver historial clínico adjunto.

INFORMACIÓN MÉDICA:
{medical_text}

Crear resumen ESTRUCTURADO (150-250 palabras):"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": "Eres un médico especialista. Creas resúmenes ESTRUCTURADOS de 150-250 palabras para interconsulta médica detallada. CRÍTICO: Si microorganismo resistente a antibiótico actual, indica CAMBIO INMEDIATO, nunca 'evaluar respuesta'. Usar información más reciente. Procedimientos ya realizados NO requieren evaluación."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def validate_ultra_concise(self, summary):
        """Validación simple para ultra-conciso"""
        
        issues = []
        word_count = len(summary.split())
        
        if word_count > 120:
            issues.append(f"Extenso: {word_count} palabras")
        elif word_count < 30:
            issues.append(f"Muy breve: {word_count} palabras")
            
        if not re.search(r'\d+/\d+', summary):
            issues.append("Falta presión arterial")
            
        if not any(word in summary.lower() for word in ["decisión", "decisiones"]):
            issues.append("Falta decisiones urgentes")
            
        if not any(word in summary.lower() for word in ["historial", "completo", "ver"]):
            issues.append("Falta referencia historial")
        
        return {
            'is_optimal': len(issues) == 0,
            'word_count': word_count,
            'issues': issues,
            'is_good_length': 40 <= word_count <= 100
        }
    
    def validate_structured(self, summary):
        """Validación para resumen estructurado"""
        
        issues = []
        word_count = len(summary.split())
        
        if word_count > 300:
            issues.append(f"Extenso: {word_count} palabras")
        elif word_count < 120:
            issues.append(f"Muy breve: {word_count} palabras")
            
        critical_sections = ["SITUACIÓN", "ESTADO", "DECISIONES"]
        missing_sections = [section for section in critical_sections if section not in summary]
        if missing_sections:
            issues.append(f"Falta secciones: {', '.join(missing_sections)}")
            
        if not re.search(r'\d+/\d+', summary):
            issues.append("Falta presión arterial")
            
        # Verificar errores médicos críticos
        if "evaluar respuesta a meropenem" in summary.lower() and "resistente" in summary.lower():
            issues.append("ERROR MÉDICO: No evaluar respuesta a antibiótico resistente")
            
        if "evaluar necesidad de nefrostomía" in summary.lower() and "28/06" in summary:
            issues.append("ERROR: Nefrostomía ya realizada")
        
        return {
            'is_complete': len(issues) == 0,
            'word_count': word_count,
            'issues': issues,
            'is_good_length': 150 <= word_count <= 250
        }

def main():
    st.set_page_config(
        page_title="Módulo de Resumen Gomedisys",
        page_icon="🏥",
        layout="wide"
    )
    
    st.title("🏥 Módulo de Resumen Gomedisys")
    
    # Sidebar para carga de archivos
    with st.sidebar:
        st.header("📤 Cargar Historias Clínicas")
        
        default_api_key = os.getenv('OPENAI_API_KEY', '')
        api_key = st.text_input("OpenAI API Key", value=default_api_key, type="password")
        
        uploaded_files = st.file_uploader(
            "Documentos HTML",
            accept_multiple_files=True,
            type=['html', 'htm'],
            help="Sube las historias clínicas en formato HTML"
        )
        
        if uploaded_files:
            st.success(f"📄 {len(uploaded_files)} archivo(s) cargado(s)")
            total_size = sum(file.size for file in uploaded_files)
            st.info(f"Tamaño total: {total_size:,} bytes")
        
        if st.button("🔄 Limpiar"):
            st.rerun()
    
    # Área principal
    if uploaded_files and api_key:
        
        summarizer = GomedisysClinicSummarizer(api_key)
        
        # Mostrar pasos del procesamiento
        st.header("🔄 Procesamiento")
        
        # Paso 1: Preprocesamiento
        with st.expander("📋 Paso 1: Preprocesamiento", expanded=True):
            with st.spinner("Procesando archivos HTML..."):
                all_texts = []
                
                for file in uploaded_files:
                    try:
                        file_bytes = file.read()
                        detected = chardet.detect(file_bytes)
                        encoding = detected['encoding'] or 'utf-8'
                        
                        html_content = file_bytes.decode(encoding, errors='replace')
                        clean_text = summarizer.clean_html_content(html_content)
                        all_texts.append(clean_text)
                        
                        st.success(f"✅ {file.name}: {len(clean_text):,} caracteres procesados")
                        
                    except Exception as e:
                        st.error(f"❌ Error en {file.name}: {str(e)}")
                
                if all_texts:
                    combined_text = '\n\n--- DOCUMENTO SIGUIENTE ---\n\n'.join(all_texts)
                    st.info(f"📊 Total procesado: {len(combined_text):,} caracteres de {len(all_texts)} documento(s)")
        
        # Paso 2: Extracción de información clave
        if all_texts:
            with st.expander("🔍 Paso 2: Extracción de Información Clave", expanded=True):
                key_info = summarizer.extract_key_medical_info(combined_text)
                
                col_a, col_b = st.columns(2)
                
                with col_a:
                    if key_info['microorganismos']:
                        st.success(f"🦠 Microorganismos: {', '.join(key_info['microorganismos'])}")
                    if key_info['resistencias']:
                        st.warning(f"⚠️ Resistencias: {', '.join(key_info['resistencias'])}")
                
                with col_b:
                    if key_info['antibioticos']:
                        st.info(f"💊 Antibióticos: {', '.join(key_info['antibioticos'])}")
                    if key_info['fechas_importantes']:
                        st.info(f"📅 Fechas clave: {', '.join(key_info['fechas_importantes'])}")
            
            # Paso 3: Generación de resúmenes
            with st.expander("⚙️ Paso 3: Generación de Resúmenes", expanded=True):
                with st.spinner("Generando ambos resúmenes..."):
                    col_gen1, col_gen2 = st.columns(2)
                    
                    with col_gen1:
                        st.info("⚡ Generando resumen ultra-conciso...")
                        concise_summary = summarizer.generate_ultra_concise_summary(combined_text)
                        st.success("✅ Ultra-conciso completado")
                    
                    with col_gen2:
                        st.info("📋 Generando resumen estructurado...")
                        structured_summary = summarizer.generate_structured_summary(combined_text)
                        st.success("✅ Estructurado completado")
            
            # Mostrar resultados finales
            st.header("📋 Resultados")
            
            # División en dos columnas para mostrar ambos resúmenes
            col1, col2 = st.columns(2)
            
            # Columna 1: Resumen Ultra-Conciso
            with col1:
                st.subheader("⚡ Resumen Ultra-Conciso")
                st.markdown("*Para urgencias médicas*")
                
                if "Error:" not in concise_summary:
                    validation_concise = summarizer.validate_ultra_concise(concise_summary)
                    
                    # Métricas ultra-conciso
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        if validation_concise['is_optimal']:
                            st.success("✅ Óptimo")
                        else:
                            st.error("❌ Mejorable")
                    
                    with col_b:
                        word_count = validation_concise['word_count']
                        if validation_concise['is_good_length']:
                            st.success(f"Palabras: {word_count}")
                        else:
                            st.warning(f"Palabras: {word_count}")
                    
                    # Mostrar problemas si existen
                    if validation_concise['issues']:
                        with st.expander("Ver problemas"):
                            for issue in validation_concise['issues']:
                                st.write(f"• {issue}")
                    
                    # Mostrar resumen
                    st.markdown("**Resumen:**")
                    st.markdown(concise_summary)
                    
                    # Descarga
                    st.download_button(
                        label="📥 Descargar Conciso",
                        data=concise_summary,
                        file_name=f"conciso_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                    
                else:
                    st.error(concise_summary)
            
            # Columna 2: Resumen Estructurado
            with col2:
                st.subheader("📋 Resumen Estructurado")
                st.markdown("*Para interconsultas detalladas*")
                
                if "Error:" not in structured_summary:
                    validation_structured = summarizer.validate_structured(structured_summary)
                    
                    # Métricas estructurado
                    col_c, col_d = st.columns(2)
                    
                    with col_c:
                        if validation_structured['is_complete']:
                            st.success("✅ Completo")
                        else:
                            st.error("❌ Incompleto")
                    
                    with col_d:
                        word_count = validation_structured['word_count']
                        if validation_structured['is_good_length']:
                            st.success(f"Palabras: {word_count}")
                        else:
                            st.warning(f"Palabras: {word_count}")
                    
                    # Mostrar problemas si existen
                    if validation_structured['issues']:
                        with st.expander("Ver problemas"):
                            for issue in validation_structured['issues']:
                                st.write(f"• {issue}")
                    
                    # Mostrar resumen
                    st.markdown("**Resumen:**")
                    st.markdown(structured_summary)
                    
                    # Descarga
                    st.download_button(
                        label="📥 Descargar Estructurado",
                        data=structured_summary,
                        file_name=f"estructurado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                    
                else:
                    st.error(structured_summary)
    
    elif not uploaded_files:
        st.info("📤 Sube historias clínicas en el panel lateral para comenzar")
    elif not api_key:
        st.info("🔑 Ingresa tu API Key de OpenAI en el panel lateral")

if __name__ == "__main__":
    main()