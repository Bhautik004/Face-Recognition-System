# apps/biometrics/session_worker.py
import os
import sys
import time
import json
import subprocess
from django.core.cache import cache
from django.apps import apps as django_apps
from django.conf import settings

LOG_DIR = getattr(settings, "SESSION_WORKER_LOG_DIR", os.path.join(settings.MEDIA_ROOT, "logs"))

def _ensure_log_dir():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception as e:
        print(f"[WORKER] WARN: could not create log dir {LOG_DIR}: {e}")

def _script_path():
    # face_session_cam.py should live next to manage.py (project root)
    return os.path.join(settings.BASE_DIR, "face_session_cam.py")

def _default_env():
    env = os.environ.copy()
    # Ensure child process can load Django
    env.setdefault("DJANGO_SETTINGS_MODULE", settings.SETTINGS_MODULE if hasattr(settings, "SETTINGS_MODULE") else f"{settings.ROOT_URLCONF.split('.')[0]}.settings")
    return env

def _log_file(session_id):
    _ensure_log_dir()
    return os.path.join(LOG_DIR, f"session_{session_id}.log")

def _is_process_running(pid):
    if not pid:
        return False
    try:
        # On Windows, this will raise if pid doesn’t exist; on POSIX, poll via os.kill(pid, 0)
        if sys.platform.startswith("win"):
            import psutil  # optional; if not installed, skip this branch
            return psutil.pid_exists(pid)
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False

def launch_face_worker(session_id, cam_source=None):
    """
    Launches face_session_cam.py in the background for the given session.
    - cam_source: optional (int or string); if None, the child defaults to 0.
    Writes logs to MEDIA_ROOT/logs/session_<id>.log
    """

    # Avoid duplicate workers
    key = f"sess:{session_id}:worker"
    existing = cache.get(key)
    if existing:
        # existing may be {"pid": 1234, "ts": ...}
        pid = existing.get("pid")
        if _is_process_running(pid):
            print(f"[WORKER] Session {session_id} already running with PID={pid}")
            return
        else:
            # stale entry
            cache.delete(key)

    script = _script_path()
    if not os.path.isfile(script):
        print(f"[WORKER] ERROR: face_session_cam.py not found at {script}")
        return

    # Optionally, derive a camera source from the Room (e.g., room.camera_source field)
    # If you want to auto-pull: 
    # Session = django_apps.get_model("academics", "Session")
    # sess = Session.objects.get(id=session_id)
    # if hasattr(sess.room, "camera_source") and sess.room.camera_source:
    #     cam_source = sess.room.camera_source

    # Build command
    cmd = [sys.executable, script, str(session_id)]
    if cam_source is not None:
        cmd.append(str(cam_source))  # our face_session_cam.py can read argv[2] as camera source

    # Prepare logs
    lf = _log_file(session_id)
    try:
        log_fh = open(lf, "a", buffering=1, encoding="utf-8", errors="replace")  # line-buffered
    except Exception as e:
        log_fh = None
        print(f"[WORKER] WARN: cannot open log file {lf}: {e}")

    # Environment
    env = _default_env()

    # Launch
    print(f"[WORKER] Launching session worker: {cmd}  (logs: {lf})")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh or subprocess.DEVNULL,
            stderr=log_fh or subprocess.STDOUT,
            cwd=settings.BASE_DIR,   # run from project root
            env=env,
            creationflags=(subprocess.DETACHED_PROCESS if sys.platform.startswith("win") else 0)
        )
    except Exception as e:
        print(f"[WORKER] ERROR: failed to start worker: {e}")
        if log_fh:
            log_fh.close()
        return

    # Cache pid so we can prevent duplicates / stop later
    cache.set(key, {"pid": proc.pid, "ts": time.time()}, timeout=60 * 60)  # 1 hour
    print(f"[WORKER] Started session {session_id} worker with PID={proc.pid}")

def stop_face_worker(session_id):
    """Optional: stop a running worker from Django."""
    key = f"sess:{session_id}:worker"
    info = cache.get(key)
    if not info:
        print(f"[WORKER] No worker found in cache for session {session_id}")
        return

    pid = info.get("pid")
    if not pid:
        cache.delete(key)
        print(f"[WORKER] No PID stored for session {session_id}")
        return

    try:
        if sys.platform.startswith("win"):
            # Windows termination (best-effort)
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            os.kill(pid, 15)  # SIGTERM
    except Exception as e:
        print(f"[WORKER] WARN: could not terminate PID={pid}: {e}")

    cache.delete(key)
    print(f"[WORKER] Stopped worker for session {session_id} (PID={pid})")
