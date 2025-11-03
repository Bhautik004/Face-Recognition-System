# apps/academics/cam_worker_insight.py
import time, threading
import numpy as np
import cv2
from django.utils import timezone
from django.apps import apps as django_apps
from django.core.cache import cache
from insightface.app import FaceAnalysis

# pick ONE loader:
from .whitelist import load_session_whitelist  # DB centroids (UserEmbeddingTemplate)
# from .whitelist import load_session_whitelist_from_gallery  # TEMP for gallery.json

_SIM_THRESH   = 0.35   # start lower to validate; later 0.55–0.60
_COOLDOWN_SEC = 20
_WORKERS = {}

def _normalize_rows(M: np.ndarray) -> np.ndarray:
    M = M.astype(np.float32, copy=False)
    norms = np.linalg.norm(M, axis=1, keepdims=True) + 1e-8
    return M / norms

def _init_insightface():
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app

def _cosine(a, B):
    # a and B rows must be L2-normalized
    return np.dot(B, a)

class ProfCamWorker(threading.Thread):
    def __init__(self, session_id, cam_source=0):
        super().__init__(daemon=True)
        self.session_id = session_id
        self.cam_source = cam_source
        self._stop = threading.Event()
        self.Session     = django_apps.get_model("academics", "Session")
        self.Attendance  = django_apps.get_model("academics", "Attendance")
        self.Student     = django_apps.get_model("academics", "Student")
        self.session = self.Session.objects.select_related("course_assignment__professor", "room").get(id=session_id)

        stu_ids, _user_ids, emb_mat, display = load_session_whitelist(self.session)
        self.display     = display or {}
        self.student_ids = list(stu_ids or [])
        self.emb_matrix  = None if emb_mat is None else _normalize_rows(np.array(emb_mat, dtype=np.float32))

        # DEBUG: shapes and sanity
        print("[DEBUG] emb_matrix shape:", None if self.emb_matrix is None else self.emb_matrix.shape)
        if self.emb_matrix is not None and len(self.student_ids) > 0:
            v0 = self.emb_matrix[0]
            print("[DEBUG] self dot v0·v0 =", float((v0 * v0).sum()))

        self.last_mark = {}
        self.face_app  = None

    def _open_camera(self):
        # Prefer DirectShow on Windows
        try:
            idx = int(self.cam_source)
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        except (ValueError, TypeError):
            dev = f"video={self.cam_source}"
            cap = cv2.VideoCapture(dev, cv2.CAP_DSHOW)

        if not cap or not cap.isOpened():
            print(f"[CAM {self.session_id}] ERROR: Cannot open camera {self.cam_source} via DSHOW")
            return None

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # warmup reads
        for _ in range(8):
            cap.read(); time.sleep(0.02)
        ok, _ = cap.read()
        if not ok:
            print(f"[CAM {self.session_id}] ERROR: warm-up read failed")
            cap.release()
            return None
        print(f"[CAM {self.session_id}] Camera opened (DSHOW) src={self.cam_source}")
        return cap

    def run(self):
        if self.emb_matrix is None or len(self.student_ids) == 0:
            print(f"[CAM {self.session_id}] No enrolled embeddings; worker not started.")
            return

        self.face_app = _init_insightface()
        cap = self._open_camera()
        if not cap:
            return

        print(f"[CAM {self.session_id}] Running with {len(self.student_ids)} enrolled vectors")
        try:
            while not self._stop.is_set():
                s = self.Session.objects.get(id=self.session_id)
                now = timezone.now()
                if s.status != "running" or (s.end_time and now >= s.end_time):
                    print(f"[CAM {self.session_id}] Session not running/ended; stopping.")
                    break

                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.03)
                    continue

                faces = self.face_app.get(frame)
                if faces:
                    print(f"[INFO] {len(faces)} face(s) detected")
                    cache.set(f"sess:{self.session_id}:last_seen", timezone.now().isoformat(), 3600)

                for f in faces:
                    emb = f.normed_embedding
                    if emb is None:
                        e = f.embedding
                        emb = e / (np.linalg.norm(e) + 1e-8)
                    emb = emb.astype(np.float32)
                    emb = emb / (np.linalg.norm(emb) + 1e-8)
                    print("[DEBUG] live emb dim:", emb.shape, "norm:", float(np.linalg.norm(emb)))

                    sims = _cosine(emb, self.emb_matrix)
                    top_idx = np.argsort(-sims)[:3]
                    top_triplet = [(int(self.student_ids[i]), float(sims[i])) for i in top_idx]
                    print(f"[DEBUG] Top-3 sims: {[(sid, round(sim,3)) for sid, sim in top_triplet]}")
                    cache.set(f"sess:{self.session_id}:last_best", str(top_triplet[0]), 60)

                    k = int(top_idx[0])
                    best_sim = float(sims[k])
                    if best_sim >= _SIM_THRESH:
                        student_id = int(self.student_ids[k])
                        last = self.last_mark.get(student_id, 0.0)
                        if time.time() - last >= _COOLDOWN_SEC:
                            self._mark_present(student_id, best_sim)
                            self.last_mark[student_id] = time.time()
                        else:
                            print(f"[COOLDOWN] student_id={student_id} sim={best_sim:.2f}")
                    else:
                        print(f"[LOW SIM] best={best_sim:.2f} < thresh={_SIM_THRESH:.2f}")

                time.sleep(0.01)
        finally:
            cap.release()
            print(f"[CAM {self.session_id}] Stopped.")

    def _mark_present(self, student_id: int, sim_score: float):
        try:
            s = self.Session.objects.select_related("course_assignment").get(id=self.session_id)
            now = timezone.now()
            status = "Present" if now <= (s.start_time + timezone.timedelta(minutes=10)) else "Late"

            obj, created = self.Attendance.objects.get_or_create(
                session_id=self.session_id,
                student_id=student_id,
                defaults={
                    "method": "face",
                    "geo_ok": False,
                    "status": status,
                    "face_conf": sim_score,
                },
            )
            name = self.display.get(student_id, str(student_id))
            if created:
                print(f"[ATTENDANCE] {status}: {name} (id={student_id}) sim={sim_score:.3f}")
                cache.set(f"sess:{self.session_id}:last_mark", f"{name} {sim_score:.2f}", 3600)
            else:
                if (obj.face_conf or 0.0) < sim_score:
                    obj.face_conf = sim_score
                    obj.save(update_fields=["face_conf"])
                    print(f"[ATTENDANCE] Updated conf → {sim_score:.3f}")
        except Exception as e:
            print(f"[ERROR] mark_present failed: {e}")

    def stop(self):
        self._stop.set()

def start_cam_for_session(session_id, cam_source=0):
    if session_id in _WORKERS:
        print(f"[CAM {session_id}] Worker already running")
        return
    w = ProfCamWorker(session_id, cam_source=cam_source)
    _WORKERS[session_id] = w
    w.start()

def stop_cam_for_session(session_id):
    w = _WORKERS.pop(session_id, None)
    if w:
        w.stop()
