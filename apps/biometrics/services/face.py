import io
import cv2
import numpy as np
from PIL import Image
import insightface
from insightface.utils import face_align
from sklearn.preprocessing import normalize

_app = None

def _prepare(ctx_id: int = -1):
    """
    Lazy-load InsightFace FaceAnalysis pack (buffalo_l).
    ctx_id: -1 = CPU, 0 = first GPU (if available)
    """
    global _app
    if _app is None:
        _app = insightface.app.FaceAnalysis(name="buffalo_l")
        _app.prepare(ctx_id=ctx_id)  # -1 CPU, 0 GPU
    return _app

def _bgr_from_bytes(b: bytes) -> np.ndarray:
    """Decode image bytes to BGR (as OpenCV/InsightFace expect)."""
    img = Image.open(io.BytesIO(b)).convert("RGB")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def _detect_align_112(bgr: np.ndarray) -> np.ndarray | None:
    """
    Detect the largest face and return an aligned 112x112 RGB float32 image in [0,1].
    Uses norm_crop (no manual warpAffine needed).
    """
    app = _prepare()
    faces = app.get(bgr)
    if not faces:
        return None

    # Pick largest face
    faces.sort(key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]), reverse=True)
    f = faces[0]

    # Ensure 5 landmarks are present
    kps = getattr(f, "kps", None)
    kps = np.asarray(kps) if kps is not None else None
    if kps is None or kps.shape != (5, 2):
        return None

    # Safe alignment to 112x112
    aligned_bgr = face_align.norm_crop(bgr, landmark=kps, image_size=112)
    aligned_rgb = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return aligned_rgb

def embed_from_image_bytes(b: bytes) -> np.ndarray | None:
    """
    Return L2-normalized 512-D ArcFace embedding for the dominant face in the image bytes.
    Returns None if no usable face is found.
    """
    bgr = _bgr_from_bytes(b)
    aligned = _detect_align_112(bgr)
    if aligned is None:
        return None

    app = _prepare()
    rec = app.models.get("recognition")
    if rec is None:
        raise RuntimeError("ArcFace recognition model not loaded in buffalo_l pack.")

    emb = rec.get_feat(aligned)             # (512,)
    emb = normalize(emb.reshape(1, -1)).astype(np.float32)[0]  # L2-normalize
    return emb
