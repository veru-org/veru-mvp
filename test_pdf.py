import sys
from app.modules.semaforo import auditar_video
from app.modules.reporte import generar_pdf

requisitos = [
    {"texto": "Mencionar skincare", "sinonimos": ["cuidado de la piel", "cuidado personal"]},
    "Mencionar maquillaje",
    "Mencionar cuidado personal",
    "Mostrar el producto o mercadería de Baysi",
]
url, video = sys.argv[1], sys.argv[2]
r = auditar_video(url, video, requisitos)
ruta = generar_pdf(r, "Baysi", url, "app/reports/auditoria_prueba.pdf")
print(r["veredicto"], "->", ruta)