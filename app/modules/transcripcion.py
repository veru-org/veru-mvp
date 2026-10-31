import time
import whisper

_modelo = None


def get_modelo(nombre: str = "small"):
    global _modelo
    if _modelo is None:
        _modelo = whisper.load_model(nombre)
    return _modelo


def transcribir(video_path: str, idioma: str = "es") -> dict:
    inicio = time.time()
    r = get_modelo().transcribe(video_path, language=idioma, fp16=False)
    return {
        "texto": r["text"].strip(),
        "segmentos": [
            {"inicio": round(s["start"], 1), "fin": round(s["end"], 1),
             "texto": s["text"].strip()}
            for s in r["segments"]
        ],
        "tiempo_proceso_seg": round(time.time() - inicio, 1),
    }