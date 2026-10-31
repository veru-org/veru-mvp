import re
import time
from difflib import SequenceMatcher

import cv2
import easyocr

_reader = None


def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["es", "en"], gpu=False)
    return _reader


# Etiquetas válidas (minúsculas, sin tildes)
ETIQUETAS = [
    "publicidad", "publi", "ad", "anuncio", "patrocinado",
    "contenido patrocinado", "colaboracion", "paid partnership",
    "sponsored", "advertisement",
]

# Etiquetas de 1-3 letras NO usan coincidencia aproximada (daría falsos positivos)
MIN_LEN_FUZZY = 5
UMBRAL_FUZZY = 0.82
UMBRAL_CONFIANZA = 0.3


def normalizar(texto: str) -> str:
    texto = texto.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        texto = texto.replace(a, b)
    return texto


def contiene_etiqueta(texto: str, fuzzy: bool = True):
    """Devuelve (etiqueta, tipo) o None. tipo = 'exacta' | 'aproximada'."""
    t = normalizar(texto)

    # 1) Coincidencia exacta por palabra completa
    for etiqueta in ETIQUETAS:
        if re.search(rf"(?<![a-z0-9]){re.escape(etiqueta)}(?![a-z0-9])", t):
            return etiqueta, "exacta"

    # 2) Coincidencia aproximada (tolera 1-2 letras mal leídas por el OCR)
    if fuzzy:
        palabras = re.findall(r"[a-z0-9]+", t)
        for etiqueta in ETIQUETAS:
            if len(etiqueta) < MIN_LEN_FUZZY or " " in etiqueta:
                continue
            for p in palabras:
                if len(p) < MIN_LEN_FUZZY:
                    continue
                if SequenceMatcher(None, p, etiqueta).ratio() >= UMBRAL_FUZZY:
                    return etiqueta, "aproximada"
    return None


def auditar_ocr(
    video_path: str,
    segundos_entre_frames: float = 2.0,
    ancho_max: int = 480,
    parar_al_primer_hallazgo: bool = True,
) -> dict:
    inicio = time.time()
    reader = get_reader()
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir el video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duracion = total_frames / fps
    paso = max(1, int(fps * segundos_entre_frames))

    hallazgos = []
    frames_leidos = 0
    frames_saltados = 0
    frame_idx = 0
    previo = None

    while frame_idx < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            break

        alto, ancho = frame.shape[:2]
        if ancho > ancho_max:
            escala = ancho_max / ancho
            frame = cv2.resize(frame, (ancho_max, int(alto * escala)))

        # Saltar frames casi idénticos al anterior (persona hablando, plano fijo)
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if previo is not None and cv2.absdiff(gris, previo).mean() < 4:
            frames_saltados += 1
            frame_idx += paso
            continue
        previo = gris

        frames_leidos += 1
        for _, texto, confianza in reader.readtext(frame):
            if confianza < UMBRAL_CONFIANZA:
                continue
            r = contiene_etiqueta(texto)
            if r:
                etiqueta, tipo = r
                hallazgos.append({
                    "timestamp": round(frame_idx / fps, 1),
                    "texto": texto,
                    "etiqueta": etiqueta,
                    "coincidencia": tipo,
                    "confianza": round(float(confianza), 2),
                })
        if hallazgos and parar_al_primer_hallazgo:
            break
        frame_idx += paso

    cap.release()

    return {
        "divulgacion_detectada": len(hallazgos) > 0,
        "duracion_video": round(duracion, 1),
        "frames_analizados": frames_leidos,
        "frames_saltados": frames_saltados,
        "tiempo_proceso_seg": round(time.time() - inicio, 1),
        "hallazgos": hallazgos,
    }