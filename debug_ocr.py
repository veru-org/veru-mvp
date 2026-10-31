import sys
import cv2
from app.modules.ocr import get_reader

video = sys.argv[1]
reader = get_reader()
cap = cv2.VideoCapture(video)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

for idx in range(0, total, int(fps)):
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    if not ok:
        break
    h, w = frame.shape[:2]
    if w > 720:
        frame = cv2.resize(frame, (720, int(h * 720 / w)))
    textos = [(t, round(float(c), 2)) for _, t, c in reader.readtext(frame)]
    print(f"{idx/fps:.1f}s -> {textos}")
cap.release()