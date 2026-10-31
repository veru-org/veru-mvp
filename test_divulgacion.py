import sys
import json
from app.modules.divulgacion import auditar_divulgacion

url = sys.argv[1]
video = sys.argv[2] if len(sys.argv) > 2 else None
r = auditar_divulgacion(url=url, video_path=video)
print(json.dumps(r, indent=2, ensure_ascii=False))