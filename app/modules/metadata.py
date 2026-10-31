import re
import yt_dlp
from app.modules.ocr import contiene_etiqueta


def obtener_metadatos(url: str) -> dict:
    opciones = {"skip_download": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "titulo": info.get("title") or "",
        "descripcion": info.get("description") or "",
        "autor": info.get("uploader") or "",
        "duracion": info.get("duration"),
    }


def auditar_metadatos(descripcion: str, titulo: str = "") -> dict:
    """Busca etiquetas publicitarias en descripción y título."""
    hashtags = re.findall(r"#\w+", descripcion)
    hallazgos = []
    for fuente, texto in (("descripcion", descripcion), ("titulo", titulo)):
        r = contiene_etiqueta(texto)
        if r:
            etiqueta, tipo = r
            hallazgos.append({"fuente": fuente, "etiqueta": etiqueta, "coincidencia": tipo})
    return {
        "divulgacion_detectada": len(hallazgos) > 0,
        "hashtags": hashtags,
        "hallazgos": hallazgos,
    }