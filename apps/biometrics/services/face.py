# apps/biometrics/services/face.py
import numpy as np
from insightface.app import FaceAnalysis
import cv2
import io

# Initialize once (module-level)
_app = None
def _get_app():
    global _app
    if _app is None:
        _app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(640, 640))
    return _app

def embed_from_image_bytes(img_bytes: bytes):
    """Return L2-normalized 512-D embedding using buffalo_l, or None if no face."""
    app = _get_app()
    data = np.frombuffer(img_bytes, dtype=np.uint8)
    im = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if im is None:
        return None
    faces = app.get(im)
    if not faces:
        return None
    # largest face
    faces.sort(key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
    f = faces[0]
    emb = f.normed_embedding
    if emb is None:
        emb = f.embedding
        emb = emb / (np.linalg.norm(emb) + 1e-8)
    emb = emb.astype(np.float32)
    # force L2 normalize
    emb = emb / (np.linalg.norm(emb) + 1e-8)
    return emb
