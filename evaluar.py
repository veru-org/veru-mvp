"""Evalúa VERU contra la revisión humana de Samuel.

Uso (con el venv activo y GEMINI_MOCK=0):
    python evaluar.py                 # corre todos los pendientes
    python evaluar.py --limite 8      # corre solo 8 (cuida la cuota diaria)
    python evaluar.py --solo-resumen  # solo recalcula las métricas

El avance se guarda en resultados_lote.json: si se corta, al volver a
correr retoma donde quedó.
"""
import argparse
import csv
import json
import os
import time

from dotenv import load_dotenv

load_dotenv()

from app.modules.semaforo import auditar_video
from app.modules.reporte import generar_pdf

CSV = "videos_prueba.csv"
SALIDA = "resultados_lote.json"
UPLOADS = "app/uploads"
REPORTES = "app/reports/lote"


def si(valor: str) -> bool:
    return valor.strip().lower().startswith("s")


def descargar(url: str, destino: str, intentos: int = 3):
    """TikTok falla de forma intermitente: se reintenta antes de rendirse."""
    import yt_dlp
    opciones = {"format": "best[ext=mp4]/best", "outtmpl": destino,
                "quiet": True, "no_warnings": True}
    ultimo = None
    for i in range(intentos):
        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                ydl.download([url])
            return
        except Exception as e:
            ultimo = e
            if i < intentos - 1:
                time.sleep(3 * (i + 1))
    raise ultimo


ETIQ = ["publicidad", "publi", "anuncio", "patrocinado", "colaboracion",
        "colaboración", "sponsored", "paid partnership", "advertisement"]
IGNORAR = {"del", "de", "la", "el", "los", "las", "tarjeta", "perfumes", "salon", "salón", "io"}


def pantalla_ocr(ruta: str, marca: str, cada=3.0, ancho=480):
    """True si en pantalla aparece texto de publicidad O el nombre de la marca."""
    import difflib
    import cv2
    import easyocr
    global _READER
    if "_READER" not in globals():
        _READER = easyocr.Reader(["es", "en"], gpu=False, verbose=False)
    tokens = [t for t in marca.lower().replace("'", "").split() if len(t) >= 3 and t not in IGNORAR]
    cap = cv2.VideoCapture(ruta)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    paso = max(1, int(fps * cada))
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                return None
            if i % paso == 0:
                h, w = frame.shape[:2]
                frame = cv2.resize(frame, (ancho, int(h * ancho / w)))
                for _, texto, conf in _READER.readtext(frame):
                    for pal in texto.lower().replace("'", "").replace("#", " ").split():
                        for ref in ETIQ + tokens:
                            if pal == ref or difflib.SequenceMatcher(None, pal, ref).ratio() >= 0.85:
                                return {"texto": texto, "coincide": ref, "seg": round(i / fps, 1)}
            i += 1
    finally:
        cap.release()


def cargar_csv() -> list:
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    for f in filas:
        f["lista_requisitos"] = [r.strip() for r in f["requisitos"].split(";") if r.strip()]
    return filas


def cargar_resultados() -> dict:
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_resultados(res: dict):
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)


