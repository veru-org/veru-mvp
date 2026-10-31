import sys
import json
from app.modules.brief import auditar_brief

requisitos = [
    {"texto": "Mencionar skincare",
     "sinonimos": ["cuidado de la piel", "cuidado personal"]},
    "Mencionar maquillaje",
    "Mencionar cuidado personal",
    "Mostrar el producto o mercadería de Baysi",
]
r = auditar_brief(sys.argv[1], requisitos)
print(json.dumps(r, indent=2, ensure_ascii=False))