import asyncio
import logging
import os
import httpx

logger = logging.getLogger(__name__)

SPEECHMATICS_API_KEY = os.getenv("SPEECHMATICS_API_KEY", "")
SPEECHMATICS_URL = "https://asr.api.speechmatics.com/v2"


class Transcriber:
    """ASR layer. Dispatches to Classic (Whisper local) or Professional (Speechmatics)."""

    def __init__(self, tier: str, model=None, lock: asyncio.Lock = None):
        self.tier = tier
        self.model = model      # WhisperModel instance (preloaded at startup)
        self.lock = lock        # Serializes CPU calls to Whisper

    async def transcribe(self, audio_path: str) -> str:
        if self.tier == "professional":
            return await self._speechmatics(audio_path)
        return await self._whisper(audio_path)

    # -------------------------------------------------------------------------
    # Classic: faster-whisper en CPU
    # -------------------------------------------------------------------------

    async def _whisper(self, audio_path: str) -> str:
        loop = asyncio.get_event_loop()
        async with self.lock:
            transcript = await loop.run_in_executor(None, self._whisper_sync, audio_path)
        return transcript

    def _whisper_sync(self, audio_path: str) -> str:
        segments, info = self.model.transcribe(
            audio_path,
            language="es",
            vad_filter=True,            # ignora silencios largos
            vad_parameters={"min_silence_duration_ms": 500}
        )
        text = " ".join(s.text.strip() for s in segments)
        logger.info(f"Whisper transcribed {info.duration:.1f}s of audio")
        return text

    # -------------------------------------------------------------------------
    # Professional: Speechmatics Medical REST API
    # -------------------------------------------------------------------------

    async def _speechmatics(self, audio_path: str) -> str:
        if not SPEECHMATICS_API_KEY:
            raise ValueError("SPEECHMATICS_API_KEY not configured")

        headers = {"Authorization": f"Bearer {SPEECHMATICS_API_KEY}"}

        async with httpx.AsyncClient(timeout=300) as client:
            # 1. Submit job
            with open(audio_path, "rb") as f:
                resp = await client.post(
                    f"{SPEECHMATICS_URL}/jobs/",
                    headers=headers,
                    files={"data_file": f},
                    data={
                        "config": '{"type":"transcription","transcription_config":{"language":"es","diarization":"speaker","operating_point":"enhanced"}}'
                    }
                )
            resp.raise_for_status()
            job_id = resp.json()["id"]
            logger.info(f"Speechmatics job submitted: {job_id}")

            # 2. Poll until done
            for _ in range(60):
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"{SPEECHMATICS_URL}/jobs/{job_id}",
                    headers=headers
                )
                job_status = status_resp.json()["job"]["status"]
                if job_status == "done":
                    break
                if job_status == "rejected":
                    raise RuntimeError(f"Speechmatics job rejected: {job_id}")

            # 3. Get transcript
            transcript_resp = await client.get(
                f"{SPEECHMATICS_URL}/jobs/{job_id}/transcript",
                headers=headers,
                params={"format": "txt"}
            )
            transcript_resp.raise_for_status()
            return transcript_resp.text
