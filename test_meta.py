import sys
from app.modules.metadata import obtener_metadatos, auditar_metadatos

m = obtener_metadatos(sys.argv[1])
print(m)
print(auditar_metadatos(m["descripcion"], m["titulo"]))