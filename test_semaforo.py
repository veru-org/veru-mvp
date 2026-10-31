import sys, json
from app.modules.semaforo import auditar_video

requisitos = [
    {"texto": "Mencionar skincare",
     "sinonimos": ["cuidado de la piel", "cuidado personal"]},
    "Mencionar maquillaje",
    "Mencionar cuidado personal",
    "Mostrar el producto o mercadería de Baysi",
]
r = auditar_video(sys.argv[1], sys.argv[2], requisitos)
print(json.dumps(r, indent=2, ensure_ascii=False))