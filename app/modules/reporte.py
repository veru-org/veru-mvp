import os
from datetime import datetime
from fpdf import FPDF

COLORES = {
    "APROBADO": (46, 160, 67),
    "OBSERVADO": (230, 170, 20),
    "RECHAZADO": (200, 50, 50),
}
VERDE = (46, 160, 67)
ROJO = (200, 50, 50)


def _t(texto) -> str:
    """Limpia texto para la fuente estándar (latin-1)."""
    return str(texto if texto is not None else "").encode("latin-1", "replace").decode("latin-1")


def _titulo(pdf: FPDF, texto: str):
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _t(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)


def generar_pdf(resultado: dict, marca: str, url: str, salida: str) -> str:
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Cabecera
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, _t("VERU - Reporte de auditoría"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _t(f"Marca: {marca}"), new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(0, 6, _t(f"Video: {url}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Fecha: {datetime.now():%Y-%m-%d %H:%M}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Semáforo
    v = resultado["veredicto"]
    pdf.set_fill_color(*COLORES[v])
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 16, v, align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Motivos
    _titulo(pdf, "Motivos")
    for m in resultado["motivos"]:
        pdf.multi_cell(0, 6, _t(f"- {m}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Divulgación
    div = resultado["divulgacion"]
    _titulo(pdf, "Divulgación publicitaria")
    pdf.cell(0, 6, _t(f"Resultado: {div['veredicto']}"), new_x="LMARGIN", new_y="NEXT")
    for h in div["hallazgos"]:
        ts = f" (s {h['timestamp']})" if h.get("timestamp") is not None else ""
        pdf.multi_cell(0, 6, _t(f"- '{h['etiqueta']}' en {h['fuente']} ({h['coincidencia']}){ts}"),
                       new_x="LMARGIN", new_y="NEXT")
    if not div["hallazgos"]:
        pdf.cell(0, 6, _t("- No se encontró etiqueta en descripción ni en pantalla."),
                 new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Requisitos del brief
    _titulo(pdf, "Requisitos del brief")
    for p in resultado["brief"]["puntos"]:
        estado = "CUMPLE" if p["cumple"] else "NO CUMPLE"
        pdf.set_text_color(*(VERDE if p["cumple"] else ROJO))
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(28, 6, f"[{estado}]")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)
        ts = f" - s {p['timestamp']}" if p.get("timestamp") is not None else ""
        pdf.multi_cell(0, 6, _t(f"{p['requisito']} ({p['tipo_coincidencia']}){ts}"),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, _t(f"    {p['evidencia']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
    pdf.ln(3)

    # Producto
    _titulo(pdf, "Producto en pantalla")
    visible = "Sí" if resultado["producto_visible"] else "No"
    rango = resultado.get("rango_producto") or "-"
    pdf.cell(0, 6, _t(f"Visible: {visible} ({rango})"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Transcripción
    _titulo(pdf, "Transcripción")
    for s in resultado["brief"]["transcripcion"]:
        pdf.multi_cell(0, 6, _t(f"[{s['inicio']:.0f}-{s['fin']:.0f} s] {s['texto']}"),
                       new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Limitaciones y trazabilidad
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, _t(
        "Nota: este reporte es una ayuda automatizada. APROBADO indica que la etiqueta "
        "publicitaria está presente, no que cumpla por sí solo la normativa vigente. "
        "Los casos OBSERVADO requieren revisión humana."),
                   new_x="LMARGIN", new_y="NEXT")
    modelo = resultado["brief"].get("modelo", "-")
    pdf.cell(0, 4, _t(f"Modelo de análisis: {modelo} | "
                      f"Tiempo de Gemini: {resultado['brief'].get('tiempo_proceso_seg', '-')} s"),
             new_x="LMARGIN", new_y="NEXT")

    pdf.output(salida)
    return salida