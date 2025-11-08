# face_session_cam.py
import os, sys, time
import numpy as np
import cv2
from datetime import datetime
from django.core.cache import cache

# ---------------- Django bootstrap ----------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.utils import timezone
from django.apps import apps as django_apps
from django.db import transaction

# ---------------- Config ----------------
SIM_THRESHOLD = 0.50        # start a bit permissive; raise to 0.55-0.60 later
COOLDOWN_S    = 30          # do not re-mark the same student within this many seconds
WARMUP_FRAMES = 10
FRAME_SLEEP   = 0.02        # small sleep during warmup/read fail
SHOW_PREVIEW  = os.environ.get("PREVIEW", "0") == "1"  # set PREVIEW=1 to see a window

# ---------------- Models (lazy via apps) ----------------
# We'll use get_model inside helpers so the module import order never breaks.

# ---------------- Camera helpers ----------------
def open_cam(source=1, width=1280, height=720, force_mjpg=False):
    """
    Open camera with DirectShow only (stable on your machine).
    `source` can be int index (0) or device name string: "video=<name>".
    Returns an opened cv2.VideoCapture or None.
    """
    # try numeric first
    cap = None
    try:
        idx = int(source)
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    except (ValueError, TypeError):
        dev = f"video={source}"
        cap = cv2.VideoCapture(dev, cv2.CAP_DSHOW)

    if not cap or not cap.isOpened():
        print(f"[ERROR] DSHOW open failed for source={source}")
        return None

    # basic config
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)
    if force_mjpg:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

    # warm-up
    for _ in range(WARMUP_FRAMES):
        cap.read()
        time.sleep(FRAME_SLEEP)

    ok, _ = cap.read()
    if not ok:
        print("[ERROR] DSHOW read failed during warm-up")
        cap.release()
        return None

    print(f"[INFO] Camera opened via DSHOW (src={source}, {int(width)}x{int(height)})")
    return cap


# ---------------- Embeddings loader ----------------
def load_gallery_for_session(session_id):
    """
    Return dict[user_id(str) -> normalized centroid vector] for students
    enrolled in the session's course_assignment.
    """
    import numpy as np
    Session = django_apps.get_model("academics", "Session")
    Enrollment = django_apps.get_model("academics", "Enrollment")
    UserEmbeddingTemplate = django_apps.get_model("biometrics", "UserEmbeddingTemplate")

    sess = Session.objects.select_related("course_assignment").get(id=session_id)

    # enrolled students → user_ids
    user_ids = list(
        Enrollment.objects.filter(course_assignment=sess.course_assignment)
        .values_list("student__user_id", flat=True)
    )
    if not user_ids:
        print(f"[WARN] No enrollments found for session {session_id}")
        return {}

    qs = UserEmbeddingTemplate.objects.filter(user_id__in=user_ids)
    gallery = {}
    for row in qs:
        v = np.array(row.centroid, dtype=np.float32)
        v /= (np.linalg.norm(v) + 1e-8)
        gallery[str(row.user_id)] = v

    return gallery


# ---------------- Matching helper ----------------
def best_match(emb, gallery):
    """Return (best_user_id:str or None, best_sim:float). emb must be L2-normalized np.float32."""
    best_id, best_sim = None, -1.0
    for uid, vec in gallery.items():
        s = float(np.dot(emb, vec))  # cosine since both normalized
        if s > best_sim:
            best_id, best_sim = uid, s
    return best_id, best_sim


# ---------------- Attendance writer ----------------
def mark_attendance_for_match(session_id, matched_user_id, sim_score):
    """
    Create/update Attendance row for this student if session is running
    and student is enrolled. Logs reasons when skipping.
    """
    Session     = django_apps.get_model("academics", "Session")
    Student     = django_apps.get_model("academics", "Student")
    Enrollment  = django_apps.get_model("academics", "Enrollment")
    Attendance  = django_apps.get_model("academics", "Attendance")

    now = timezone.now()
    sess = Session.objects.select_related("course_assignment").get(id=session_id)

    if sess.status != "running":
        print(f"[SKIP] Session {session_id} not running (status={sess.status})")
        return False

    # End-time safety: stop if past end_time
    if sess.end_time and now >= sess.end_time:
        print(f"[STOP] Session {session_id} ended at {sess.end_time}.")
        return False

    # Map user -> student
    try:
        student = Student.objects.get(user_id=matched_user_id)
    except Student.DoesNotExist:
        print(f"[SKIP] No Student found for user_id={matched_user_id}")
        return False

    # Must be enrolled in this course_assignment
    enrolled = Enrollment.objects.filter(
        student=student,
        course_assignment=sess.course_assignment
    ).exists()
    if not enrolled:
        print(f"[SKIP] Student {student.id} user_id={matched_user_id} not enrolled in this course.")
        return False

    # Present vs Late (10-min grace)
    LATE_GRACE_MIN = 10
    status = "Present" if now <= (sess.start_time + timezone.timedelta(minutes=LATE_GRACE_MIN)) else "Late"

    try:
        with transaction.atomic():
            obj, created = Attendance.objects.get_or_create(
                session=sess,
                student=student,
                defaults={
                    "method": "face",
                    "liveness_score": None,
                    "face_conf": float(sim_score),
                    "geo_ok": False,
                    "status": status,
                }
            )
            if created:
                print(f"[ATTENDANCE] MARKED {status}: student_id={student.id} user_id={matched_user_id} "
                      f"sim={sim_score:.3f} session={session_id}")
                cache.incr(f"sess:{session_id}:face_seen", ignore_key_check=True)

                return True
            else:
                # update confidence if this pass is stronger
                old = obj.face_conf or 0.0
                if sim_score > old:
                    obj.face_conf = float(sim_score)
                    obj.save(update_fields=["face_conf"])
                    print(f"[ATTENDANCE] Already marked — updated conf: {old:.3f} -> {obj.face_conf:.3f}")
                else:
                    print(f"[ATTENDANCE] Already marked — conf stays {old:.3f}")
                    cache.incr(f"sess:{session_id}:face_seen", ignore_key_check=True)

                return True
    except Exception as e:
        print(f"[ERROR] Attendance insert failed: {e}")
        return False


