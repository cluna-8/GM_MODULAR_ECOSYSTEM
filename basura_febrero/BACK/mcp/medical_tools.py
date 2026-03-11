# mcp/medical_tools.py - Refactored Medical Tools for Hybrid Architecture
import aiohttp
import asyncio
import re
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging
from urllib.parse import quote, urlencode

from models import ToolResult, ToolType, ResponseStatus

logger = logging.getLogger(__name__)

class MedicalTools:
    """
    Herramientas médicas refactorizadas para arquitectura híbrida
    Retorna resultados estructurados compatibles con el nuevo sistema
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.enabled_tools: set = set()
        self.request_timeout = 15
        self.max_retries = 3
        
        # Headers para requests HTTP
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; HealthcareBot/2.0; +medical-research)',
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'en-US,en;q=0.9,es;q=0.8'
        }
        
    async def initialize(self):
        """Inicializar herramientas médicas"""
        try:
            if not self.session:
                timeout = aiohttp.ClientTimeout(total=self.request_timeout)
                self.session = aiohttp.ClientSession(
                    headers=self.default_headers,
                    timeout=timeout
                )
                
            # Habilitar todas las herramientas por defecto
            self.enabled_tools = {
                ToolType.FDA.value,
                ToolType.PUBMED.value, 
                #ToolType.CLINICAL_TRIALS.value,
                ToolType.ICD10.value,
                ToolType.SCRAPING.value
            }
            
            logger.info("✅ Medical tools initialized with hybrid architecture")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing medical tools: {e}")
            return False
    
    async def cleanup(self):
        """Limpiar recursos"""
        if self.session:
            await self.session.close()
            logger.info("🧹 Medical tools session closed")
    
    # ============================================================================
    # HERRAMIENTA FDA - MEJORADA
    # ============================================================================
    
    async def search_fda_drug(self, drug_name: str, max_results: int = 3) -> ToolResult:
        """Buscar medicamento en FDA con resultado estructurado"""
        if ToolType.FDA.value not in self.enabled_tools:
            return ToolResult(
                success=False,
                tool_name=ToolType.FDA,
                query=drug_name,
                error_message="FDA tool is disabled"
            )
            
        try:
            await self.initialize()
            
            # URLs de la FDA para probar
            search_strategies = [
                {
                    "url": "https://api.fda.gov/drug/label.json", 
                    "params": {"search": f'openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}"', "limit": max_results}
                },
                {
                    "url": "https://api.fda.gov/drug/event.json",
                    "params": {"search": f'patient.drug.medicinalproduct:"{drug_name}"', "limit": max_results}
                }
            ]
            
            for strategy in search_strategies:
                try:
                    async with self.session.get(strategy["url"], params=strategy["params"]) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'results' in data and data['results']:
                                formatted_result = self._format_fda_response(data, drug_name)
                                
                                return ToolResult(
                                    success=True,
                                    tool_name=ToolType.FDA,
                                    query=drug_name,
                                    raw_result=json.dumps(data['results'][:max_results], indent=2),
                                    processed_result=formatted_result,
                                    metadata={
                                        "results_count": len(data['results']),
                                        "api_endpoint": strategy["url"],
                                        "search_strategy": "official_fda"
                                    }
                                )
                        elif response.status == 404:
                            continue  # Probar siguiente estrategia
                            
                except Exception as e:
                    logger.warning(f"FDA strategy failed: {e}")
                    continue
            
            # Fallback: RxNorm API
            return await self._search_rxnorm_fallback(drug_name)
                
        except Exception as e:
            logger.error(f"FDA search error: {e}")
            return ToolResult(
                success=False,
                tool_name=ToolType.FDA,
                query=drug_name,
                error_message=f"FDA search failed: {str(e)}"
            )
    
    async def _search_rxnorm_fallback(self, drug_name: str) -> ToolResult:
        """Fallback usando RxNorm cuando FDA falla"""
        try:
            url = "https://rxnav.nlm.nih.gov/REST/drugs.json"
            params = {"name": drug_name}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    formatted_result = self._format_rxnorm_response(data, drug_name)
                    
                    return ToolResult(
                        success=True,
                        tool_name=ToolType.FDA,
                        query=drug_name,
                        raw_result=json.dumps(data, indent=2),
                        processed_result=formatted_result,
                        metadata={
                            "source": "rxnorm_fallback",
                            "api_endpoint": url
                        }
                    )
                        
        except Exception as e:
            logger.error(f"RxNorm fallback error: {e}")
        
        return ToolResult(
            success=False,
            tool_name=ToolType.FDA,
            query=drug_name,
            error_message=f"No drug information found for '{drug_name}'"
        )
    
    def _format_fda_response(self, data: Dict, drug_name: str) -> str:
        """Formatear respuesta de FDA"""
        if 'results' not in data:
            return f"No FDA results found for '{drug_name}'"
        
        results = []
        for item in data['results'][:3]:
            if 'openfda' in item:
                openfda = item['openfda']
                brand_name = self._safe_get_first(openfda.get('brand_name', []))
                generic_name = self._safe_get_first(openfda.get('generic_name', []))
                manufacturer = self._safe_get_first(openfda.get('manufacturer_name', []))
                ndc = self._safe_get_first(openfda.get('product_ndc', []))
                
                result_text = f"• **{brand_name}** ({generic_name})"
                if manufacturer != 'Unknown':
                    result_text += f" - {manufacturer}"
                if ndc != 'Unknown':
                    result_text += f" [NDC: {ndc}]"
                    
                results.append(result_text)
                
            elif 'patient' in item and 'drug' in item['patient']:
                # Event data format
                drugs = item['patient']['drug'][:2]
                for drug in drugs:
                    name = drug.get('medicinalproduct', 'Unknown')
                    if name != 'Unknown':
                        results.append(f"• **{name}**")
        
        if results:
            return f"**FDA Drug Information for '{drug_name}':**\n" + "\n".join(results)
        return f"No detailed information found for '{drug_name}'"
    
    def _format_rxnorm_response(self, data: Dict, drug_name: str) -> str:
        """Formatear respuesta de RxNorm"""
        try:
            drug_group = data.get('drugGroup', {})
            concept_groups = drug_group.get('conceptGroup', [])
            
            results = []
            for group in concept_groups:
                if 'conceptProperties' in group:
                    concepts = group['conceptProperties'][:3]
                    for concept in concepts:
                        name = concept.get('name', 'Unknown')
                        rxcui = concept.get('rxcui', 'Unknown')
                        synonym = concept.get('synonym', '')
                        
                        result_text = f"• **{name}**"
                        if rxcui != 'Unknown':
                            result_text += f" (RxCUI: {rxcui})"
                        if synonym:
                            result_text += f" - {synonym}"
                            
                        results.append(result_text)
            
            if results:
                return f"**RxNorm Drug Information for '{drug_name}':**\n" + "\n".join(results)
                
        except Exception as e:
            logger.error(f"Error formatting RxNorm response: {e}")
        
        return f"No drug information found for '{drug_name}' in available databases"
    
    def _safe_get_first(self, item_list: List) -> str:
        """Obtener primer elemento de lista de forma segura"""
        if item_list and len(item_list) > 0:
            return str(item_list[0])
        return 'Unknown'
    
    # ============================================================================
    # HERRAMIENTA PUBMED - MEJORADA
    # ============================================================================
    
    async def search_pubmed(self, query: str, max_results: int = 3) -> ToolResult:
        """Buscar literatura médica en PubMed con resultado estructurado"""
        if ToolType.PUBMED.value not in self.enabled_tools:
            return ToolResult(
                success=False,
                tool_name=ToolType.PUBMED,
                query=query,
                error_message="PubMed tool is disabled"
            )
            
        try:
            await self.initialize()
            
            # Paso 1: Búsqueda de PMIDs
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json",
                "sort": "relevance",
                "field": "title/abstract"
            }
            
            async with self.session.get(search_url, params=search_params) as response:
                if response.status != 200:
                    return ToolResult(
                        success=False,
                        tool_name=ToolType.PUBMED,
                        query=query,
                        error_message=f"PubMed search API error: {response.status}"
                    )
                
                search_data = await response.json()
                pmids = search_data.get('esearchresult', {}).get('idlist', [])
                
                if not pmids:
                    return ToolResult(
                        success=False,
                        tool_name=ToolType.PUBMED,
                        query=query,
                        error_message=f"No PubMed articles found for '{query}'"
                    )
                
                # Paso 2: Obtener detalles de artículos
                summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                summary_params = {
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "json"
                }
                
                async with self.session.get(summary_url, params=summary_params) as summary_response:
                    if summary_response.status == 200:
                        summary_data = await summary_response.json()
                        formatted_result = self._format_pubmed_response(summary_data, pmids, query)
                        
                        return ToolResult(
                            success=True,
                            tool_name=ToolType.PUBMED,
                            query=query,
                            raw_result=json.dumps(summary_data, indent=2),
                            processed_result=formatted_result,
                            metadata={
                                "results_count": len(pmids),
                                "pmids": pmids,
                                "search_url": search_url
                            }
                        )
                    
        except Exception as e:
            logger.error(f"PubMed search error: {e}")
            return ToolResult(
                success=False,
                tool_name=ToolType.PUBMED,
                query=query,
                error_message=f"PubMed search failed: {str(e)}"
            )
    
    def _format_pubmed_response(self, data: Dict, pmids: List[str], query: str) -> str:
        """Formatear respuesta de PubMed"""
        results = []
        
        for pmid in pmids[:3]:
            if pmid in data.get('result', {}):
                article = data['result'][pmid]
                
                title = article.get('title', 'No title available')
                authors = article.get('authors', [])
                author_names = [a.get('name', '') for a in authors[:3]]
                journal = article.get('source', 'Unknown journal')
                pub_date = article.get('pubdate', 'Unknown date')
                
                # Limpiar título de HTML tags
                title = re.sub(r'<[^>]+>', '', title)
                
                result_text = f"• **{title}**\n"
                if author_names:
                    result_text += f"  *Authors:* {', '.join(author_names)}\n"
                result_text += f"  *Journal:* {journal} ({pub_date})\n"
                result_text += f"  *PMID:* {pmid}"
                
                results.append(result_text)
        
        if results:
            return f"**PubMed Literature Search for '{query}':**\n\n" + "\n\n".join(results)
        return f"No articles found for '{query}'"
    
    # ============================================================================
    # HERRAMIENTA CLINICAL TRIALS - MEJORADA
    # ============================================================================
    
    async def search_clinical_trials(self, condition: str, max_results: int = 3) -> ToolResult:
        """Buscar ensayos clínicos con resultado estructurado"""
        if ToolType.CLINICAL_TRIALS.value not in self.enabled_tools:
            return ToolResult(
                success=False,
                tool_name=ToolType.CLINICAL_TRIALS,
                query=condition,
                error_message="Clinical Trials tool is disabled"
            )
            
        try:
            await self.initialize()
            
            url = "https://clinicaltrials.gov/api/v2/studies"
            params = {
                "query.condition": condition,  # Correcto para v2
                "filter.overall_status": "RECRUITING",  # Formato v2
                "pageSize": max_results,
                "format": "json"
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    studies = data.get('studies', [])
                    
                    if not studies:
                        return ToolResult(
                            success=False,
                            tool_name=ToolType.CLINICAL_TRIALS,
                            query=condition,
                            error_message=f"No recruiting clinical trials found for '{condition}'"
                        )
                    
                    formatted_result = self._format_clinical_trials_response(studies, condition)
                    
                    return ToolResult(
                        success=True,
                        tool_name=ToolType.CLINICAL_TRIALS,
                        query=condition,
                        raw_result=json.dumps(studies, indent=2),
                        processed_result=formatted_result,
                        metadata={
                            "results_count": len(studies),
                            "api_endpoint": url,
                            "status_filter": "RECRUITING"
                        }
                    )
                else:
                    return ToolResult(
                        success=False,
                        tool_name=ToolType.CLINICAL_TRIALS,
                        query=condition,
                        error_message=f"Clinical Trials API error: {response.status}"
                    )
                    
        except Exception as e:
            logger.error(f"Clinical Trials search error: {e}")
            return ToolResult(
                success=False,
                tool_name=ToolType.CLINICAL_TRIALS,
                query=condition,
                error_message=f"Clinical Trials search failed: {str(e)}"
            )
    
    def _format_clinical_trials_response(self, studies: List[Dict], condition: str) -> str:
        """Formatear respuesta de Clinical Trials"""
        results = []
        
        for study in studies[:3]:
            protocol = study.get('protocolSection', {})
            identification = protocol.get('identificationModule', {})
            design = protocol.get('designModule', {})
            
            title = identification.get('briefTitle', 'No title available')
            nct_id = identification.get('nctId', 'Unknown ID')
            phases = design.get('phases', ['Unknown'])
            phase = phases[0] if phases else 'Unknown'
            
            # Obtener intervenciones si están disponibles
            interventions = protocol.get('armsInterventionsModule', {}).get('interventions', [])
            intervention_names = [i.get('name', '') for i in interventions[:2]]
            
            result_text = f"• **{title}**\n"
            result_text += f"  *NCT ID:* {nct_id}\n"
            result_text += f"  *Phase:* {phase}\n"
            result_text += f"  *Status:* Recruiting"
            
            if intervention_names:
                result_text += f"\n  *Interventions:* {', '.join(intervention_names)}"
            
            results.append(result_text)
        
        if results:
            return f"**Clinical Trials for '{condition}':**\n\n" + "\n\n".join(results)
        return f"No clinical trials found for '{condition}'"
    
    # ============================================================================
    # HERRAMIENTA ICD-10 - MEJORADA
    # ============================================================================
    
    async def search_icd10(self, term: str, max_results: int = 5) -> ToolResult:
        """Buscar códigos ICD-10 con resultado estructurado"""
        if ToolType.ICD10.value not in self.enabled_tools:
            return ToolResult(
                success=False,
                tool_name=ToolType.ICD10,
                query=term,
                error_message="ICD-10 tool is disabled"
            )
            
        try:
            await self.initialize()
            
            url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
            params = {
                "sf": "code,name",
                "terms": term,
                "maxList": max_results
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if len(data) > 3 and data[3]:
                        formatted_result = self._format_icd10_response(data[3], term)
                        
                        return ToolResult(
                            success=True,
                            tool_name=ToolType.ICD10,
                            query=term,
                            raw_result=json.dumps(data[3], indent=2),
                            processed_result=formatted_result,
                            metadata={
                                "results_count": len(data[3]),
                                "api_endpoint": url
                            }
                        )
                    else:
                        return ToolResult(
                            success=False,
                            tool_name=ToolType.ICD10,
                            query=term,
                            error_message=f"No ICD-10 codes found for '{term}'"
                        )
                else:
                    return ToolResult(
                        success=False,
                        tool_name=ToolType.ICD10,
                        query=term,
                        error_message=f"ICD-10 API error: {response.status}"
                    )
                    
        except Exception as e:
            logger.error(f"ICD-10 search error: {e}")
            return ToolResult(
                success=False,
                tool_name=ToolType.ICD10,
                query=term,
                error_message=f"ICD-10 search failed: {str(e)}"
            )
    
    def _format_icd10_response(self, items: List, term: str) -> str:
        """Formatear respuesta de ICD-10"""
        results = []
        
        for item in items[:5]:
            if len(item) >= 2:
                code = item[0]
                description = item[1]
                results.append(f"• **{code}**: {description}")
        
        if results:
            return f"**ICD-10 codes for '{term}':**\n" + "\n".join(results)
        return f"No ICD-10 codes found for '{term}'"
    
    # ============================================================================
    # HERRAMIENTA WEB SCRAPING - MEJORADA
    # ============================================================================
    
    async def scrape_medical_site(self, url: str, search_term: str = None, max_content_length: int = 2000) -> ToolResult:
        """Web scraping de sitios médicos con resultado estructurado"""
        if ToolType.SCRAPING.value not in self.enabled_tools:
            return ToolResult(
                success=False,
                tool_name=ToolType.SCRAPING,
                query=f"{url} ({search_term})" if search_term else url,
                error_message="Web scraping tool is disabled"
            )
            
        try:
            await self.initialize()
            
            # Headers específicos para scraping
            scraping_headers = {
                **self.default_headers,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            async with self.session.get(url, headers=scraping_headers) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Limpiar HTML básico
                    clean_text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                    clean_text = re.sub(r'<style[^>]*>.*?</style>', '', clean_text, flags=re.DOTALL | re.IGNORECASE)
                    clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    
                    # Buscar término específico si se proporciona
                    if search_term:
                        formatted_result = self._extract_relevant_content(clean_text, search_term, url)
                    else:
                        # Tomar primeros caracteres si no hay término específico
                        preview = clean_text[:max_content_length]
                        if len(clean_text) > max_content_length:
                            preview += "..."
                        formatted_result = f"**Content preview from {url}:**\n\n{preview}"
                    
                    return ToolResult(
                        success=True,
                        tool_name=ToolType.SCRAPING,
                        query=f"{url} ({search_term})" if search_term else url,
                        raw_result=clean_text[:1000] + "..." if len(clean_text) > 1000 else clean_text,
                        processed_result=formatted_result,
                        metadata={
                            "url": url,
                            "search_term": search_term,
                            "content_length": len(clean_text),
                            "status_code": response.status
                        }
                    )
                else:
                    return ToolResult(
                        success=False,
                        tool_name=ToolType.SCRAPING,
                        query=f"{url} ({search_term})" if search_term else url,
                        error_message=f"HTTP {response.status}: Unable to access {url}"
                    )
                    
        except Exception as e:
            logger.error(f"Web scraping error: {e}")
            return ToolResult(
                success=False,
                tool_name=ToolType.SCRAPING,
                query=f"{url} ({search_term})" if search_term else url,
                error_message=f"Web scraping failed: {str(e)}"
            )
    
    def _extract_relevant_content(self, text: str, search_term: str, url: str) -> str:
        """Extraer contenido relevante basado en término de búsqueda"""
        search_term_lower = search_term.lower()
        text_lower = text.lower()
        
        if search_term_lower in text_lower:
            # Encontrar todas las posiciones del término
            positions = []
            start = 0
            while True:
                pos = text_lower.find(search_term_lower, start)
                if pos == -1:
                    break
                positions.append(pos)
                start = pos + 1
            
            # Extraer contexto alrededor de las primeras 2 ocurrencias
            contexts = []
            for pos in positions[:2]:
                context_start = max(0, pos - 300)
                context_end = min(len(text), pos + 300)
                context = text[context_start:context_end]
                
                # Marcar el término encontrado
                context = re.sub(
                    re.escape(search_term), 
                    f"**{search_term}**", 
                    context, 
                    flags=re.IGNORECASE
                )
                
                contexts.append(f"...{context}...")
            
            result = f"**Found '{search_term}' in {url}:**\n\n"
            result += "\n\n---\n\n".join(contexts)
            return result
        else:
            return f"**Term '{search_term}' not found in {url}**\n\nContent preview:\n{text[:500]}..."
    
    # ============================================================================
    # MÉTODOS DE GESTIÓN Y UTILIDADES
    # ============================================================================
    
    def enable_tool(self, tool_name: str) -> bool:
        """Habilitar herramienta específica"""
        if tool_name in [tool.value for tool in ToolType]:
            self.enabled_tools.add(tool_name)
            logger.info(f"✅ Enabled tool: {tool_name}")
            return True
        logger.warning(f"⚠️ Unknown tool: {tool_name}")
        return False
    
    def disable_tool(self, tool_name: str) -> bool:
        """Deshabilitar herramienta específica"""
        self.enabled_tools.discard(tool_name)
        logger.info(f"❌ Disabled tool: {tool_name}")
        return True
    
    def is_tool_enabled(self, tool_name: Union[str, ToolType]) -> bool:
        """Verificar si una herramienta está habilitada"""
        tool_str = tool_name.value if isinstance(tool_name, ToolType) else tool_name
        return tool_str in self.enabled_tools
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Obtener lista de herramientas disponibles"""
        tools = []
        
        for tool in ToolType:
            tools.append({
                "name": tool.value,
                "enabled": self.is_tool_enabled(tool),
                "description": self._get_tool_description(tool),
                "methods": self._get_tool_methods(tool)
            })
        
        return tools
    
    def _get_tool_description(self, tool: ToolType) -> str:
        """Obtener descripción de herramienta"""
        descriptions = {
            ToolType.FDA: "Search FDA drug database for official medication information",
            ToolType.PUBMED: "Search PubMed for peer-reviewed medical literature", 
            ToolType.CLINICAL_TRIALS: "Search ClinicalTrials.gov for active clinical studies",
            ToolType.ICD10: "Search ICD-10 medical diagnostic codes",
            ToolType.SCRAPING: "Extract medical information from trusted websites"
        }
        return descriptions.get(tool, "Unknown tool")
    
    def _get_tool_methods(self, tool: ToolType) -> List[str]:
        """Obtener métodos disponibles para herramienta"""
        methods = {
            ToolType.FDA: ["search_fda_drug"],
            ToolType.PUBMED: ["search_pubmed"],
            ToolType.CLINICAL_TRIALS: ["search_clinical_trials"],
            ToolType.ICD10: ["search_icd10"],
            ToolType.SCRAPING: ["scrape_medical_site"]
        }
        return methods.get(tool, [])
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener estado completo de las herramientas médicas"""
        return {
            "initialized": self.session is not None,
            "enabled_tools": list(self.enabled_tools),
            "available_tools": [tool.value for tool in ToolType],
            "session_active": self.session is not None and not self.session.closed,
            "request_timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "all_tools_free": True,
            "rate_limits": {
                "fda": "No official limit",
                "pubmed": "10,000 requests/day (E-utilities)",
                "clinical_trials": "No official limit",
                "icd10": "No official limit",
                "scraping": "Depends on target website"
            }
        }

# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_medical_tools_instance: Optional[MedicalTools] = None

async def get_medical_tools() -> MedicalTools:
    """Obtener instancia singleton de MedicalTools"""
    global _medical_tools_instance
    
    if _medical_tools_instance is None:
        _medical_tools_instance = MedicalTools()
        await _medical_tools_instance.initialize()
    
    return _medical_tools_instance