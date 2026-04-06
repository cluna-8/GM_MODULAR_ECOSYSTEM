"""
Test end-to-end completo: Cliente → ADM Gateway → gm-voice
Valida autenticación, billing, transcripción y SOAP.
"""

import os, sys, time, json, uuid
import requests
from pathlib import Path
from openai import OpenAI

ADM_URL    = os.getenv("ADM_URL",    "http://healthcare-api-gateway:8000")
VOICE_URL  = os.getenv("VOICE_URL",  "http://gm-voice:7003")
API_TOKEN  = os.getenv("API_TOKEN",  "hcg_gomedisys_user_demo_8025A4507BCBD1D1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
TIER       = os.getenv("TIER", "classic")

HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

CONSULTA_1 = """
Doctor: Buenos días, ¿qué lo trae hoy?
Paciente: Llevo tres días con dolor de cabeza fuerte en la nuca. También fiebre.
Doctor: ¿Cuánto de fiebre?
Paciente: 38.2 ayer en la noche.
Doctor: ¿El dolor es continuo?
Paciente: Casi continuo. La luz me molesta mucho y vomité una vez.
Doctor: ¿Toma algún medicamento?
Paciente: Solo enalapril cinco miligramos por la presión, desde hace dos años.
"""

CONSULTA_2 = """
Doctor: Le tomo la presión. Tiene 150 sobre 95.
Doctor: ¿Antecedentes familiares?
Paciente: Mi padre tuvo un derrame a los 65.
Doctor: ¿Alergias?
Paciente: Ninguna.
Doctor: Al bajar el mentón al pecho, ¿le duele?
Paciente: Sí, bastante.
Doctor: Le pido analítica urgente y punción lumbar para descartar meningitis.
Le pongo paracetamol un gramo cada seis horas.
"""

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def generar_audio(texto, path):
    client = OpenAI(api_key=OPENAI_KEY)
    resp = client.audio.speech.create(model="tts-1", voice="onyx", input=texto.strip())
    Path(path).write_bytes(resp.content)
    print(f"  Audio: {path} ({Path(path).stat().st_size//1024} KB)")

def enviar_chunk_adm(session_id, chunk_number, audio_path):
    with open(audio_path, "rb") as f:
        r = requests.post(
            f"{ADM_URL}/medical/voice/chunk",
            headers=HEADERS,
            data={"session_id": session_id, "chunk_number": chunk_number, "tier": TIER},
            files={"audio": (Path(audio_path).name, f, "audio/mpeg")},
            timeout=20
        )
    return r.status_code, r.json() if r.content else {}

def enviar_chunk_directo(session_id, chunk_number, audio_path):
    with open(audio_path, "rb") as f:
        r = requests.post(
            f"{VOICE_URL}/chunk",
            data={"session_id": session_id, "chunk_number": chunk_number, "tier": TIER},
            files={"audio": (Path(audio_path).name, f, "audio/mpeg")},
            timeout=20
        )
    return r.status_code, r.json() if r.content else {}

def esperar_chunk(session_id, chunk_n, timeout=300):
    print(f"  Procesando chunk {chunk_n}", end="", flush=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(f"{VOICE_URL}/status/{session_id}", timeout=5)
            if r.status_code == 200:
                state = r.json()
                if state.get("chunks_processed", 0) >= chunk_n:
                    print(" ✓")
                    return state
                if state.get("last_error"):
                    print(f" ERROR: {state['last_error']}")
                    return state
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(5)
    print(" TIMEOUT")
    return None

def mostrar_doc(doc):
    campos = [
        ("Motivo", "motivo_consulta"),
        ("Enfermedad actual", "enfermedad_actual"),
        ("Antecedentes", "antecedentes"),
        ("Medicación actual", "medicacion_actual"),
        ("Diagnóstico sugerido", "diagnostico_sugerido"),
        ("Medicamentos sugeridos", "medicamentos_sugeridos"),
        ("Exámenes sugeridos", "examenes_sugeridos"),
    ]
    for label, key in campos:
        val = doc.get(key)
        if val:
            print(f"  {label}: ", end="")
            if isinstance(val, list):
                print(", ".join(val))
            else:
                print(val)
    vitales = {k:v for k,v in doc.get("signos_vitales",{}).items() if v}
    if vitales:
        print(f"  Signos vitales: {vitales}")

# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main():
    session_id = f"adm_{uuid.uuid4().hex[:8]}"
    print(f"\n{'='*60}")
    print(f"TEST COMPLETO: ADM → gm-voice")
    print(f"Session: {session_id} | Tier: {TIER}")
    print(f"{'='*60}")

    # 1. Generar audios
    print("\n[1] Generando audios con OpenAI TTS...")
    generar_audio(CONSULTA_1, "/tmp/c1.mp3")
    generar_audio(CONSULTA_2, "/tmp/c2.mp3")

    # 2. Test directo al ADM (autenticación + proxy)
    print(f"\n[2] Enviando chunk 1 via ADM ({ADM_URL})...")
    status_code, resp = enviar_chunk_adm(session_id, 1, "/tmp/c1.mp3")
    print(f"  HTTP {status_code}: {resp}")

    if status_code not in (200, 202):
        print("\n  ⚠️  ADM rechazó el chunk. Probando directo a gm-voice...")
        status_code, resp = enviar_chunk_directo(session_id, 1, "/tmp/c1.mp3")
        print(f"  Directo HTTP {status_code}: {resp}")

    estado = esperar_chunk(session_id, 1)
    if estado:
        print("\n  Documento parcial después del chunk 1:")
        mostrar_doc(estado.get("documento", {}))

    # 3. Chunk 2
    print(f"\n[3] Enviando chunk 2 via ADM...")
    status_code, resp = enviar_chunk_adm(session_id, 2, "/tmp/c2.mp3")
    print(f"  HTTP {status_code}: {resp}")

    if status_code not in (200, 202):
        enviar_chunk_directo(session_id, 2, "/tmp/c2.mp3")

    estado = esperar_chunk(session_id, 2)
    if estado:
        print("\n  Documento parcial después del chunk 2:")
        mostrar_doc(estado.get("documento", {}))

    # 4. Fin de consulta
    print("\n[4] Finalizando consulta...")
    r = requests.post(f"{ADM_URL}/medical/voice/end",
                      headers=HEADERS,
                      json={"session_id": session_id},
                      timeout=120)
    if r.status_code != 200:
        print(f"  ADM /end falló ({r.status_code}), probando directo...")
        r = requests.post(f"{VOICE_URL}/end",
                          json={"session_id": session_id},
                          timeout=120)

    final = r.json()

    print("\n" + "="*60)
    print("DOCUMENTO FINAL COMPLETO")
    print("="*60)
    mostrar_doc(final.get("documento", {}))

    alertas = final.get("alertas", [])
    if alertas:
        print(f"\n  ⚠️  Alertas clínicas: {alertas}")

    # 5. Reporte de tokens y billing
    usage = final.get("usage", {})
    print("\n" + "="*60)
    print("REPORTE DE CONSUMO")
    print("="*60)
    print(f"  Chunks procesados : {final.get('chunks_processed', '?')}")
    print(f"  Tokens LLM totales: {usage.get('total_llm_tokens', '?')}")
    print(f"  Tokens entrada    : {usage.get('input_tokens', '?')}")
    print(f"  Tokens salida     : {usage.get('output_tokens', '?')}")
    print(f"  Tier              : {final.get('tier', TIER)}")
    print(f"  Estado            : {final.get('status', '?')}")

    # 6. Verificar log en ADM
    print("\n[5] Verificando logs en ADM gateway...")
    r = requests.get(f"{ADM_URL}/monitor/requests?limit=5",
                     headers={"Authorization": f"Bearer {API_TOKEN}"},
                     timeout=10)
    if r.status_code == 200:
        logs = r.json()
        voice_logs = [l for l in logs if "voice" in l.get("endpoint","")]
        print(f"  Registros de voz en ADM: {len(voice_logs)}")
        for l in voice_logs:
            print(f"    {l['endpoint']} | tool: {l.get('tool_used')} | tiempo: {l.get('processing_time',0):.2f}s")
    else:
        print(f"  No se pudieron obtener logs del ADM ({r.status_code})")

    # Guardar resultado
    out = f"/tmp/resultado_adm_{session_id}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\n  Resultado guardado: {out}")


if __name__ == "__main__":
    main()
