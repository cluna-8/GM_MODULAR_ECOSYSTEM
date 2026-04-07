# prompt_manager.py - Gestión Dinámica de Prompts con YAML + Redis
import asyncio
import yaml
import json
import os
from typing import Dict, Optional, Any
from datetime import datetime
import logging
import redis.asyncio as redis
from pathlib import Path

from models import PromptConfig, PromptMode, ToolType



logger = logging.getLogger(__name__)

class PromptManager:
    """
    Gestor de prompts que carga desde YAML y almacena en Redis
    Permite hot reload y fallbacks automáticos
    """
    
    def __init__(self, redis_client: redis.Redis = None, yaml_path: str = "prompts.yml"):
        self.redis_client = redis_client
        self.yaml_path = Path(yaml_path)
        self.prompts_cache: Dict[str, PromptConfig] = {}
        self.version = "1.0.0"
        self.last_loaded = None
        
        # Redis keys
        self.REDIS_PREFIX = "prompts:"
        self.VERSION_KEY = "prompts:version"
        self.LAST_LOADED_KEY = "prompts:last_loaded"
        
    async def initialize(self):
        """Inicializar el gestor de prompts"""
        try:
            # Cargar prompts desde YAML si existe
            if self.yaml_path.exists():
                await self.load_prompts_from_yaml()
                logger.info(f"✅ Prompts loaded from {self.yaml_path}")
            else:
                # Crear YAML por defecto si no existe
                await self.create_default_prompts_yaml()
                await self.load_prompts_from_yaml()
                logger.info(f"✅ Default prompts created and loaded")
                
            # Cargar prompts por defecto en memoria como fallback
            await self._load_default_prompts()
            
            logger.info(f"🎯 PromptManager initialized with {len(self.prompts_cache)} prompts")
            
        except Exception as e:
            logger.error(f"❌ Error initializing PromptManager: {e}")
            # Cargar solo prompts por defecto como fallback
            await self._load_default_prompts()
    
    async def load_prompts_from_yaml(self) -> bool:
        """Cargar prompts desde archivo YAML a Redis y cache"""
        try:
            if not self.yaml_path.exists():
                logger.warning(f"YAML file not found: {self.yaml_path}")
                return False
                
            with open(self.yaml_path, 'r', encoding='utf-8') as file:
                yaml_data = yaml.safe_load(file)
            
            if not yaml_data or 'prompts' not in yaml_data:
                logger.error("Invalid YAML structure - missing 'prompts' key")
                return False
            
            prompts_data = yaml_data['prompts']
            loaded_count = 0
            
            # Procesar cada prompt
            for mode_name, config in prompts_data.items():
                try:
                    # Validar que el modo existe en el enum
                    if mode_name.upper() not in PromptMode.__members__:
                        logger.warning(f"Unknown prompt mode: {mode_name}")
                        continue
                    
                    # Crear configuración de prompt
                    prompt_config = PromptConfig(
                        system_prompt=config.get('system_prompt', ''),
                        temperature=config.get('temperature', 0.1),
                        max_tokens=config.get('max_tokens', 1000),
                        description=config.get('description', '')
                    )
                    
                    # Guardar en cache local
                    self.prompts_cache[mode_name] = prompt_config
                    
                    # Guardar en Redis si está disponible
                    if self.redis_client:
                        redis_key = f"{self.REDIS_PREFIX}{mode_name}"
                        await self.redis_client.set(
                            redis_key, 
                            prompt_config.model_dump_json(),
                            ex=86400  # 24 horas de expiración
                        )
                    
                    loaded_count += 1
                    logger.debug(f"Loaded prompt: {mode_name}")
                    
                except Exception as e:
                    logger.error(f"Error loading prompt {mode_name}: {e}")
                    continue
            
            # Cargar tool_prompts si existen
            if 'tool_prompts' in yaml_data:
                self.tool_prompts_cache = {}
                tool_prompts_data = yaml_data['tool_prompts']
                
                for tool_name, config in tool_prompts_data.items():
                    if 'system_prompt' in config:
                        self.tool_prompts_cache[tool_name] = config['system_prompt']
                        logger.debug(f"Loaded tool prompt: {tool_name}")
                
                logger.info(f"✅ Loaded {len(self.tool_prompts_cache)} tool prompts from YAML")
            else:
                logger.warning("No tool_prompts section found in YAML")
                self.tool_prompts_cache = {}
            
            # Cargar extraction_prompts si existen
            if 'extraction_prompts' in yaml_data:
                self.extraction_prompts_cache = {}
                extraction_prompts_data = yaml_data['extraction_prompts']
                
                for tool_name, config in extraction_prompts_data.items():
                    if 'system_prompt' in config:
                        self.extraction_prompts_cache[tool_name] = config['system_prompt']
                        logger.debug(f"Loaded extraction prompt: {tool_name}")
                
                logger.info(f"✅ Loaded {len(self.extraction_prompts_cache)} extraction prompts from YAML")
            else:
                logger.warning("No extraction_prompts section found in YAML")
                self.extraction_prompts_cache = {}
            
            # Actualizar metadatos
            self.last_loaded = datetime.now()
            self.version = yaml_data.get('version', '1.0.0')
            
            if self.redis_client:
                await self.redis_client.set(self.VERSION_KEY, self.version)
                await self.redis_client.set(self.LAST_LOADED_KEY, self.last_loaded.isoformat())
            
            logger.info(f"✅ Loaded {loaded_count} prompts from YAML")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error loading prompts from YAML: {e}")
            return False
    
    async def get_prompt(self, mode: PromptMode) -> PromptConfig:
        """Obtener configuración de prompt por modo"""
        mode_str = mode.value if isinstance(mode, PromptMode) else str(mode)
        
        try:
            # 1. Intentar desde cache local
            if mode_str in self.prompts_cache:
                return self.prompts_cache[mode_str]
            
            # 2. Intentar desde Redis
            if self.redis_client:
                redis_key = f"{self.REDIS_PREFIX}{mode_str}"
                cached_data = await self.redis_client.get(redis_key)
                
                if cached_data:
                    prompt_config = PromptConfig.model_validate_json(cached_data)
                    # Actualizar cache local
                    self.prompts_cache[mode_str] = prompt_config
                    return prompt_config
            
            # 3. Fallback a prompt por defecto
            logger.warning(f"Prompt not found for mode: {mode_str}, using default")
            return self._get_default_prompt(mode_str)
            
        except Exception as e:
            logger.error(f"Error getting prompt for {mode_str}: {e}")
            return self._get_default_prompt(mode_str)
    
    async def get_tool_prompt(self, tool_type: ToolType) -> str:
        """Obtener prompt específico para herramienta desde YAML"""
        try:
            # Recargar YAML si es necesario para obtener tool_prompts
            if not hasattr(self, 'tool_prompts_cache'):
                await self.load_prompts_from_yaml()
            
            tool_name = tool_type.value
            
            # Obtener desde cache de tool_prompts
            if hasattr(self, 'tool_prompts_cache') and tool_name in self.tool_prompts_cache:
                return self.tool_prompts_cache[tool_name]
            
            logger.warning(f"Tool prompt not found for {tool_name}")
            return f"Use information from {tool_name.upper()}: {{tool_data}}"
            
        except Exception as e:
            logger.error(f"Error getting tool prompt: {e}")
            return f"Use information from {tool_type.value.upper()}: {{tool_data}}"

    
    def _get_default_prompt(self, mode: str) -> PromptConfig:
        """Obtener prompt por defecto según el modo"""
        default_prompts = {
            "medical": PromptConfig(
                system_prompt="""Eres un asistente médico profesional con acceso a bases de datos médicas.
                Proporciona información médica precisa y profesional, siempre recomendando consultar con profesionales de la salud.
                Responde en el mismo idioma que te preguntaron.
                Utiliza markdown para estructurar tus respuestas de manera clara y profesional.""",
                temperature=0.1,
                max_tokens=1000,
                description="Asistente médico general"
            ),
            "pediatric": PromptConfig(
                system_prompt="""Eres un especialista en medicina pediátrica.
                Proporciona información médica específica para niños y adolescentes.
                Usa lenguaje apropiado y considera las diferencias de dosificación por edad/peso.
                Siempre enfatiza la importancia de consultar con pediatras.""",
                temperature=0.05,
                max_tokens=800,
                description="Especialista en pediatría"
            ),
            "emergency": PromptConfig(
                system_prompt="""Eres un médico de urgencias. Prioriza información crítica y signos de alarma.
                Proporciona respuestas concisas y directas. Indica cuándo buscar atención médica inmediata.
                Usa un tono profesional pero tranquilizador.""",
                temperature=0.0,
                max_tokens=600,
                description="Medicina de urgencias"
            ),
            "pharmacy": PromptConfig(
                system_prompt="""Eres un farmacéutico especializado.
                Proporciona información detallada sobre medicamentos, dosificación, interacciones y efectos secundarios.
                Enfócate en la seguridad farmacológica y siempre recomienda consultar con profesionales.""",
                temperature=0.1,
                max_tokens=1200,
                description="Farmacología especializada"
            ),
            "general": PromptConfig(
                system_prompt="""Eres un asistente de salud general.
                Proporciona información básica sobre salud y bienestar.
                Mantén un tono amigable pero profesional.
                Siempre recomienda consultar profesionales para diagnósticos específicos.""",
                temperature=0.2,
                max_tokens=800,
                description="Asistente de salud general"
            )
        }
        
        return default_prompts.get(mode, default_prompts["medical"])
    
    async def _load_default_prompts(self):
        """Cargar prompts por defecto en cache"""
        for mode in PromptMode:
            if mode.value not in self.prompts_cache:
                self.prompts_cache[mode.value] = self._get_default_prompt(mode.value)
    
    async def update_prompt(self, mode: PromptMode, config: PromptConfig) -> bool:
        """Actualizar un prompt específico"""
        try:
            mode_str = mode.value if isinstance(mode, PromptMode) else str(mode)
            
            # Actualizar cache local
            self.prompts_cache[mode_str] = config
            
            # Actualizar Redis
            if self.redis_client:
                redis_key = f"{self.REDIS_PREFIX}{mode_str}"
                await self.redis_client.set(
                    redis_key,
                    config.model_dump_json(),
                    ex=86400  # 24 horas
                )
            
            logger.info(f"✅ Updated prompt for mode: {mode_str}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating prompt: {e}")
            return False
    
    async def reload_prompts(self) -> bool:
        """Recargar prompts desde YAML (hot reload)"""
        logger.info("🔄 Reloading prompts from YAML...")
        success = await self.load_prompts_from_yaml()
        
        if success:
            logger.info("✅ Prompts reloaded successfully")
        else:
            logger.error("❌ Failed to reload prompts")
            
        return success
    
    async def create_default_prompts_yaml(self):
        """Crear archivo YAML por defecto si no existe"""
        default_yaml_content = {
            "version": "1.0.0",
            "description": "Configuración de prompts para Healthcare Chatbot",
            "last_updated": datetime.now().isoformat(),
            "prompts": {
                "medical": {
                    "system_prompt": """Eres un asistente médico profesional con acceso a bases de datos médicas y herramientas de búsqueda.
Puedes buscar información en FDA, PubMed, ensayos clínicos y códigos ICD-10.
Proporciona información médica precisa, empática y profesional.
Siempre recomienda consultar con profesionales de la salud para decisiones médicas.
Responde en el mismo idioma que te preguntaron (español o inglés).
Utiliza markdown para estructurar tus respuestas de manera clara y profesional.
Incluye disclaimers médicos apropiados.""",
                    "temperature": 0.1,
                    "max_tokens": 1000,
                    "description": "Asistente médico general con acceso a herramientas"
                },
                "pediatric": {
                    "system_prompt": """Eres un especialista en medicina pediátrica con acceso a bases de datos médicas.
Proporciona información médica específica para bebés, niños y adolescentes.
Considera siempre las diferencias de dosificación por edad y peso.
Usa lenguaje comprensible para padres y cuidadores.
Enfatiza la importancia de consultar con pediatras.
Responde en el idioma de la consulta.""",
                    "temperature": 0.05,
                    "max_tokens": 800,
                    "description": "Especialista en pediatría"
                },
                "emergency": {
                    "system_prompt": """Eres un médico de urgencias con acceso a información médica actualizada.
PRIORIZA información crítica y signos de alarma.
Proporciona respuestas CONCISAS y DIRECTAS.
Indica claramente cuándo buscar atención médica INMEDIATA.
Usa un tono profesional pero tranquilizador.
En casos graves, recomienda llamar a emergencias.""",
                    "temperature": 0.0,
                    "max_tokens": 600,
                    "description": "Medicina de urgencias - respuestas críticas"
                },
                "pharmacy": {
                    "system_prompt": """Eres un farmacéutico especializado con acceso a bases de datos de medicamentos.
Proporciona información DETALLADA sobre:
- Medicamentos y principios activos
- Dosificación y administración
- Interacciones medicamentosas
- Efectos secundarios y contraindicaciones
- Almacenamiento y conservación
Enfócate en la SEGURIDAD farmacológica.
Siempre recomienda consultar con farmacéuticos o médicos.""",
                    "temperature": 0.1,
                    "max_tokens": 1200,
                    "description": "Farmacología especializada"
                },
                "general": {
                    "system_prompt": """Eres un asistente de salud general amigable y accesible.
Proporciona información básica sobre salud, bienestar y prevención.
Mantén un tono amigable pero profesional.
Enfoca en hábitos saludables y cuidado preventivo.
Para síntomas específicos o diagnósticos, SIEMPRE deriva a profesionales.
Responde de manera clara y comprensible.""",
                    "temperature": 0.2,
                    "max_tokens": 800,
                    "description": "Asistente de salud general"
                }
            }
        }
        
        try:
            with open(self.yaml_path, 'w', encoding='utf-8') as file:
                yaml.dump(default_yaml_content, file, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"✅ Created default prompts.yml at {self.yaml_path}")
            
        except Exception as e:
            logger.error(f"❌ Error creating default YAML: {e}")
            raise
    
    async def get_prompts_info(self) -> Dict[str, Any]:
        """Obtener información sobre prompts cargados"""
        return {
            "version": self.version,
            "last_loaded": self.last_loaded.isoformat() if self.last_loaded else None,
            "prompts_count": len(self.prompts_cache),
            "available_modes": list(self.prompts_cache.keys()),
            "yaml_path": str(self.yaml_path),
            "yaml_exists": self.yaml_path.exists(),
            "redis_connected": self.redis_client is not None
        }
    
    async def delete_prompt(self, mode: PromptMode) -> bool:
        """Eliminar un prompt (solo de Redis, no del YAML)"""
        try:
            mode_str = mode.value if isinstance(mode, PromptMode) else str(mode)
            
            # Remover de cache local
            if mode_str in self.prompts_cache:
                del self.prompts_cache[mode_str]
            
            # Remover de Redis
            if self.redis_client:
                redis_key = f"{self.REDIS_PREFIX}{mode_str}"
                await self.redis_client.delete(redis_key)
            
            logger.info(f"✅ Deleted prompt: {mode_str}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting prompt: {e}")
            return False
    
    async def cleanup(self):
        """Limpiar recursos"""
        logger.info("🧹 Cleaning up PromptManager...")
        self.prompts_cache.clear()

# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_prompt_manager_instance: Optional[PromptManager] = None

async def get_prompt_manager(redis_client: redis.Redis = None) -> PromptManager:
    """Obtener instancia singleton del PromptManager"""
    global _prompt_manager_instance
    
    if _prompt_manager_instance is None:
        _prompt_manager_instance = PromptManager(redis_client)
        await _prompt_manager_instance.initialize()
    
    return _prompt_manager_instance

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def hot_reload_prompts() -> bool:
    """Función de utilidad para hot reload"""
    if _prompt_manager_instance:
        return await _prompt_manager_instance.reload_prompts()
    return False

async def get_prompt_for_mode(mode: PromptMode) -> PromptConfig:

    """Función de utilidad para obtener prompt"""
    manager = await get_prompt_manager()
    return await manager.get_prompt(mode)

async def get_extraction_prompt(self, tool_type: ToolType) -> str:
    """Obtener prompt de extracción de términos desde YAML"""
    try:
        # Recargar YAML si es necesario para obtener extraction_prompts
        if not hasattr(self, 'extraction_prompts_cache'):
            await self.load_prompts_from_yaml()
        
        tool_name = tool_type.value
        
        # Obtener desde cache de extraction_prompts
        if hasattr(self, 'extraction_prompts_cache') and tool_name in self.extraction_prompts_cache:
            return self.extraction_prompts_cache[tool_name]
        
        logger.warning(f"Extraction prompt not found for {tool_name}")
        return f"Extract medical term from: {{message}}"
        
    except Exception as e:
        logger.error(f"Error getting extraction prompt: {e}")
        return f"Extract medical term from: {{message}}"