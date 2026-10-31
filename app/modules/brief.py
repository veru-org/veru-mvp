import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODELO = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
_cliente = None


def get_cliente():
    global _cliente
    if _cliente is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Falta GEMINI_API_KEY en el .env")
        _cliente = genai.Client(api_key=key)
    return _cliente


PROMPT = """Eres un auditor de contenido de marketing de creadores.
Analiza el video (imagen y audio) y compáralo con el brief de la campaña.

BRIEF:
{brief}

Responde SOLO con JSON válido, sin texto extra, con esta estructura:
{{
  "transcripcion": [{{"inicio": 0.0, "fin": 0.0, "texto": "..."}}],
  "cumple_brief": true,
  "puntos_brief": [
    {{"punto": "requisito del brief", "cumple": true,
      "timestamp": 0.0, "evidencia": "qué se dice o se ve"}}
  ],
  "producto_visible": true,
  "timestamps_producto": [0.0],
  "resumen": "una frase con el motivo del veredicto"
}}
Los tiempos van en segundos. Si algo no se puede determinar, usa null."""


def _generar(cliente, archivo, brief, modelo, intentos=4):
    """Llama a Gemini con reintentos ante errores transitorios (503/429)."""
    for i in range(intentos):
        try:
            return cliente.models.generate_content(
                model=modelo,
                contents=[archivo, PROMPT.format(brief=brief)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.1
                ),
            )
        except Exception as e:
            transitorio = "503" in str(e) or "429" in str(e)
            if not transitorio or i == intentos - 1:
                raise
            time.sleep(3 * (i + 1))


def auditar_brief(video_path: str, brief: str) -> dict:
    inicio = time.time()
    cliente = get_cliente()

    archivo = cliente.files.upload(file=video_path)
    try:
        while archivo.state.name == "PROCESSING":
            time.sleep(1)
            archivo = cliente.files.get(name=archivo.name)
        if archivo.state.name == "FAILED":
            raise RuntimeError("Gemini no pudo procesar el video")

        resp = _generar(cliente, archivo, brief, MODELO)
    finally:
        # Privacidad: no dejar el video almacenado en Gemini
        try:
            cliente.files.delete(name=archivo.name)
        except Exception:
            pass

    datos = json.loads(resp.text)
    datos["tiempo_proceso_seg"] = round(time.time() - inicio, 1)
    return datos