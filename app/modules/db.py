import os
from supabase import create_client

_cliente = None


def get_db():
    """Cliente del servidor (service_role). Salta el RLS: solo para el backend."""
    global _cliente
    if _cliente is None:
        _cliente = create_client(
            os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    return _cliente


def _cliente_auth():
    """Cliente con anon key, para registro y login."""
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


# ---------- Auditorías ----------
def guardar_auditoria(registro: dict, resultado: dict, user_id: str | None = None) -> dict:
    fila = {
        "marca": registro["marca"],
        "video_url": registro["video"],
        "veredicto": registro["veredicto"],
        "motivos": registro["motivos"],
        "reporte_pdf": registro["reporte_pdf"],
        "divulgacion_detectada": resultado["divulgacion"]["divulgacion_detectada"],
        "producto_detectado": resultado["producto_visible"],
        "brief_cumplido": resultado["brief"]["cumple_brief"],
        "resultado": {"puntos": resultado["brief"]["puntos"],
                      "rango_producto": resultado.get("rango_producto"),
                      "compliance": resultado.get("compliance")},
    }
    if user_id:
        fila["user_id"] = user_id
    r = get_db().table("auditorias").insert(fila).execute()
    return r.data[0]


def listar_auditorias(user_id: str | None = None) -> list:
    q = get_db().table("auditorias").select(
        "id,marca,video_url,veredicto,motivos,reporte_pdf,created_at"
    ).order("created_at", desc=True)
    if user_id:
        q = q.eq("user_id", user_id)
    return q.execute().data


# ---------- Auth ----------
def registrar(email: str, password: str) -> dict:
    r = _cliente_auth().auth.sign_up({"email": email, "password": password})
    return {"id": r.user.id if r.user else None,
            "email": email,
            "token": r.session.access_token if r.session else None}


def login(email: str, password: str) -> dict:
    r = _cliente_auth().auth.sign_in_with_password({"email": email, "password": password})
    return {"id": r.user.id, "email": email, "token": r.session.access_token}


def usuario_desde_token(token: str) -> str | None:
    try:
        return get_db().auth.get_user(token).user.id
    except Exception:
        return None