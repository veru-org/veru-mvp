from concurrent.futures import ThreadPoolExecutor

from app.modules.divulgacion import auditar_divulgacion
from app.modules.brief import auditar_brief


def _rango(ts):
    if not ts:
        return None
    return f"{min(ts):.0f} s a {max(ts):.0f} s"


def auditar_video(url, video_path, requisitos):
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_div = ex.submit(auditar_divulgacion, url=url, video_path=video_path)
        f_brief = ex.submit(auditar_brief, video_path, requisitos)
        div, brief = f_div.result(), f_brief.result()

    motivos = []
    rojo = False
    amarillo = False

    # Divulgación
    if div["veredicto"] == "RECHAZADO":
        rojo = True
        motivos.append("Sin etiqueta publicitaria en descripción ni en pantalla.")
    elif div["veredicto"] == "OBSERVADO":
        amarillo = True
        motivos.append("Etiqueta publicitaria dudosa; requiere revisión humana.")

    # Brief
    for p in brief["puntos"]:
        if not p["cumple"]:
            rojo = True
            motivos.append(f"No cumple: {p['requisito']}.")
        elif p["tipo_coincidencia"] == "equivalente":
            amarillo = True
            motivos.append(
                f"Cumple por equivalencia: {p['requisito']} (s {p['timestamp']}).")

    # Producto
    if not brief["producto_visible"]:
        rojo = True
        motivos.append("El producto no es visible en el video.")

    veredicto = "RECHAZADO" if rojo else "OBSERVADO" if amarillo else "APROBADO"
    if veredicto == "APROBADO":
        motivos.append("Divulgación, brief y producto cumplen.")

    return {
        "veredicto": veredicto,
        "motivos": motivos,
        "divulgacion": div,
        "brief": brief,
        "producto_visible": brief["producto_visible"],
        "rango_producto": _rango(brief["timestamps_producto"]),
    }