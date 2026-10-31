import json
import os
import time
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()

MODELO = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MOCK_PATH = "app/mock/brief_baysi.json"
_cliente = None


def get_cliente():
    global _cliente
    if _cliente is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Falta GEMINI_API_KEY en el .env")
        _cliente = genai.Client(api_key=key)
    return _cliente


# ---------- Esquema estricto de la respuesta ----------
class Segmento(BaseModel):
    inicio: float
    fin: float
    texto: str


class Punto(BaseModel):
    requisito: str
    cumple: bool
    tipo_coincidencia: Literal["literal", "equivalente", "ninguna"]
    timestamp: float | None
    evidencia: str


class Resultado(BaseModel):
    transcripcion: list[Segmento]
    puntos: list[Punto]
    producto_visible: bool
    timestamps_producto: list[float]
    resumen: str


# ---------- Prompt ----------
PROMPT = """Eres un auditor de contenido de marketing de creadores.
Analiza el video (imagen y audio) y evalúa EXACTAMENTE los requisitos listados,
ni más ni menos. No agregues requisitos propios.

REQUISITOS:
{requisitos}

Reglas:
- Un requisito con sinónimos aceptados se cumple si se menciona o se ve
  cualquiera de ellos.
- tipo_coincidencia: "literal" si aparece la palabra exacta del requisito,
  "equivalente" si aparece uno de los sinónimos o un concepto claramente
  equivalente, "ninguna" si no cumple.
- Para requisitos visuales (mostrar producto), cumple si el producto o la
  mercadería de la marca es visible en pantalla, aunque sea en un plano
  general; indica el segundo en "timestamp".
- Los tiempos van en segundos. Si no se puede determinar, usa null.
- "producto_visible" indica si el producto de la marca se ve en algún momento;
  "timestamps_producto" lista solo el segundo de inicio y el de fin del tramo
  donde se ve (máximo 2 valores por tramo)."""


def formatear_requisitos(requisitos: list) -> str:
    """Acepta strings o dicts {"texto": "...", "sinonimos": [...]}."""
    lineas = []
    for r in requisitos:
        if isinstance(r, str):
            lineas.append(f"- {r}")
        else:
            sin = r.get("sinonimos") or []
            extra = f" (sinónimos aceptados: {', '.join(sin)})" if sin else ""
            lineas.append(f"- {r['texto']}{extra}")
    return "\n".join(lineas)


def _subir(cliente, video_path, intentos=4):
    """Sube el video con reintentos ante cortes de red."""
    for i in range(intentos):
        try:
            return cliente.files.upload(file=video_path)
        except Exception as e:
            if i == intentos - 1:
                raise
            print(f"[reintento subida {i + 1}] {type(e).__name__}")
            time.sleep(2 * (i + 1))


def _generar(cliente, archivo, requisitos, modelo, intentos=4):
    """Llama a Gemini con reintentos ante errores transitorios (503/429)."""
    prompt = PROMPT.format(requisitos=formatear_requisitos(requisitos))
    for i in range(intentos):
        try:
            return cliente.models.generate_content(
                model=modelo,
                contents=[archivo, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Resultado,
                    temperature=0.0,
                ),
            )
        except Exception as e:
            msg = str(e)
            # Cuota diaria agotada: reintentar no sirve
            if "PerDay" in msg or "per day" in msg.lower():
                raise RuntimeError(
                    "Cuota diaria de Gemini agotada. Cambia de modelo/key "
                    "o activa GEMINI_MOCK=1.") from e
            transitorio = "503" in msg or "429" in msg
            if not transitorio or i == intentos - 1:
                raise
            print(f"[reintento {i + 1}] {type(e).__name__}: error transitorio")
            time.sleep(3 * (i + 1))


def _auditar_mock() -> dict:
    with open(MOCK_PATH, encoding="utf-8") as f:
        datos = json.load(f)
    datos["modelo"] = "MOCK"
    return datos


def auditar_brief(video_path: str, requisitos: list) -> dict:
    # Modo mock: no consume cuota de Gemini
    if os.getenv("GEMINI_MOCK") == "1":
        return _auditar_mock()

    inicio = time.time()
    tiempos = {}
    cliente = get_cliente()

    archivo = _subir(cliente, video_path)
    tiempos["subida_seg"] = round(time.time() - inicio, 1)
    try:
        while archivo.state.name == "PROCESSING":
            time.sleep(1)
            archivo = cliente.files.get(name=archivo.name)
        tiempos["procesado_seg"] = round(time.time() - inicio, 1)
        if archivo.state.name == "FAILED":
            raise RuntimeError("Gemini no pudo procesar el video")

        resp = _generar(cliente, archivo, requisitos, MODELO)
        tiempos["respuesta_seg"] = round(time.time() - inicio, 1)
    finally:
        # Privacidad: no dejar el video almacenado en Gemini
        try:
            cliente.files.delete(name=archivo.name)
        except Exception:
            pass

    datos = json.loads(resp.text)
    datos["cumple_brief"] = all(p["cumple"] for p in datos["puntos"])
    datos["modelo"] = MODELO
    datos["tiempos"] = tiempos
    datos["tiempo_proceso_seg"] = round(time.time() - inicio, 1)

    # Guardar la última respuesta real para usarla como mock
    try:
        os.makedirs(os.path.dirname(MOCK_PATH), exist_ok=True)
        with open(MOCK_PATH, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return datos