from app.modules.metadata import obtener_metadatos, auditar_metadatos
from app.modules.ocr import auditar_ocr


def auditar_divulgacion(url: str = None, video_path: str = None,
                        descripcion_manual: str = "") -> dict:
    """
    Combina metadatos (rápido) y OCR (lento, solo si hace falta).
    Devuelve veredicto semaforizado con motivos y timestamps.
    """
    motivos = []
    hallazgos = []
    meta_res = None
    ocr_res = None

    # 1) Metadatos primero (~3 s)
    descripcion, titulo = descripcion_manual, ""
    if url:
        try:
            m = obtener_metadatos(url)
            descripcion, titulo = m["descripcion"], m["titulo"]
        except Exception as e:
            motivos.append(f"No se pudieron leer los metadatos del link ({type(e).__name__}).")

    if descripcion or titulo:
        meta_res = auditar_metadatos(descripcion, titulo)
        for h in meta_res["hallazgos"]:
            hallazgos.append({"fuente": h["fuente"], "etiqueta": h["etiqueta"],
                              "coincidencia": h["coincidencia"], "timestamp": None})

    # 2) OCR solo si los metadatos no encontraron etiqueta exacta
    hay_exacta = any(h["coincidencia"] == "exacta" for h in hallazgos)
    if video_path and not hay_exacta:
        ocr_res = auditar_ocr(video_path, segundos_entre_frames=3.0)
        for h in ocr_res["hallazgos"]:
            hallazgos.append({"fuente": "pantalla", "etiqueta": h["etiqueta"],
                              "coincidencia": h["coincidencia"],
                              "timestamp": h["timestamp"]})

    # 3) Veredicto
    if any(h["coincidencia"] == "exacta" for h in hallazgos):
        veredicto = "APROBADO"
        motivos.append("Se encontró una etiqueta publicitaria explícita.")
    elif hallazgos:
        veredicto = "OBSERVADO"
        motivos.append("Se encontró una coincidencia aproximada; requiere revisión humana.")
    else:
        veredicto = "RECHAZADO"
        motivos.append("No se detectó etiqueta publicitaria en descripción ni en pantalla.")

    return {
        "divulgacion_detectada": veredicto != "RECHAZADO",
        "veredicto": veredicto,
        "motivos": motivos,
        "hallazgos": hallazgos,
        "ocr_ejecutado": ocr_res is not None,
        "tiempo_ocr_seg": ocr_res["tiempo_proceso_seg"] if ocr_res else 0,
    }