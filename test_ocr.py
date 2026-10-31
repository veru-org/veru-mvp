import sys
from app.modules.ocr import auditar_ocr

video = sys.argv[1]
resultado = auditar_ocr(video)
print(resultado)
