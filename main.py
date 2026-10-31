import json
import os
import shutil
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

load_dotenv()

from app.modules.semaforo import auditar_video
from app.modules.reporte import generar_pdf

app = FastAPI(title="VERU MVP")

UPLOADS = "app/uploads"
REPORTS = "app/reports"
DATA = "app/data/auditorias.json"
os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(REPORTS, exist_ok=True)
os.makedirs(os.path.dirname(DATA), exist_ok=True)

REQUISITOS_DEFECTO = ["Mostrar el producto o mercadería de la marca"]


def _leer() -> list:
    if not os.path.exists(DATA):
        return []
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def _guardar(lista: list):
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def _descargar_video(url: str, destino: str):
    import yt_dlp
    opciones = {"format": "best[ext=mp4]/best", "outtmpl": destino,
                "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opciones) as ydl:
        ydl.download([url])


def _vacio(valor) -> bool:
    """Swagger a veces manda '' o 'string' como relleno."""
    return valor is None or valor.strip() in ("", "string")


@app.get("/")
def root():
    return {"message": "VERU API funcionando"}


@app.post("/audit")
async def audit(
        marca: str = Form(...),
        url: str = Form(None),
        requisitos: str = Form(None),  # JSON: ["texto", {"texto": "...", "sinonimos": [...]}]
        video: UploadFile = File(None),
):
    if _vacio(url):
        url = None
    if video is not None and not video.filename:
        video = None

    if not url and not video:
        raise HTTPException(400, "Envía un link (url) o un archivo MP4 (video).")

    try:
        reqs = REQUISITOS_DEFECTO if _vacio(requisitos) else json.loads(requisitos)
    except json.JSONDecodeError:
        raise HTTPException(400, "requisitos debe ser JSON válido.")

    audit_id = uuid.uuid4().hex[:8]
    ruta_video = os.path.join(UPLOADS, f"{audit_id}.mp4")
    ruta_pdf = os.path.join(REPORTS, f"auditoria_{audit_id}.pdf")
    origen = url or video.filename

    try:
        # 1) Obtener el video (archivo o link)
        if video:
            with open(ruta_video, "wb") as f:
                shutil.copyfileobj(video.file, f)
        else:
            await run_in_threadpool(_descargar_video, url, ruta_video)

        # 2) Auditar (bloqueante: se ejecuta en un hilo)
        resultado = await run_in_threadpool(auditar_video, url, ruta_video, reqs)

        # 3) PDF
        await run_in_threadpool(generar_pdf, resultado, marca, origen, ruta_pdf)
    except Exception as e:
        raise HTTPException(500, f"Error al auditar: {type(e).__name__}: {e}")
    finally:
        # Privacidad: borrar el video local siempre
        if os.path.exists(ruta_video):
            os.remove(ruta_video)

    registro = {
        "id": audit_id,
        "marca": marca,
        "video": origen,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "veredicto": resultado["veredicto"],
        "motivos": resultado["motivos"],
        "reporte_pdf": ruta_pdf,
    }
    historial = _leer()
    historial.append(registro)
    _guardar(historial)
    return registro


@app.get("/audits")
def listar():
    return list(reversed(_leer()))


@app.get("/audits/{audit_id}/report")
def reporte(audit_id: str):
    for r in _leer():
        if r["id"] == audit_id and os.path.exists(r["reporte_pdf"]):
            return FileResponse(r["reporte_pdf"], media_type="application/pdf",
                                filename=f"veru_{audit_id}.pdf")
    raise HTTPException(404, "Reporte no encontrado.")