def procesar(fila: dict) -> dict:
    vid = fila["id"]
    ruta = os.path.join(UPLOADS, f"lote_{vid}.mp4")
    os.makedirs(UPLOADS, exist_ok=True)
    inicio = time.time()
    try:
        descargar(fila["link"], ruta)
        t_aud = time.time()
        r = auditar_video(fila["link"], ruta, fila["lista_requisitos"])
        t_aud = round(time.time() - t_aud, 1)
        try:
            generar_pdf(r, fila["marca"], fila["link"],
                        os.path.join(REPORTES, f"{vid}_{fila['marca']}.pdf".replace(" ", "_")))
        except Exception as e:
            print(f"  (PDF no generado: {e})")
        pantalla = None
        try:
            pantalla = pantalla_ocr(ruta, fila["marca"])
        except Exception as e:
            print(f"  (OCR de pantalla falló: {e})")
        div = r["divulgacion"]
        # Etiqueta detectada en metadatos (lo que Samuel marcó en su columna)
        en_meta = any(h["fuente"] in ("descripcion", "titulo") and h["coincidencia"] == "exacta" for h in div["hallazgos"])
        return {
            "ok": True,
            "veredicto": r["veredicto"],
            "etiqueta_meta": en_meta,
            "pantalla": pantalla,
            "tiempo_auditoria": t_aud,
            "etiqueta_total": div["divulgacion_detectada"],
            "ocr_ejecutado": div["ocr_ejecutado"],
            "brief_sistema": r["brief"]["cumple_brief"],
            "puntos_fallidos": [p["requisito"] for p in r["brief"]["puntos"] if not p["cumple"]],
            "motivos": r["motivos"],
            "tiempo_seg": round(time.time() - inicio, 1),
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "tiempo_seg": round(time.time() - inicio, 1)}
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def resumen(filas: list, res: dict):
    print("\n" + "=" * 78)
    print(f"{'id':>2} {'marca':<24} {'humano':<7} {'sistema':<8} {'brief H/S':<10} {'veredicto':<10} {'seg':>5}")
    hechos = []
    for f in filas:
        r = res.get(f["id"])
        if not r:
            print(f"{f['id']:>2} {f['marca'][:24]:<24} (pendiente)")
            continue
        if not r["ok"]:
            print(f"{f['id']:>2} {f['marca'][:24]:<24} ERROR: {r['error'][:40]}")
            continue
        hechos.append((f, r))
        h = "Sí" if si(f["etiqueta_humano"]) else "No"
        s = "Sí" if r["etiqueta_meta"] else "No"
        bh = "Sí" if si(f["cumple_brief_humano"]) else "No"
        bs = "Sí" if r["brief_sistema"] else "No"
        marca_ok = "" if h == s else " <-- difiere"
        print(f"{f['id']:>2} {f['marca'][:24]:<24} {h:<7} {s:<8} {bh+'/'+bs:<10} "
              f"{r['veredicto']:<10} {r['tiempo_seg']:>5}{marca_ok}")

    if not hechos:
        return
    sin = [(f, r) for f, r in hechos if not si(f["etiqueta_humano"])]
    con = [(f, r) for f, r in hechos if si(f["etiqueta_humano"])]
    falsos_pos = [f["marca"] for f, r in sin if r["etiqueta_meta"]]
    falsos_neg = [f["marca"] for f, r in con if not r["etiqueta_meta"]]
    print("\nMÉTRICAS (etiqueta en descripción, contra la revisión humana)")
    print(f"  Videos medidos: {len(hechos)} de {len(filas)}")
    if sin:
        ok = len(sin) - len(falsos_pos)
        print(f"  Detección de videos SIN etiqueta: {ok}/{len(sin)} = {100*ok/len(sin):.0f}%  (meta >= 80%)")
        print(f"  Falsos positivos: {len(falsos_pos)}/{len(sin)} = {100*len(falsos_pos)/len(sin):.0f}%  (meta <= 15%) {falsos_pos}")
    if con:
        ok = len(con) - len(falsos_neg)
        print(f"  Detección de videos CON etiqueta: {ok}/{len(con)} = {100*ok/len(con):.0f}%  {('perdidos: ' + str(falsos_neg)) if falsos_neg else ''}")
    pm = [(f, r) for f, r in hechos if "pantalla" in r]
    if pm:
        ac = sum(1 for f, r in pm if si(f["pantalla_humano"]) == bool(r["pantalla"]))
        dif = [f["marca"] for f, r in pm if si(f["pantalla_humano"]) != bool(r["pantalla"])]
        print(f"  Acuerdo en 'etiqueta o marca en pantalla': {ac}/{len(pm)} = {100*ac/len(pm):.0f}%  {('difieren: ' + str(dif)) if dif else ''}")
    acuerdo = sum(1 for f, r in hechos if si(f["cumple_brief_humano"]) == r["brief_sistema"])
    print(f"  Acuerdo en 'cumple el brief': {acuerdo}/{len(hechos)} = {100*acuerdo/len(hechos):.0f}%")
    ta = [r["tiempo_auditoria"] for _, r in hechos if "tiempo_auditoria" in r]
    if ta:
        print(f"  Solo auditoría (sin descarga ni OCR extra): promedio {sum(ta)/len(ta):.0f} s, máximo {max(ta):.0f} s")
    tiempos = [r["tiempo_seg"] for _, r in hechos]
    print(f"  Tiempo por video: promedio {sum(tiempos)/len(tiempos):.0f} s, máximo {max(tiempos):.0f} s (meta < 60 s)")


