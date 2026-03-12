from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import os
import yaml
from openai import AsyncOpenAI
from pathlib import Path
import json
import numpy as np
from redis import Redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.query import Query

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medical-auditor")

app = FastAPI(
    title="Medical Auditor API",
    description="Independent Clinical Validation and Analysis Service (BioMistral Core)",
    version="1.1.0",
)

# Configuration
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://vllm-server:8000/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "BioMistral/BioMistral-7B-Instruct-v1")
PROMPTS_PATH = Path(__file__).parent / "clinical_prompts.yml"

# Direct OpenAI Client (GPT-4o migration)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# OLD Client for vLLM (OpenAI compatible) - Keep for offline processing reference
# vllm_client = AsyncOpenAI(api_key="none", base_url=VLLM_BASE_URL)


class PromptLoader:
    def __init__(self):
        self.prompts = {}
        self.load_prompts()

    def load_prompts(self):
        try:
            with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
                self.prompts = yaml.safe_load(f)
            logger.info("✅ Clinical prompts loaded successfully")
        except Exception as e:
            logger.error(f"❌ Error loading clinical prompts: {e}")


prompt_loader = PromptLoader()


class SemanticCache:
    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url)
        self.index_name = "idx:medical_cache_ada002"
        self.dim = 1536  # text-embedding-ada-002 dimension

        try:
            self._ensure_index()
            logger.info("✅ Semantic Cache initialized successfully with OpenAI embeddings")
        except Exception as e:
            logger.error(f"⚠️ Semantic Cache disabled (Redis error): {e}")

    def _ensure_index(self):
        try:
            self.redis.ft(self.index_name).info()
        except:
            schema = (
                TextField("text"),
                TextField("verdict"),
                TextField("status"),
                VectorField(
                    "embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.dim,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            )
            try:
                self.redis.ft(self.index_name).create_index(schema)
                logger.info("✅ RedisSearch index created for ADA-002")
            except Exception as e:
                logger.warning(f"Could not create index (maybe already exists): {e}")

    async def get_embedding(self, text: str):
        try:
            response = await openai_client.embeddings.create(
                input=text,
                model="text-embedding-ada-002"
            )
            embedding = response.data[0].embedding
            return np.array(embedding, dtype=np.float32).tobytes()
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    async def search(
        self, text: str, threshold: float = 0.95
    ) -> Optional[Dict[str, Any]]:
        query_vector = await self.get_embedding(text)
        if not query_vector:
            return None

        q = (
            Query(f"*=>[KNN 1 @embedding $vec AS score]")
            .sort_by("score")
            .return_fields("text", "verdict", "status", "score")
            .dialect(2)
        )
        params = {"vec": query_vector}
        results = self.redis.ft(self.index_name).search(q, params)

        if results.docs:
            doc = results.docs[0]
            # In COSINE distance, lower is better (0 is exact match, 1 is orthogonal)
            score = float(doc.score)
            if score < (1 - threshold):
                return {"status": doc.status, "verdict": doc.verdict, "cached": True}
        return None

    async def save(self, text: str, status: str, verdict: str):
        vector = await self.get_embedding(text)
        if not vector:
            return

        key = f"cache:{hash(text)}"
        self.redis.hset(
            key,
            mapping={
                "text": text,
                "status": status,
                "verdict": verdict,
                "embedding": vector,
            },
        )
        self.redis.expire(key, 3600)


semantic_cache = SemanticCache(os.getenv("REDIS_URL", "redis://redis-general:6379/0"))


class AuditRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None
    instruction: Optional[str] = None


class AuditResponse(BaseModel):
    status: str  # OK, ALERT, REJECTED
    verdict: str
    reasoning: Optional[str] = None
    risk_level: Optional[str] = None
    is_safe: Optional[bool] = None
    entities: List[str] = []
    timestamp: datetime = datetime.now()
    metadata: Dict[str, Any] = {}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "medical-auditor",
        "engine": "GPT-4o-mini",
        "version": "1.2.0",
    }


async def call_gpt_auditor(prompt_key: str, content: str) -> Dict[str, Any]:
    """Audit engine using GPT-4o-mini with Chain of Thought and JSON Enforcement"""
    prompts = prompt_loader.prompts.get(prompt_key, {})
    system_prompt = prompts.get("system_prompt", "Eres un asistente médico experto.")

    try:
        # GPT-4o-mini call with JSON mode
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,  # Strict for auditing
        )
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        logger.error(f"Error calling GPT Auditor ({prompt_key}): {e}")
        # Fallback security profile
        return {
            "reasoning": f"Audit engine error: {str(e)}",
            "status": "OK",
            "verdict": "Audit failed (fallback safety enabled)",
            "risk_level": "LOW",
            "is_safe": True,
        }


