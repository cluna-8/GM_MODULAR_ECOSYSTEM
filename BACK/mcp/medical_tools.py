# mcp/medical_tools.py - Herramientas médicas simples
import aiohttp
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

class MedicalTools:
    def __init__(self):
        self.session = None
        self.enabled_tools = set()
        
    async def initialize(self):
        """Inicializar herramientas médicas"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        # Habilitar herramientas por defecto
        self.enabled_tools = {"fda", "pubmed", "clinicaltrials", "scraping"}
        print("✅ Medical tools initialized")
    
    async def cleanup(self):
        """Limpiar recursos"""
        if self.session:
            await self.session.close()
    
    # ============ FDA API (GRATIS) ============
    async def search_fda_drug(self, drug_name: str) -> str:
        """Busca medicamento en FDA - Completamente gratis"""
        if "fda" not in self.enabled_tools:
            return "FDA tool not enabled"
            
        try:
            await self.initialize()
            # Intentar primero drug/label, si falla probar drug/event
            urls_to_try = [
                "https://api.fda.gov/drug/label.json",
                "https://api.fda.gov/drug/event.json"
            ]
            
            for url in urls_to_try:
                params = {
                    "search": f'patient.drug.medicinalproduct:"{drug_name}"' if 'event' in url else f'openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}"',
                    "limit": 3
                }
                
                try:
                    async with self.session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'results' in data and data['results']:
                                return self._format_fda_response(data, drug_name)
                        elif response.status == 404:
                            continue  # Try next URL
                        else:
                            print(f"FDA API response {response.status}: {await response.text()}")
                except Exception as e:
                    print(f"Error with {url}: {e}")
                    continue
            
            # Si ambas fallan, usar API alternativa simple
            return await self._search_drug_simple(drug_name)
                
        except Exception as e:
            return f"FDA search error: {str(e)}"
    
    async def _search_drug_simple(self, drug_name: str) -> str:
        """Fallback simple drug search"""
        try:
            # Usar RxNorm como alternativa
            url = "https://rxnav.nlm.nih.gov/REST/drugs.json"
            params = {"name": drug_name}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    drug_group = data.get('drugGroup', {})
                    concept_group = drug_group.get('conceptGroup', [])
                    
                    if concept_group:
                        for group in concept_group:
                            if 'conceptProperties' in group:
                                concepts = group['conceptProperties'][:3]
                                results = []
                                for concept in concepts:
                                    name = concept.get('name', 'Unknown')
                                    rxcui = concept.get('rxcui', 'Unknown')
                                    results.append(f"• **{name}** (RxCUI: {rxcui})")
                                
                                if results:
                                    return f"RxNorm Drug Information for '{drug_name}':\n" + "\n".join(results)
                    
                    return f"No drug information found for '{drug_name}' in available databases"
                
        except Exception as e:
            return f"Drug search failed: {str(e)}"
    
    def _format_fda_response(self, data: Dict, drug_name: str) -> str:
        """Formatea respuesta de FDA"""
        if 'results' not in data:
            return f"No FDA results found for '{drug_name}'"
        
        results = []
        for item in data['results'][:3]:
            if 'openfda' in item:
                openfda = item['openfda']
                brand_name = openfda.get('brand_name', ['Unknown'])[0] if openfda.get('brand_name') else 'Unknown'
                generic_name = openfda.get('generic_name', ['Unknown'])[0] if openfda.get('generic_name') else 'Unknown'
                manufacturer = openfda.get('manufacturer_name', ['Unknown'])[0] if openfda.get('manufacturer_name') else 'Unknown'
                
                results.append(f"• **{brand_name}** ({generic_name}) - {manufacturer}")
            elif 'patient' in item:
                # Event data format
                drugs = item.get('patient', {}).get('drug', [])
                for drug in drugs[:2]:
                    name = drug.get('medicinalproduct', 'Unknown')
                    results.append(f"• **{name}**")
        
        if results:
            return f"FDA Drug Information for '{drug_name}':\n" + "\n".join(results)
        return f"No detailed information found for '{drug_name}'"
    
    # ============ PubMed API (GRATIS hasta 10k/día) ============
    async def search_pubmed(self, query: str, max_results: int = 3) -> str:
        """Busca literatura médica en PubMed - Gratis hasta 10,000/día"""
        if "pubmed" not in self.enabled_tools:
            return "PubMed tool not enabled"
            
        try:
            await self.initialize()
            
            # Búsqueda de PMIDs
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "json"
            }
            
            async with self.session.get(search_url, params=search_params) as response:
                if response.status == 200:
                    search_data = await response.json()
                    pmids = search_data.get('esearchresult', {}).get('idlist', [])
                    
                    if not pmids:
                        return f"No PubMed articles found for '{query}'"
                    
                    # Obtener detalles de artículos
                    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                    summary_params = {
                        "db": "pubmed",
                        "id": ",".join(pmids),
                        "retmode": "json"
                    }
                    
                    async with self.session.get(summary_url, params=summary_params) as summary_response:
                        if summary_response.status == 200:
                            summary_data = await summary_response.json()
                            results = []
                            
                            for pmid in pmids[:3]:
                                if pmid in summary_data.get('result', {}):
                                    article = summary_data['result'][pmid]
                                    title = article.get('title', 'No title')
                                    authors = article.get('authors', [])
                                    author_names = [a.get('name', '') for a in authors[:2]]
                                    journal = article.get('source', 'Unknown journal')
                                    year = article.get('pubdate', 'Unknown year')
                                    
                                    result_text = f"• **{title}**\n  Authors: {', '.join(author_names)}\n  Journal: {journal} ({year})\n  PMID: {pmid}"
                                    results.append(result_text)
                            
                            return f"PubMed Literature Search for '{query}':\n\n" + "\n\n".join(results)
                
                return f"PubMed API error: {response.status}"
                
        except Exception as e:
            return f"PubMed search error: {str(e)}"
    
    # ============ Clinical Trials (GRATIS) ============
    async def search_clinical_trials(self, condition: str, max_results: int = 3) -> str:
        """Busca ensayos clínicos - Completamente gratis"""
        if "clinicaltrials" not in self.enabled_tools:
            return "Clinical trials tool not enabled"
            
        try:
            await self.initialize()
            url = "https://clinicaltrials.gov/api/v2/studies"
            params = {
                "query.cond": condition,
                "filter.overallStatus": "RECRUITING",
                "pageSize": max_results,
                "format": "json"
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    studies = data.get('studies', [])
                    
                    if not studies:
                        return f"No recruiting clinical trials found for '{condition}'"
                    
                    results = []
                    for study in studies[:3]:
                        protocol = study.get('protocolSection', {})
                        identification = protocol.get('identificationModule', {})
                        design = protocol.get('designModule', {})
                        
                        title = identification.get('briefTitle', 'No title')
                        nct_id = identification.get('nctId', 'Unknown ID')
                        phase = design.get('phases', ['Unknown'])[0] if design.get('phases') else 'Unknown'
                        
                        result_text = f"• **{title}**\n  NCT ID: {nct_id}\n  Phase: {phase}\n  Status: Recruiting"
                        results.append(result_text)
                    
                    return f"Clinical Trials for '{condition}':\n\n" + "\n\n".join(results)
                
                return f"Clinical Trials API error: {response.status}"
                
        except Exception as e:
            return f"Clinical trials search error: {str(e)}"
    
    # ============ Web Scraping Simple ============
    async def scrape_medical_site(self, url: str, search_term: str = None) -> str:
        """Scraping simple de sitios médicos - Gratis"""
        if "scraping" not in self.enabled_tools:
            return "Web scraping tool not enabled"
            
        try:
            await self.initialize()
            
            # Headers para parecer un navegador normal
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Extracción básica de texto (sin BeautifulSoup para mantener simple)
                    # Remover tags HTML básicos
                    import re
                    text = re.sub(r'<[^>]+>', ' ', content)
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    # Si hay término de búsqueda, buscar contexto
                    if search_term:
                        search_term_lower = search_term.lower()
                        text_lower = text.lower()
                        
                        if search_term_lower in text_lower:
                            # Encontrar el contexto alrededor del término
                            pos = text_lower.find(search_term_lower)
                            start = max(0, pos - 200)
                            end = min(len(text), pos + 200)
                            context = text[start:end]
                            return f"Found '{search_term}' in {url}:\n\n...{context}..."
                        else:
                            return f"Term '{search_term}' not found in {url}"
                    
                    # Si no hay término, devolver primeros caracteres
                    preview = text[:500] + "..." if len(text) > 500 else text
                    return f"Content from {url}:\n\n{preview}"
                
                return f"Error accessing {url}: HTTP {response.status}"
                
        except Exception as e:
            return f"Scraping error for {url}: {str(e)}"
    
    # ============ ICD-10 Simple (GRATIS) ============
    async def search_icd10(self, term: str) -> str:
        """Busca códigos ICD-10 - Gratis"""
        try:
            await self.initialize()
            url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
            params = {"sf": "code,name", "terms": term, "maxList": 5}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if len(data) > 3 and data[3]:
                        results = []
                        for item in data[3][:5]:
                            if len(item) >= 2:
                                code = item[0]
                                name = item[1]
                                results.append(f"• **{code}**: {name}")
                        
                        if results:
                            return f"ICD-10 codes for '{term}':\n" + "\n".join(results)
                    
                    return f"No ICD-10 codes found for '{term}'"
                
                return f"ICD-10 API error: {response.status}"
                
        except Exception as e:
            return f"ICD-10 search error: {str(e)}"

    # ============ Herramientas disponibles para LlamaIndex ============
    def get_available_functions(self) -> List[Dict[str, Any]]:
        """Retorna funciones disponibles como diccionarios para LlamaIndex"""
        return [
            {
                "name": "search_fda_drug",
                "function": self.search_fda_drug,
                "description": "Search for drug information in FDA database (free, unlimited)",
                "parameters": {"drug_name": "string - name of the drug to search"}
            },
            {
                "name": "search_pubmed",
                "function": self.search_pubmed,
                "description": "Search medical literature in PubMed (free, 10k requests/day)",
                "parameters": {"query": "string - medical search query", "max_results": "int - max number of results (default 3)"}
            },
            {
                "name": "search_clinical_trials",
                "function": self.search_clinical_trials,
                "description": "Search recruiting clinical trials (free, unlimited)",
                "parameters": {"condition": "string - medical condition", "max_results": "int - max results (default 3)"}
            },
            {
                "name": "search_icd10",
                "function": self.search_icd10,
                "description": "Search ICD-10 medical codes (free, unlimited)",
                "parameters": {"term": "string - medical term to find ICD-10 codes"}
            },
            {
                "name": "scrape_medical_site",
                "function": self.scrape_medical_site,
                "description": "Scrape content from medical websites (free)",
                "parameters": {"url": "string - website URL", "search_term": "string - optional term to find in content"}
            }
        ]
    
    def enable_tool(self, tool_name: str) -> bool:
        """Habilitar herramienta específica"""
        valid_tools = {"fda", "pubmed", "clinicaltrials", "scraping", "icd10"}
        if tool_name in valid_tools:
            self.enabled_tools.add(tool_name)
            return True
        return False
    
    def disable_tool(self, tool_name: str) -> bool:
        """Deshabilitar herramienta específica"""
        self.enabled_tools.discard(tool_name)
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Estado de las herramientas médicas"""
        return {
            "available_tools": ["fda", "pubmed", "clinicaltrials", "icd10", "scraping"],
            "enabled_tools": list(self.enabled_tools),
            "session_active": self.session is not None,
            "all_free": True,
            "rate_limits": {
                "fda": "No limit",
                "pubmed": "10,000 requests/day",
                "clinicaltrials": "No limit", 
                "icd10": "No limit",
                "scraping": "Depends on target site"
            }
        }
