"""
Script de prueba end-to-end para gm-voice.
1. Genera audio de consulta médica simulada con OpenAI TTS
2. Divide el audio en chunks y los envía al servicio
3. Hace polling del documento parcial entre chunks
4. Llama a /end y muestra el documento final
5. Reporta tokens consumidos
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VOICE_URL = os.getenv("VOICE_URL", "http://localhost:7003")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TIER = "classic"

# Consulta médica simulada en dos partes (simula dos chunks de ~3 min)
CONSULTA_PARTE_1 = """
Doctor: Buenos días, ¿qué lo trae por aquí hoy?
Paciente: Doctora, llevo tres días con un dolor de cabeza muy fuerte, sobre todo en la nuca.
También tengo algo de fiebre.
Doctor: ¿Cuánto de fiebre? ¿Lo midió?
Paciente: Sí, ayer en la noche tenía treinta y ocho punto dos.
Doctor: ¿El dolor es continuo o va y viene?
Paciente: Es casi continuo. Con la luz me molesta más.
Doctor: ¿Tiene náuseas o vómitos?
Paciente: Sí, ayer vomité una vez.
Doctor: ¿Toma algún medicamento habitualmente?
Paciente: Solo enalapril, cinco miligramos, por la presión alta. La tengo desde hace dos años.
"""

CONSULTA_PARTE_2 = """
Doctor: Voy a tomarle la presión. Tiene ciento cincuenta sobre noventa y cinco. Un poco elevada.
¿Ha tenido episodios similares antes?
Paciente: Una vez hace un año, pero no tan fuerte.
Doctor: ¿Alguna alergia a medicamentos?
Paciente: No, ninguna.
Doctor: ¿Antecedentes familiares de problemas neurológicos o cardíacos?
Paciente: Mi padre tuvo un derrame cerebral a los sesenta y cinco.
Doctor: Voy a explorarle el cuello. ¿Le duele cuando intenta bajar el mentón hacia el pecho?
Paciente: Sí, bastante.
Doctor: Bien. Le voy a pedir una analítica urgente y una punción lumbar para descartar meningitis.
Por ahora le pongo paracetamol un gramo cada seis horas para el dolor y la fiebre.
"""


def generar_audio(texto: str, archivo: str, voice: str = "alloy"):
    """Genera un archivo de audio MP3 usando OpenAI TTS."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    print(f"  Generando audio: {archivo}...")
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=texto.strip()
    )
    Path(archivo).write_bytes(response.content)
    size_kb = Path(archivo).stat().st_size // 1024
    print(f"  Audio generado: {size_kb} KB")


