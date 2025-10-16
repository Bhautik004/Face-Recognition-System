import json, time
import numpy as np
import cv2
from insightface.app import FaceAnalysis

SIM_THRESH = 0.55   # adjust to 0.60 if you see false accepts
COOLDOWN_S  = 60    # avoid repeating the same student spam
HEADLESS  = False  # set to True if no GUI available

def init_model():
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app

def load_gallery(path="gallery.json"):
    with open(path, "r") as f:
        raw = json.load(f)
    gallery = {sid: np.array(vec, dtype=np.float32) for sid, vec in raw.items()}
    # ensure L2 normalize
    for sid in gallery:
        v = gallery[sid]
        gallery[sid] = v / (np.linalg.norm(v) + 1e-8)
    return gallery

def best_match(emb, gallery):
    best_id, best_sim = None, -1.0
    for sid, g in gallery.items():
        # cosine because both are normalized
        s = float(np.dot(emb, g))
        if s > best_sim:
            best_id, best_sim = sid, s
    return best_id, best_sim

def main(cam_src=1):
    app = init_model()
    gallery = load_gallery()
    print(f"Loaded {len(gallery)} students from gallery.json")

    cap = cv2.VideoCapture(cam_src, cv2.CAP_MSMF)
    print("cap opened:", cap.isOpened())
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera: {cam_src}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    last_marked = {}  # sid -> timestamp

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera: {cam_src}")

    print("Press ESC to quit.")
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        faces = app.get(frame)
        for f in faces:
            emb = f.normed_embedding
            if emb is None:
                e = f.embedding
                emb = e / (np.linalg.norm(e) + 1e-8)
            emb = emb.astype(np.float32)

            sid, sim = best_match(emb, gallery)

            x1,y1,x2,y2 = [int(x) for x in f.bbox]
            color = (0,255,0) if sim >= SIM_THRESH else (0,0,255)
            label = f"{sid or 'unknown'} {sim:.2f}"
            cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
            cv2.putText(frame, label, (x1, max(0,y1-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            now = time.time()
            if sid and sim >= SIM_THRESH and (now - last_marked.get(sid, 0) >= COOLDOWN_S):
                print(f"[MATCH] {sid} sim={sim:.3f} @ {time.strftime('%H:%M:%S')}")
                last_marked[sid] = now

        if not HEADLESS:
            cv2.imshow("S",frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC
                break
        else:
            # headless: no window; optional: write a preview every few seconds
            # cv2.imwrite("preview.jpg", frame)  # uncomment if you want snapshots
            pass



    cap.release()
    if not HEADLESS:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main(0)  # 0 = default webcam, or pass RTSP/HTTP URL