SALIDA_DIV = "resultados_divulgacion.json"


def procesar_div(fila: dict) -> dict:
    """Solo divulgación (descripción + OCR). No usa Gemini, no gasta cuota."""
    from app.modules.divulgacion import auditar_divulgacion
    ruta = os.path.join(UPLOADS, f"lote_{fila['id']}.mp4")
    os.makedirs(UPLOADS, exist_ok=True)
    inicio = time.time()
    try:
        descargar(fila["link"], ruta)
        t0 = time.time()
        div = auditar_divulgacion(fila["link"], ruta)
        t_div = round(time.time() - t0, 1)
        en_meta = any(h["fuente"] in ("descripcion", "titulo") and h["coincidencia"] == "exacta" for h in div["hallazgos"])
        try:
            pantalla = pantalla_ocr(ruta, fila["marca"])
        except Exception as e:
            print(f"  (OCR de pantalla falló: {e})")
            pantalla = None
        return {"ok": True, "etiqueta_meta": en_meta, "etiqueta_total": div["divulgacion_detectada"],
                "no_verificable": div.get("no_verificable", False), "veredicto_div": div["veredicto"],
                "ocr_ejecutado": div["ocr_ejecutado"], "pantalla": pantalla,
                "tiempo_divulgacion": t_div, "tiempo_seg": round(time.time() - inicio, 1)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "tiempo_seg": round(time.time() - inicio, 1)}
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def resumen_div(filas: list, res: dict):
    print("\n" + "=" * 78)
    print(f"{'id':>2} {'marca':<24} {'desc H/S':<9} {'verif.':<7} {'pantalla H/S':<13} detalle pantalla")
    hechos = []
    for f in filas:
        r = res.get(f["id"])
        if not r:
            print(f"{f['id']:>2} {f['marca'][:24]:<24} (pendiente)")
            continue
        if not r["ok"]:
            print(f"{f['id']:>2} {f['marca'][:24]:<24} ERROR: {r['error'][:45]}")
            continue
        hechos.append((f, r))
        h = "Sí" if si(f["etiqueta_humano"]) else "No"
        s = "Sí" if r["etiqueta_meta"] else "No"
        ph = "Sí" if si(f["pantalla_humano"]) else "No"
        ps = "Sí" if r["pantalla"] else "No"
        det = f"'{r['pantalla']['texto']}' ~ {r['pantalla']['coincide']} (s {r['pantalla']['seg']})" if r["pantalla"] else ""
        marca = " <--" if (h != s or ph != ps) else ""
        print(f"{f['id']:>2} {f['marca'][:24]:<24} {h+'/'+s:<9} {'NO' if r['no_verificable'] else 'ok':<7} "
              f"{ph+'/'+ps:<13} {det}{marca}")
    if not hechos:
        return
    sin = [(f, r) for f, r in hechos if not si(f["etiqueta_humano"])]
    con = [(f, r) for f, r in hechos if si(f["etiqueta_humano"])]
    fp = [f["marca"] for f, r in sin if r["etiqueta_meta"]]
    fn = [f["marca"] for f, r in con if not r["etiqueta_meta"]]
    nv = [f["marca"] for f, r in hechos if r["no_verificable"]]
    print("\nMÉTRICAS DE DIVULGACIÓN (sin Gemini)")
    print(f"  Videos medidos: {len(hechos)} de {len(filas)}")
    if sin:
        print(f"  Detección de videos SIN etiqueta: {len(sin)-len(fp)}/{len(sin)} = {100*(len(sin)-len(fp))/len(sin):.0f}%  (meta >= 80%)")
        print(f"  Falsos positivos: {len(fp)}/{len(sin)} = {100*len(fp)/len(sin):.0f}%  (meta <= 15%) {fp}")
    if con:
        print(f"  Detección de videos CON etiqueta: {len(con)-len(fn)}/{len(con)}  {('perdidos: ' + str(fn)) if fn else ''}")
    if nv:
        print(f"  Sin poder leer descripción: {nv}")
    ac = sum(1 for f, r in hechos if si(f["pantalla_humano"]) == bool(r["pantalla"]))
    print(f"  Acuerdo en 'etiqueta o marca en pantalla': {ac}/{len(hechos)} = {100*ac/len(hechos):.0f}%")
    t = [r["tiempo_divulgacion"] for _, r in hechos if "tiempo_divulgacion" in r]
    if t:
        print(f"  Tiempo de divulgación: promedio {sum(t)/len(t):.0f} s, máximo {max(t):.0f} s")