def health_check():
    """Verifica que el servicio esté activo."""
    try:
        r = requests.get(f"{VOICE_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False


def enviar_chunk(session_id: str, chunk_number: int, audio_path: str, tier: str = "classic"):
    """Envía un chunk de audio al servicio."""
    with open(audio_path, "rb") as f:
        r = requests.post(
            f"{VOICE_URL}/chunk",
            data={
                "session_id": session_id,
                "chunk_number": chunk_number,
                "tier": tier
            },
            files={"audio": (Path(audio_path).name, f, "audio/mpeg")},
            timeout=15
        )
    r.raise_for_status()
    return r.json()


def obtener_estado(session_id: str):
    """Consulta el estado actual del documento."""
    r = requests.get(f"{VOICE_URL}/status/{session_id}", timeout=10)
    r.raise_for_status()
    return r.json()


def finalizar_consulta(session_id: str):
    """Señala el fin de la consulta y obtiene el documento consolidado."""
    r = requests.post(
        f"{VOICE_URL}/end",
        json={"session_id": session_id},
        timeout=120
    )
    r.raise_for_status()
    return r.json()


def esperar_chunk_procesado(session_id: str, chunk_number: int, timeout: int = 300):
    """Hace polling hasta que el chunk haya sido procesado."""
    print(f"  Esperando procesamiento del chunk {chunk_number}...", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        estado = obtener_estado(session_id)
        if estado.get("chunks_processed", 0) >= chunk_number:
            print(" listo")
            return estado
        if estado.get("last_error"):
            print(f" ERROR: {estado['last_error']}")
            return estado
        print(".", end="", flush=True)
        time.sleep(5)
    print(" TIMEOUT")
    return None


def mostrar_documento(estado: dict):
    """Imprime el documento clínico de forma legible."""
    doc = estado.get("documento", {})
    print("\n" + "="*60)
    print("DOCUMENTO CLÍNICO PARCIAL")
    print("="*60)
    campos = [
        ("Motivo de consulta", "motivo_consulta"),
        ("Enfermedad actual", "enfermedad_actual"),
        ("Antecedentes", "antecedentes"),
        ("Medicación actual", "medicacion_actual"),
        ("Diagnóstico sugerido", "diagnostico_sugerido"),
        ("Medicamentos sugeridos", "medicamentos_sugeridos"),
        ("Exámenes sugeridos", "examenes_sugeridos"),
    ]
    for label, key in campos:
        valor = doc.get(key)
        if valor:
            print(f"\n{label}:")
            if isinstance(valor, list):
                for item in valor:
                    print(f"  - {item}")
            else:
                print(f"  {valor}")

    vitales = doc.get("signos_vitales", {})
    vitales_activos = {k: v for k, v in vitales.items() if v}
    if vitales_activos:
        print("\nSignos vitales:")
        for k, v in vitales_activos.items():
            print(f"  {k}: {v}")

    alertas = estado.get("alertas", [])
    if alertas:
        print("\n⚠️  ALERTAS CLÍNICAS:")
        for a in alertas:
            print(f"  ! {a}")


def mostrar_tokens(estado: dict):
    """Muestra el resumen de tokens consumidos."""
    usage = estado.get("usage", {})
    chunks = estado.get("chunks_processed", 0)
    print("\n" + "="*60)
    print("RESUMEN DE CONSUMO")
    print("="*60)
    print(f"  Chunks procesados : {chunks}")
    print(f"  Tokens LLM totales: {usage.get('total_llm_tokens', 'no registrado')}")
    print(f"  Tokens entrada    : {usage.get('input_tokens', 'no registrado')}")
    print(f"  Tokens salida     : {usage.get('output_tokens', 'no registrado')}")
    print(f"  Tier usado        : {estado.get('tier', 'classic')}")
    print(f"  Estado final      : {estado.get('status')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import uuid

    print(f"\n🔍 Verificando servicio gm-voice en {VOICE_URL}...")
    if not health_check():
        print(f"❌ El servicio no responde en {VOICE_URL}")
        print("   Levantalo con: docker compose up -d")
        sys.exit(1)
    print("✅ Servicio activo")

    session_id = f"test_{uuid.uuid4().hex[:8]}"
    print(f"\n📋 Session ID: {session_id}")
    print(f"   Tier: {TIER}\n")

    # 1. Generar audios
    print("🎙️  Generando audios de prueba...")
    generar_audio(CONSULTA_PARTE_1, "/tmp/chunk1.mp3", voice="onyx")
    generar_audio(CONSULTA_PARTE_2, "/tmp/chunk2.mp3", voice="onyx")

    # 2. Enviar chunk 1
    print("\n📤 Enviando chunk 1 (anamnesis inicial)...")
    resp = enviar_chunk(session_id, 1, "/tmp/chunk1.mp3", TIER)
    print(f"  Respuesta: {resp}")

    # 3. Polling chunk 1
    estado = esperar_chunk_procesado(session_id, 1)
    if estado:
        mostrar_documento(estado)

    # 4. Enviar chunk 2
    print("\n📤 Enviando chunk 2 (exploración y plan)...")
    resp = enviar_chunk(session_id, 2, "/tmp/chunk2.mp3", TIER)
    print(f"  Respuesta: {resp}")

    # 5. Polling chunk 2
    estado = esperar_chunk_procesado(session_id, 2)
    if estado:
        mostrar_documento(estado)

    # 6. Finalizar consulta
    print("\n🏁 Finalizando consulta...")
    final = finalizar_consulta(session_id)
    mostrar_documento(final)
    mostrar_tokens(final)

    # 7. Guardar resultado completo
    output_path = f"/tmp/resultado_{session_id}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Resultado completo guardado en: {output_path}")


if __name__ == "__main__":
    main()
