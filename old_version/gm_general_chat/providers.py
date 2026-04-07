from enum import Enum
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import os

from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding

class ProviderType(str, Enum):
    AZURE = "azure"
    OPENAI = "openai"

class BaseProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def get_llm(self) -> Any:
        pass
    
    @abstractmethod
    def get_embedding(self) -> Any:
        pass
    
    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        pass

class AzureProvider(BaseProvider):
    """Azure OpenAI provider implementation"""
    
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        self.embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate Azure configuration"""
        if not all([self.endpoint, self.api_key, self.deployment_name]):
            raise ValueError("Missing Azure OpenAI configuration. Check AZURE_OPENAI_* environment variables.")
    
    def get_llm(self) -> AzureOpenAI:
        """Get Azure OpenAI LLM instance"""
        return AzureOpenAI(
            model=self.deployment_name,
            deployment_name=self.deployment_name,
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.api_version,
            temperature=0.1,
            max_tokens=1000,
        )
    
    def get_embedding(self) -> AzureOpenAIEmbedding:
        """Get Azure OpenAI embedding instance"""
        return AzureOpenAIEmbedding(
            model=self.embedding_deployment,
            deployment_name=self.embedding_deployment,
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.api_version,
        )
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information"""
        return {
            "provider": "azure",
            "endpoint": self.endpoint,
            "model": self.deployment_name,
            "embedding_model": self.embedding_deployment,
            "api_version": self.api_version,
            "status": "configured"
        }

class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate OpenAI configuration"""
        if not self.api_key:
            raise ValueError("Missing OpenAI API key. Check OPENAI_API_KEY environment variable.")
    
    def get_llm(self) -> OpenAI:
        """Get OpenAI LLM instance"""
        return OpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=0.1,
            max_tokens=1000,
        )
    
    def get_embedding(self) -> OpenAIEmbedding:
        """Get OpenAI embedding instance"""
        return OpenAIEmbedding(
            model=self.embedding_model,
            api_key=self.api_key,
        )
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information"""
        return {
            "provider": "openai",
            "model": self.model,
            "embedding_model": self.embedding_model,
            "status": "configured"
        }

class ProviderManager:
    """Manages multiple LLM providers and allows switching between them"""
    
    def __init__(self, default_provider: str = None):
        self.providers: Dict[str, BaseProvider] = {}
        self.current_provider: Optional[str] = None
        
        # Initialize available providers
        self._initialize_providers()
        
        # Set default provider
        default = default_provider or os.getenv("DEFAULT_PROVIDER", "azure")
        self.set_provider(default)
    
    def _initialize_providers(self):
        """Initialize all available providers"""
        # Try to initialize Azure provider
        try:
            self.providers["azure"] = AzureProvider()
            print("✅ Azure OpenAI provider initialized")
        except Exception as e:
            print(f"⚠️ Azure OpenAI provider not available: {e}")
        
        # Try to initialize OpenAI provider
        try:
            self.providers["openai"] = OpenAIProvider()
            print("✅ OpenAI provider initialized")
        except Exception as e:
            print(f"⚠️ OpenAI provider not available: {e}")
        
        if not self.providers:
            raise ValueError("No LLM providers could be initialized. Check your configuration.")
    
    def set_provider(self, provider_name: str) -> bool:
        """Switch to a specific provider"""
        if provider_name not in self.providers:
            return False
        
        self.current_provider = provider_name
        print(f"🔄 Switched to {provider_name} provider")
        return True
    
    def get_current_provider(self) -> BaseProvider:
        """Get the current active provider"""
        if not self.current_provider or self.current_provider not in self.providers:
            raise ValueError("No active provider set")
        
        return self.providers[self.current_provider]
    
    def get_available_providers(self) -> list:
        """Get list of available providers"""
        return list(self.providers.keys())
    
    def get_provider_info(self, provider_name: str = None) -> Dict[str, Any]:
        """Get information about a specific provider or current provider"""
        if provider_name:
            if provider_name not in self.providers:
                return {"error": f"Provider {provider_name} not available"}
            return self.providers[provider_name].get_provider_info()
        
        if self.current_provider:
            info = self.get_current_provider().get_provider_info()
            info["is_current"] = True
            return info
        
        return {"error": "No active provider"}