# ---------------- InsightFace ----------------
def init_insightface():
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app


# ---------------- Main loop ----------------
def run_session_worker(session_id, cam_source=0):
    print(f"[INFO] Starting worker for session_id={session_id}, cam_source={cam_source}")

    # Load embeddings only for enrolled students
    gallery = load_gallery_for_session(session_id)
    print(f"[INFO] Loaded {len(gallery)} student embeddings for session {session_id}")
    if not gallery:
        print("[WARN] No enrolled embeddings found; worker will run but won’t mark.")
    app = init_insightface()

    # open camera
    cap = open_cam(cam_source, width=1280, height=720, force_mjpg=False)
    if not cap:
        print("[ERROR] Cannot open camera. Exiting.")
        return

    Session = django_apps.get_model("academics", "Session")
    last_mark_by_user = {}  # cooldown: user_id -> last_ts
    last_seen_faces_ts = 0

    # preview window
    if SHOW_PREVIEW:
        cv2.namedWindow("Session Camera", cv2.WINDOW_NORMAL)

    try:
        while True:
            # stop when session ends or is stopped
            sess = Session.objects.get(id=session_id)
            now = timezone.now()
            if sess.status != "running":
                print(f"[STOP] Session status is {sess.status}, stopping worker.")
                break
            if sess.end_time and now >= sess.end_time:
                print(f"[STOP] Reached end_time={sess.end_time}, stopping worker.")
                break

            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            faces = app.get(frame)
            # debug
            if faces:
                last_seen_faces_ts = time.time()
                print(f"[INFO] {len(faces)} face(s) detected in frame.")

            for f in faces:
                emb = f.normed_embedding
                if emb is None:
                    e = f.embedding
                    emb = e / (np.linalg.norm(e) + 1e-8)
                emb = emb.astype(np.float32)

                best_id, best_sim = best_match(emb, gallery)
                x1, y1, x2, y2 = [int(x) for x in f.bbox]
                color = (0, 255, 0) if (best_id and best_sim >= SIM_THRESHOLD) else (0, 0, 255)
                label = f"{best_id or 'unknown'} {best_sim:.2f}"

                # draw in preview
                if SHOW_PREVIEW:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, max(0, y1 - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                # marking
                if best_id and best_sim >= SIM_THRESHOLD:
                    now_ts = time.time()
                    if now_ts - last_mark_by_user.get(best_id, 0) >= COOLDOWN_S:
                        ok = mark_attendance_for_match(session_id, int(best_id), best_sim)
                        if ok:
                            last_mark_by_user[best_id] = now_ts
                    else:
                        print(f"[COOLDOWN] user_id={best_id} sim={best_sim:.2f}")
                else:
                    if best_id:
                        print(f"[LOW SIM] user_id={best_id} sim={best_sim:.2f} < {SIM_THRESHOLD}")

            if SHOW_PREVIEW:
                cv2.imshow("Session Camera", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("[INFO] q pressed — stopping preview worker.")
                    break

    finally:
        cap.release()
        if SHOW_PREVIEW:
            cv2.destroyAllWindows()
        print("[INFO] Worker stopped/cleaned up.")


# ---------------- CLI entry ----------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python face_session_cam.py <SESSION_ID> [CAM_SOURCE]")
        sys.exit(1)
    sess_id = int(sys.argv[1])
    cam_src = sys.argv[2] if len(sys.argv) >= 3 else 0
    # cast to int if it's a digit
    if isinstance(cam_src, str) and cam_src.isdigit():
        cam_src = int(cam_src)
    run_session_worker(sess_id, cam_src)
