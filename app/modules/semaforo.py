from concurrent.futures import ThreadPoolExecutor

from app.modules.divulgacion import auditar_divulgacion
from app.modules.brief import auditar_brief
from app.modules.compliance import evaluar_compliance

# Reglas que dependen de leer la descripción del video
_REGLAS_DIVULGACION = ("PE-01", "PE-02")


def _rango(ts):
    if not ts:
        return None
    return f"{min(ts):.0f} s a {max(ts):.0f} s"


def _seg(valor):
    """Formato único de segundos: 106.0 -> 106, '11' -> 11."""
    try:
        return int(round(float(valor)))
    except (TypeError, ValueError):
        return valor


def _es_requisito_visual(requisito: str) -> bool:
    """Los requisitos de 'mostrar producto' no deben bajar a OBSERVADO
    solo porque el modelo los marque como 'equivalente'."""
    r = requisito.lower()
    return "mostrar" in r or "producto" in r or "mercader" in r


def auditar_video(url, video_path, requisitos, pais="pe"):
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_div = ex.submit(auditar_divulgacion, url=url, video_path=video_path)
        f_brief = ex.submit(auditar_brief, video_path, requisitos)
        div, brief = f_div.result(), f_brief.result()

    for p in brief["puntos"]:
        p["timestamp"] = _seg(p.get("timestamp"))

    motivos = []
    rojo = False
    amarillo = False
    no_verificable = bool(div.get("no_verificable"))

    # Brief (requisitos de la campaña)
    for p in brief["puntos"]:
        if not p["cumple"]:
            rojo = True
            motivos.append(f"No cumple: {p['requisito']}.")
        elif (p["tipo_coincidencia"] == "equivalente"
              and not _es_requisito_visual(p["requisito"])):
            amarillo = True
            motivos.append(
                f"Cumple por equivalencia: {p['requisito']} (s {p['timestamp']}).")

    # Compliance por país (incluye divulgación y producto: PE-01, PE-02, PE-07)
    comp = evaluar_compliance(div, brief, pais)
    for it in comp["items"]:
        if it["estado"] == "no_cumple":
            if it["gravedad"] == "rechaza" and not (
                    no_verificable and it["id"] in _REGLAS_DIVULGACION):
                rojo = True
            else:
                amarillo = True
            if no_verificable and it["id"] in _REGLAS_DIVULGACION:
                motivos.append(f"{it['id']}: revisar - no se pudo leer la descripción del video; "
                               "no se puede confirmar si tenía etiqueta.")
                it["estado"] = "revisar"
                it["detalle"] = "No se pudo leer la descripción; requiere revisión humana."
            else:
                motivos.append(f"{it['id']}: {it['descripcion']} - {it['detalle']}")
        elif it["estado"] == "revisar":
            amarillo = True
            motivos.append(f"{it['id']}: revisar - {it['detalle']}")

    veredicto = "RECHAZADO" if rojo else "OBSERVADO" if amarillo else "APROBADO"
    if veredicto == "APROBADO":
        motivos.append("Divulgación, brief, producto y checklist cumplen.")

    return {
        "veredicto": veredicto,
        "motivos": motivos,
        "divulgacion": div,
        "brief": brief,
        "compliance": comp,
        "producto_visible": brief["producto_visible"],
        "rango_producto": _rango(brief["timestamps_producto"]),
    }