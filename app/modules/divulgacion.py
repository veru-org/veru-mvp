from app.modules.metadata import obtener_metadatos, auditar_metadatos
from app.modules.ocr import auditar_ocr


def auditar_divulgacion(url: str = None, video_path: str = None,
                        descripcion_manual: str = "") -> dict:
    """
    Combina metadatos (rápido) y OCR (lento, solo si hace falta).
    Devuelve veredicto semaforizado con motivos y timestamps.

    Si no se pudo leer la descripción (fallo técnico) y el OCR tampoco encuentra
    nada, NO se rechaza: queda OBSERVADO con "no_verificable" = True, porque no
    sabemos si el video tenía etiqueta.
    """
    motivos = []
    hallazgos = []
    meta_res = None
    ocr_res = None
    meta_fallo = False

    # 1) Metadatos primero (~3 s)
    descripcion, titulo = descripcion_manual, ""
    if url:
        try:
            m = obtener_metadatos(url)
            descripcion, titulo = m["descripcion"], m["titulo"]
        except Exception as e:
            meta_fallo = not descripcion_manual
            motivos.append(f"No se pudieron leer los metadatos del link ({type(e).__name__}).")

    if descripcion or titulo:
        meta_res = auditar_metadatos(descripcion, titulo)
        for h in meta_res["hallazgos"]:
            hallazgos.append({"fuente": h["fuente"], "etiqueta": h["etiqueta"],
                              "coincidencia": h["coincidencia"], "timestamp": None,
                              "nota": h.get("nota", "")})

    # 2) OCR solo si los metadatos no encontraron etiqueta exacta
    hay_exacta = any(h["coincidencia"] == "exacta" for h in hallazgos)
    if video_path and not hay_exacta:
        ocr_res = auditar_ocr(video_path, segundos_entre_frames=3.0)
        for h in ocr_res["hallazgos"]:
            hallazgos.append({"fuente": "pantalla", "etiqueta": h["etiqueta"],
                              "coincidencia": h["coincidencia"],
                              "timestamp": h["timestamp"]})

    # 3) Veredicto
    no_verificable = False
    if any(h["coincidencia"] == "exacta" for h in hallazgos):
        veredicto = "APROBADO"
        motivos.append("Se encontró una etiqueta publicitaria explícita.")
    elif hallazgos:
        veredicto = "OBSERVADO"
        if any(h.get("nota") for h in hallazgos) and not any(h["fuente"] == "pantalla" for h in hallazgos):
            motivos.append("La palabra de publicidad aparece dentro de una frase, no como etiqueta "
                           "(por ejemplo #publicidad); requiere revisión humana.")
        else:
            motivos.append("Se encontró una coincidencia aproximada; requiere revisión humana.")
    elif meta_fallo:
        veredicto = "OBSERVADO"
        no_verificable = True
        motivos.append("No se pudo verificar la descripción del video y no se encontró etiqueta "
                       "en pantalla; requiere revisión humana.")
    else:
        veredicto = "RECHAZADO"
        motivos.append("No se detectó etiqueta publicitaria en descripción ni en pantalla.")

    return {
        "divulgacion_detectada": veredicto == "APROBADO" or (veredicto == "OBSERVADO" and not no_verificable),
        "veredicto": veredicto,
        "no_verificable": no_verificable,
        "motivos": motivos,
        "hallazgos": hallazgos,
        "ocr_ejecutado": ocr_res is not None,
        "tiempo_ocr_seg": ocr_res["tiempo_proceso_seg"] if ocr_res else 0,
    }