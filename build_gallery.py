import os, glob, json, numpy as np
from insightface.app import FaceAnalysis

def init_model():
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app

def face_embed(app, img_path):
    import cv2
    im = cv2.imread(img_path)
    if im is None:
        return None
    faces = app.get(im)
    if not faces:
        return None
    # take the largest face
    faces.sort(key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
    emb = faces[0].normed_embedding
    if emb is None:
        emb = faces[0].embedding
        emb = emb / (np.linalg.norm(emb) + 1e-8)
    return emb.astype(float).tolist()

def avg_embedding(vectors):
    arr = np.array(vectors, dtype=np.float32)
    m = arr.mean(axis=0)
    return (m / (np.linalg.norm(m) + 1e-8)).astype(float).tolist()

def main():
    app = init_model()
    base = "media/faces"
    out = {}
    for sid in os.listdir(base):
        sid_dir = os.path.join(base, sid)
        if not os.path.isdir(sid_dir):
            continue
        vecs = []
        for p in glob.glob(os.path.join(sid_dir, "*")):
            v = face_embed(app, p)
            if v is not None:
                vecs.append(v)
        if vecs:
            out[sid] = avg_embedding(vecs)
            print(f"[OK] {sid}: {len(vecs)} images")
        else:
            print(f"[WARN] {sid}: no face found in any image")

    with open("gallery.json", "w") as f:
        json.dump(out, f)
    print(f"Saved {len(out)} students to gallery.json")

if __name__ == "__main__":
    main()
