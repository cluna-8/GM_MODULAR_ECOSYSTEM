import asyncio
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile

from auditor_client import validate_suggestions
from structurer import EMPTY_DOCUMENT, consolidate_final, update_document
from transcriber import Transcriber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis-general:6379/0")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "medium")
VOICE_SESSION_TTL = 7200  # 2 hours

redis_client = None
whisper_model = None
whisper_lock = None  # Serializes CPU inference calls


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, whisper_model, whisper_lock

    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    whisper_lock = asyncio.Lock()

    logger.info(f"Loading Whisper model '{WHISPER_MODEL_SIZE}' (CPU, int8)...")
    from faster_whisper import WhisperModel
    whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    logger.info("✅ gm-voice ready")

    yield

    await redis_client.aclose()


app = FastAPI(title="gm-voice", version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

async def get_session(session_id: str) -> dict | None:
    data = await redis_client.get(f"voice:{session_id}")
    return json.loads(data) if data else None


async def save_session(session_id: str, state: dict):
    await redis_client.set(
        f"voice:{session_id}",
        json.dumps(state, ensure_ascii=False),
        ex=VOICE_SESSION_TTL
    )


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------

async def process_chunk(session_id: str, chunk_number: int, tier: str, audio_path: str):
    try:
        transcriber = Transcriber(tier=tier, model=whisper_model, lock=whisper_lock)
        transcript = await transcriber.transcribe(audio_path)
        logger.info(f"[{session_id}] chunk {chunk_number} transcribed ({len(transcript)} chars)")

        state = await get_session(session_id)
        if not state:
            state = {
                "session_id": session_id,
                "tier": tier,
                "status": "processing",
                "chunks_processed": 0,
                "accumulated_transcript": "",
                "documento": dict(EMPTY_DOCUMENT),
                "alertas": []
            }

        state["accumulated_transcript"] += f"\n[Segmento {chunk_number}]: {transcript}"
        state["chunks_processed"] += 1
        state["documento"], usage = await update_document(
            current_doc=state["documento"],
            new_transcript=transcript,
            chunk_number=chunk_number
        )
        state.setdefault("usage", {"input_tokens": 0, "output_tokens": 0, "total_llm_tokens": 0})
        state["usage"]["input_tokens"] += usage["input_tokens"]
        state["usage"]["output_tokens"] += usage["output_tokens"]
        state["usage"]["total_llm_tokens"] += usage["total_tokens"]

        await save_session(session_id, state)

    except Exception as e:
        logger.error(f"[{session_id}] chunk {chunk_number} error: {e}")
        state = await get_session(session_id) or {}
        state["last_error"] = str(e)
        await save_session(session_id, state)

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/chunk", status_code=202)
async def receive_chunk(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    chunk_number: int = Form(...),
    tier: str = Form("classic")
):
    if tier not in ("classic", "professional"):
        raise HTTPException(status_code=400, detail="tier must be 'classic' or 'professional'")

    suffix = os.path.splitext(audio.filename or "audio.mp3")[1] or ".mp3"
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        prefix=f"voice_{session_id}_c{chunk_number}_"
    )
    tmp.write(await audio.read())
    tmp.close()

    # Inicializar sesión en Redis antes de lanzar el background task
    # así el polling no recibe 404 mientras Whisper transcribe
    state = await get_session(session_id)
    if not state:
        await save_session(session_id, {
            "session_id": session_id,
            "tier": tier,
            "status": "processing",
            "chunks_processed": 0,
            "accumulated_transcript": "",
            "documento": dict(EMPTY_DOCUMENT),
            "alertas": [],
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_llm_tokens": 0}
        })

    background_tasks.add_task(process_chunk, session_id, chunk_number, tier, tmp.name)

    return {
        "session_id": session_id,
        "chunk_number": chunk_number,
        "status": "processing"
    }


@app.post("/end")
async def end_consultation(payload: dict):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=422, detail="session_id required")

    state = await get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if state.get("status") == "complete":
        return state

    state["documento"], usage = await consolidate_final(
        documento=state["documento"],
        accumulated_transcript=state["accumulated_transcript"]
    )
    state.setdefault("usage", {"input_tokens": 0, "output_tokens": 0, "total_llm_tokens": 0})
    state["usage"]["input_tokens"] += usage["input_tokens"]
    state["usage"]["output_tokens"] += usage["output_tokens"]
    state["usage"]["total_llm_tokens"] += usage["total_tokens"]

    state["alertas"] = await validate_suggestions(state["documento"])
    state["status"] = "complete"

    await save_session(session_id, state)

    return state


@app.get("/status/{session_id}")
async def get_status(session_id: str):
    state = await get_session(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return state


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "gm-voice", "version": "1.0.0"}
