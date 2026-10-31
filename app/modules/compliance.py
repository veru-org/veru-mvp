import json
import os

REGLAS_DIR = "reglas"


def cargar_reglas(pais: str = "pe") -> dict:
    ruta = os.path.join(REGLAS_DIR, f"{pais.lower()}.json")
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No hay reglas para el país '{pais}'")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _lista(brief: dict, campo: str):
    """None si el campo no existe (no se pudo evaluar)."""
    return brief.get(campo)


def _txt(items) -> str:
    return "; ".join(f"'{a['texto']}' (s {a.get('timestamp')})" for a in items)


def _verificar(verificador: str, div: dict, brief: dict):
    """Devuelve (estado, detalle). estado: cumple | no_cumple | revisar."""
    if verificador == "divulgacion_presente":
        if div["divulgacion_detectada"]:
            return "cumple", "Etiqueta publicitaria detectada."
        return "no_cumple", "No se detectó etiqueta en descripción ni en pantalla."

    if verificador == "divulgacion_clara":
        if not div["divulgacion_detectada"]:
            return "no_cumple", "Sin divulgación."
        if any(h["coincidencia"] == "exacta" for h in div["hallazgos"]):
            return "cumple", "Coincidencia exacta."
        return "revisar", "Solo coincidencia aproximada."

    if verificador in ("sin_afirmaciones_salud", "sin_afirmaciones_objetivas"):
        campo = ("afirmaciones_salud" if verificador == "sin_afirmaciones_salud"
                 else "afirmaciones_objetivas")
        items = _lista(brief, campo)
        if items is None:
            return "revisar", "No se pudo evaluar."
        if items:
            return "revisar", _txt(items)
        return "cumple", "No se detectaron."

    if verificador == "promocion_con_condiciones":
        promos = _lista(brief, "promociones")
        if promos is None:
            return "revisar", "No se pudo evaluar."
        if not promos:
            return "cumple", "No hay promociones."
        if brief.get("promocion_con_condiciones"):
            return "cumple", "Promoción con condiciones informadas."
        return "revisar", "Promoción sin condiciones claras: " + _txt(promos)

    if verificador == "sin_comparacion_competidor":
        items = _lista(brief, "comparaciones_competidor")
        if items is None:
            return "revisar", "No se pudo evaluar."
        if items:
            return "revisar", _txt(items)
        return "cumple", "No hay comparaciones."

    if verificador == "precios_con_igv":
        precios = _lista(brief, "precios_mostrados")
        if precios is None:
            return "revisar", "No se pudo evaluar."
        if not precios:
            return "cumple", "No se muestran precios."
        if brief.get("precios_indican_igv"):
            return "cumple", "Precios indican IGV."
        return "revisar", "Precios sin aclarar IGV: " + _txt(precios)

    if verificador == "producto_visible":
        if brief["producto_visible"]:
            return "cumple", "Producto visible."
        return "no_cumple", "Producto no visible."

    return "revisar", f"Verificador desconocido: {verificador}"


def evaluar_compliance(div: dict, brief: dict, pais: str = "pe") -> dict:
    cfg = cargar_reglas(pais)
    items = []
    for r in cfg["reglas"]:
        estado, detalle = _verificar(r["verificador"], div, brief)
        items.append({"id": r["id"], "norma": r.get("norma", ""),
                      "descripcion": r["descripcion"],
                      "gravedad": r["gravedad"], "estado": estado,
                      "detalle": detalle})
    return {"pais": cfg["pais"], "autoridad": cfg["autoridad"],
            "estado_reglas": cfg["estado"],
            "declaracion_marca": cfg.get("declaracion_marca", []),
            "items": items}