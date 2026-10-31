import sys
import json
from app.modules.transcripcion import transcribir

r = transcribir(sys.argv[1])
print(json.dumps(r, indent=2, ensure_ascii=False))