import sys
import json
from app.modules.brief import auditar_brief

brief = ("El creador debe mencionar que Baysi vende skincare, maquillaje "
         "y cuidado personal, y mostrar el producto.")
r = auditar_brief(sys.argv[1], brief)
print(json.dumps(r, indent=2, ensure_ascii=False))