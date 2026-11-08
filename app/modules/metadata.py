import os
import re
import time
import unicodedata

import yt_dlp

from app.modules.ocr import contiene_etiqueta

try:
    from app.modules.ocr import ETIQUETAS
except ImportError:  # por si el nombre cambia
    ETIQUETAS = ["publicidad", "publi", "ad", "anuncio", "patrocinado",
                 "contenido patrocinado", "colaboracion", "paid partnership",
                 "sponsored", "advertisement"]


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def _como_etiqueta(texto: str):
    """Devuelve la etiqueta si aparece USADA como etiqueta: hashtag (#publicidad)
    o suelta (al inicio, tras salto de línea, entre corchetes o barras).
    Una palabra dentro de una frase ('para hacerle esta publicidad') no cuenta."""
    t = _norm(texto)
    for lab in ETIQUETAS:
        l = _norm(lab)
        pegada = re.escape(l.replace(" ", ""))
        con_esp = r"\s+".join(re.escape(p) for p in l.split())
        if re.search(r"#" + pegada + r"(?!\w)", t):
            return lab
        if re.search(r"(?:^|[\n\[\(\|•—])\s*" + con_esp + r"\s*(?:$|[\n\]\)\|•—:#@])", t):
            return lab
    return None


def obtener_metadatos(url: str, intentos: int = 3) -> dict:
    """Lee título y descripción con yt-dlp. Reintenta porque TikTok falla de forma
    intermitente. Si defines YTDLP_COOKIES_BROWSER=chrome en el .env, usa las
    cookies de ese navegador (ayuda cuando TikTok bloquea la extracción)."""
    opciones = {"skip_download": True, "quiet": True, "no_warnings": True}
    navegador = os.getenv("YTDLP_COOKIES_BROWSER", "").strip()
    if navegador:
        opciones["cookiesfrombrowser"] = (navegador,)
    ultimo_error = None
    for i in range(intentos):
        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=False)
            return {
                "titulo": info.get("title") or "",
                "descripcion": info.get("description") or "",
                "autor": info.get("uploader") or "",
                "duracion": info.get("duration"),
            }
        except Exception as e:
            ultimo_error = e
            if i < intentos - 1:
                time.sleep(2 * (i + 1))
    raise ultimo_error


def auditar_metadatos(descripcion: str, titulo: str = "") -> dict:
    """Busca etiquetas publicitarias en descripción y título.
    'exacta' = usada como etiqueta (hashtag o suelta). Si la palabra solo aparece
    dentro de una frase, queda 'aproximada' (requiere revisión humana)."""
    hashtags = re.findall(r"#\w+", descripcion)
    hallazgos = []
    for fuente, texto in (("descripcion", descripcion), ("titulo", titulo)):
        if not texto:
            continue
        lab = _como_etiqueta(texto)
        if lab:
            hallazgos.append({"fuente": fuente, "etiqueta": lab, "coincidencia": "exacta"})
            continue
        r = contiene_etiqueta(texto)
        if r:
            etiqueta, tipo = r
            hallazgos.append({"fuente": fuente, "etiqueta": etiqueta, "coincidencia": "aproximada",
                              "nota": "dentro de una frase" if tipo == "exacta" else ""})
    return {
        "divulgacion_detectada": len(hallazgos) > 0,
        "hashtags": hashtags,
        "hallazgos": hallazgos,
    }