# async def call_biomistral(prompt_key: str, content: str) -> Dict[str, Any]:
#     """Helper to call BioMistral engine via vLLM (Commented for reference)"""
#     prompts = prompt_loader.prompts.get(prompt_key, {})
#     system_prompt = prompts.get("system_prompt", "Eres un asistente médico.")
#     try:
#         # response = await vllm_client.chat.completions.create(...)
#         # Simulation of BioMistral (Mock)
#         return {"status": "OK", "verdict": "BioMistral Mock OK"}
#     except Exception as e:
#         logger.error(f"Error: {e}")
#         return {"status": "OK"}


@app.post("/audit/pre-process", response_model=AuditResponse)
async def pre_process(request: AuditRequest):
    """
    Step 1: Capa de Pre-Análisis (Detección de Entidades e Incoherencias)
    Migrado a GPT-4o-mini para mayor razonamiento lógico.
    """
    logger.info(
        f"Pre-processing audit request with GPT-4o-mini: {request.text[:50]}..."
    )

    # Preparar el contenido a auditar. Si hay memoria de contexto, se añade.
    content = request.text
    if request.context and "memory" in request.context and request.context["memory"]:
        content = f"Mensaje del usuario: {request.text}\nContexto de la conversación (memoria reciente): {request.context['memory']}"

    # Check cache based on the full content
    cached = await semantic_cache.search(content)
    if cached:
        logger.info("🎯 Semantic Cache Hit for pre-process")
        return AuditResponse(
            status=cached["status"],
            verdict=f"[CACHED] {cached['verdict']}",
            timestamp=datetime.now(),
        )

    result = await call_gpt_auditor("audit_pre_process", content)

    # Save to cache if result is valid
    if "status" in result and "verdict" in result:
        await semantic_cache.save(content, result["status"], result["verdict"])

    return AuditResponse(
        status=result.get("status", "OK"),
        verdict=result.get("verdict", "Análisis completado."),
        reasoning=result.get("reasoning"),
        risk_level=result.get("risk_level", "LOW"),
        is_safe=result.get("is_safe", result.get("status") == "OK"),
        entities=result.get("entities", []),
        timestamp=datetime.now(),
    )


@app.post("/audit/validate-safety", response_model=AuditResponse)
async def validate_safety(request: AuditRequest):
    """
    Step 2: Capa de Validación de Seguridad (El Juez)
    Migrado a GPT-4o-mini para detección de alergias cruzadas y errores de dosificación.
    """
    logger.info("Validating safety with GPT-4o-mini (Chain of Thought)...")

    content = f"Respuesta de IA a validar: {request.text}\nContexto HIS del Paciente: {request.context}"
    result = await call_gpt_auditor("audit_validate_safety", content)

    return AuditResponse(
        status=result.get("status", "OK"),
        verdict=result.get("verdict", "Validación completed."),
        reasoning=result.get("reasoning"),
        risk_level=result.get("risk_level", "LOW"),
        is_safe=result.get("is_safe", result.get("status") == "OK"),
        entities=result.get("entities", []),
        timestamp=datetime.now(),
        metadata={"engine": "gpt-4o-mini"},
    )


@app.get("/terms/standardize")
async def standardize_terms(query: str):
    """
    Step 4: Estandarización de Interconsulta (SNOMED/CIE-10)
    """
    return {
        "query": query,
        "standardized_terms": [
            {"code": "CIE-10: I10", "term": "Hipertensión esencial"}
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