def main_div(a):
    filas = cargar_csv()
    res = {}
    if os.path.exists(SALIDA_DIV):
        with open(SALIDA_DIV, encoding="utf-8") as f:
            res = json.load(f)
    if not a.solo_resumen:
        corridos = 0
        for f in filas:  # Lumar también entra: aquí no se usa el brief
            previo = res.get(f["id"])
            if previo and (previo["ok"] or not a.reintentar_errores):
                continue
            if a.limite is not None and corridos >= a.limite:
                break
            print(f"[{f['id']}] {f['marca']} ...")
            res[f["id"]] = procesar_div(f)
            with open(SALIDA_DIV, "w", encoding="utf-8") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=2)
            corridos += 1
            e = res[f["id"]]
            print("  ->", e.get("veredicto_div") or e.get("error"), f"({e['tiempo_seg']} s)")
    resumen_div(filas, res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-divulgacion", action="store_true",
                    help="mide etiqueta y pantalla sin usar Gemini (no gasta cuota)")
    ap.add_argument("--limite", type=int, default=None, help="máximo de videos nuevos en esta corrida")
    ap.add_argument("--solo-resumen", action="store_true")
    ap.add_argument("--reintentar-errores", action="store_true")
    a = ap.parse_args()

    if a.solo_divulgacion:
        return main_div(a)

    filas = cargar_csv()
    res = cargar_resultados()

    if not a.solo_resumen:
        if os.getenv("GEMINI_MOCK") == "1":
            raise SystemExit("GEMINI_MOCK=1: con el mock todos darían lo mismo. Ponlo en 0.")
        corridos = 0
        for f in filas:
            if f["requisitos"].strip().upper() == "PENDIENTE":
                print(f"[{f['id']}] {f['marca']}: omitido (brief pendiente de corregir)")
                continue
            previo = res.get(f["id"])
            if previo and (previo["ok"] or not a.reintentar_errores):
                continue
            if a.limite is not None and corridos >= a.limite:
                break
            print(f"[{f['id']}] {f['marca']} ...")
            res[f["id"]] = procesar(f)
            guardar_resultados(res)  # guarda tras cada video
            corridos += 1
            e = res[f["id"]]
            print("  ->", e.get("veredicto") or e.get("error"), f"({e['tiempo_seg']} s)")

    resumen(filas, res)


if __name__ == "__main__":
    main()