from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import httpx
import time

from database import engine, get_db
import models, auth

# Configuración de seguridad compatible
security = HTTPBearer()

# Creamos las tablas en la DB al iniciar (solo para la demo/prueba inicial)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ADM Modular Gateway - Production Ready")

# Habilitar CORS para el Sandbox
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuración de Módulos (Los 4 Chats) ---
# En producción, estas URLs vendrían de variables de entorno
CHAT_MODULES = {
    "chat1": "http://gm-general-chat:7005",  # Especialista Clínico General
    "chat2": "http://gm-ch-summary:7006",  # Resumen de Historias Clínicas
    "chat3": "http://gm-voice:7007",  # Extractor Voz-a-JSON
    "chat4": "http://gm-diagnosis:7008",  # Agente de Diagnóstico
}


# --- El Portero (Compatible con Bearer Token) ---
async def validate_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Verifica el token que viene como 'Bearer hcg_...'"""
    token_str = credentials.credentials
    db_token = db.query(models.Token).filter(models.Token.token == token_str).first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o no autorizado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return db_token


# --- Rutas COMPATIBLES (Alias amigables para el cliente) ---
@app.post("/medical/chat")
async def legacy_chat_proxy(
    request_data: dict,
    token: models.Token = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """Alias amigable: mapea /medical/chat -> Chat 1 (Asistente Médico General)"""
    return await modular_chat_proxy("chat1", request_data, token, db)


@app.post("/medical/summary")
async def summary_chat_proxy(
    request_data: dict,
    token: models.Token = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """Alias amigable: mapea /medical/summary -> Chat 2 (Resumen de Historia Clínica)"""
    return await modular_chat_proxy("chat2", request_data, token, db)


# --- Rutas de los Chats (El Proxy Modular) ---
@app.post("/v1/{module_id}/chat")
async def modular_chat_proxy(
    module_id: str,
    request_data: dict,
    token: models.Token = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    # 1. Validar que el módulo exista
    if module_id not in CHAT_MODULES:
        raise HTTPException(status_code=404, detail="Módulo de chat no encontrado")

    target_url = f"{CHAT_MODULES[module_id]}/chat"

    # 2. Re-enviar la petición al backend correspondiente
    start_time = time.time()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(target_url, json=request_data, timeout=60.0)
            data = response.json()

            # 3. Registro Contable (Contador de uso)
            usage = data.get("usage") or {}
            total_tokens = usage.get("total_tokens", 0)

            # Capturar metadatos del auditor para revisión profesional
            auditor_data = data.get("data", {})
            auditor_alert = bool(auditor_data.get("auditor_alert", False)) or bool(auditor_data.get("auditor_intercept", False))
            session_id = data.get("session_id", None)
            prompt_snippet = None
            if "promptData" in request_data:
                prompt_snippet = str(request_data["promptData"])[:200]
            elif "message" in request_data:
                prompt_snippet = str(request_data["message"])[:200]

            new_log = models.APILog(
                token_id=token.id,
                endpoint=module_id,
                total_tokens=total_tokens,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                auditor_alert=auditor_alert,
                session_id=session_id,
                prompt_snippet=prompt_snippet,
            )
            db.add(new_log)

            # Actualizar el acumulado del cliente
            token.total_tokens_consumed += total_tokens
            db.commit()

            return data

    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Error conectando con el módulo {module_id}"
        )


@app.get("/health")
def health_check():
    return {"status": "online", "modules_active": list(CHAT_MODULES.keys())}


# --- Management Endpoints (Solo para el Sandbox/Admin) ---


@app.get("/admin/tokens")
async def list_tokens(db: Session = Depends(get_db)):
    # Unimos con la tabla User para obtener los roles
    tokens = (
        db.query(
            models.Token.token,
            models.Token.name,
            models.User.username,
            models.User.role,
        )
        .join(models.User)
        .all()
    )
    # Convertir a dict para JSON
    return [
        {"token": t.token, "name": t.name, "user": t.username, "role": t.role}
        for t in tokens
    ]


@app.post("/admin/tokens")
async def create_token(data: dict, db: Session = Depends(get_db)):
    # Crear o encontrar usuario
    username = data.get("username", "demo_user")
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = models.User(username=username, role="user")
        db.add(user)
        db.commit()
        db.refresh(user)

    # Crear el token
    import uuid

    new_token_str = f"hcg_{uuid.uuid4().hex[:12]}"
    token = models.Token(
        token=new_token_str, user_id=user.id, name=data.get("name", "Generated Token")
    )
    db.add(token)
    db.commit()
    return {"token": token.token, "name": token.name}


@app.get("/admin/logs")
async def get_logs(db: Session = Depends(get_db)):
    logs = (
        db.query(models.APILog).order_by(models.APILog.timestamp.desc()).limit(10).all()
    )
    return logs


@app.get("/admin/flagged-queries")
async def get_flagged_queries(db: Session = Depends(get_db)):
    """Lista todas las consultas marcadas como peligrosas por el auditor.
    El profesional puede usar el session_id para ver la traza completa
    en GET /admin/trace/{session_id} y enviar su feedback a POST /audit/feedback."""
    flagged = (
        db.query(models.APILog)
        .filter(models.APILog.auditor_alert == True)
        .order_by(models.APILog.timestamp.desc())
        .all()
    )
    return [
        {
            "id": log.id,
            "timestamp": str(log.timestamp),
            "endpoint": log.endpoint,
            "session_id": log.session_id,
            "prompt_snippet": log.prompt_snippet,
            "tokens": log.total_tokens,
            "trace_url": f"/admin/trace/{log.session_id}" if log.session_id else None,
            "feedback_url": "/audit/feedback  [POST]",
        }
        for log in flagged
    ]

@app.get("/admin/usage/{token_str}")
async def get_token_usage(token_str: str, db: Session = Depends(get_db)):
    """Consulta el consumo total de tokens de una API Key específica"""
    token = db.query(models.Token).filter(models.Token.token == token_str).first()
    if not token:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    logs = db.query(models.APILog).filter(models.APILog.token_id == token.id).all()
    return {
        "token": token_str,
        "name": token.name,
        "total_tokens_consumed": token.total_tokens_consumed,
        "calls": len(logs),
        "log_detail": [
            {"endpoint": l.endpoint, "tokens": l.total_tokens, "timestamp": str(l.timestamp)}
            for l in logs
        ]
    }


@app.get("/admin/trace/{session_id}")
async def get_audit_trace(session_id: str):
    """Proxy para obtener el trazo completo desde el módulo de chat"""
    target_url = f"{CHAT_MODULES['chat1']}/audit/trace/{session_id}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(target_url, timeout=5.0)
            return response.json()
        except Exception:
            return {"error": "Trace not available"}
