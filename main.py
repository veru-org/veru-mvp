import json
import os
import shutil
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from app.modules import db
from app.modules.semaforo import auditar_video
from app.modules.reporte import generar_pdf

app = FastAPI(title="VERU MVP")
seguridad = HTTPBearer()

UPLOADS = "app/uploads"
REPORTS = "app/reports"
os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(REPORTS, exist_ok=True)

REQUISITOS_DEFECTO = ["Mostrar el producto o mercadería de la marca"]


class Credenciales(BaseModel):
    email: str
    password: str


def usuario_actual(cred=Depends(seguridad)) -> str:
    uid = db.usuario_desde_token(cred.credentials)
    if not uid:
        raise HTTPException(401, "Token inválido o vencido.")
    return uid


def _vacio(valor) -> bool:
    """Swagger a veces manda '' o 'string' como relleno."""
    return valor is None or valor.strip() in ("", "string")


def _descargar_video(url: str, destino: str):
    import yt_dlp
    opciones = {"format": "best[ext=mp4]/best", "outtmpl": destino,
                "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opciones) as ydl:
        ydl.download([url])


@app.get("/")
def root():
    return {"message": "VERU API funcionando"}


@app.post("/auth/register")
def registro(c: Credenciales):
    try:
        return db.registrar(c.email, c.password)
    except Exception as e:
        raise HTTPException(400, f"No se pudo registrar: {e}")


@app.post("/auth/login")
def iniciar_sesion(c: Credenciales):
    try:
        return db.login(c.email, c.password)
    except Exception:
        raise HTTPException(401, "Credenciales incorrectas.")


@app.post("/audit")
async def audit(
        marca: str = Form(...),
        url: str = Form(None),
        requisitos: str = Form(None),
        video: UploadFile = File(None),
        user_id: str = Depends(usuario_actual),
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
        if video:
            with open(ruta_video, "wb") as f:
                shutil.copyfileobj(video.file, f)
        else:
            await run_in_threadpool(_descargar_video, url, ruta_video)

        resultado = await run_in_threadpool(auditar_video, url, ruta_video, reqs)
        await run_in_threadpool(generar_pdf, resultado, marca, origen, ruta_pdf)
    except Exception as e:
        raise HTTPException(500, f"Error al auditar: {type(e).__name__}: {e}")
    finally:
        # Privacidad: borrar el video local siempre
        if os.path.exists(ruta_video):
            os.remove(ruta_video)

    registro = {
        "marca": marca,
        "video": origen,
        "veredicto": resultado["veredicto"],
        "motivos": resultado["motivos"],
        "reporte_pdf": ruta_pdf,
    }
    try:
        fila = await run_in_threadpool(db.guardar_auditoria, registro, resultado, user_id)
    except Exception as e:
        raise HTTPException(500, f"Auditoría hecha, pero no se pudo guardar: {e}")
    return {"id": fila["id"], **registro}


@app.get("/audits")
def listar(user_id: str = Depends(usuario_actual)):
    return db.listar_auditorias(user_id)


@app.get("/audits/{audit_id}/report")
def reporte(audit_id: str, user_id: str = Depends(usuario_actual)):
    for r in db.listar_auditorias(user_id):
        if r["id"] == audit_id and r["reporte_pdf"] and os.path.exists(r["reporte_pdf"]):
            return FileResponse(r["reporte_pdf"], media_type="application/pdf",
                                filename=f"veru_{audit_id}.pdf")
    raise HTTPException(404, "Reporte no encontrado.")