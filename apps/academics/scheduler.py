# apps/academics/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from django.apps import apps as django_apps
import atexit
from .cam_worker_insight import stop_cam_for_session
from apps.biometrics.session_worker import launch_face_worker

_scheduler = None

def start_due_sessions():
    """Flip SCHEDULED → RUNNING when start_time <= now < end_time."""
    Session = django_apps.get_model("academics", "Session")
    now = timezone.now()
    qs = Session.objects.filter(
        status=Session.STATUS_SCHEDULED,
        start_time__lte=now,
        end_time__gt=now,
    )
    updated = 0
    for s in qs:
        s.status = Session.STATUS_RUNNING
        s.save(update_fields=["status"])
        updated += 1

        launch_face_worker(s.id)
        print(f"[AUTO START] Session {s.id} started at {now}")
    return updated

def stop_expired_sessions():
    """Flip RUNNING → STOPPED when end_time <= now."""
    Session = django_apps.get_model("academics", "Session")
    now = timezone.now()
    qs = Session.objects.filter(
        status=Session.STATUS_RUNNING,
        end_time__lte=now,
    )
    updated = 0
    for s in qs:
        s.status = Session.STATUS_STOPPED
        s.save(update_fields=["status"])
        updated += 1
        print(f"[AUTO STOP] Session {s.id} stopped at {now}")
    return updated

def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone=str(timezone.get_current_timezone()))
    # Run both jobs every 15–30s (tune as you like)
    _scheduler.add_job(start_due_sessions, "interval", seconds=15, id="auto_start_sessions", replace_existing=True)
    _scheduler.add_job(stop_expired_sessions,  "interval", seconds=15, id="auto_stop_sessions",  replace_existing=True)
    _scheduler.start()
    atexit.register(lambda: _scheduler.shutdown(wait=False))
    print("Scheduler started with jobs: auto_start_sessions, auto_stop_sessions")


def stop_expired_sessions():
    Session = django_apps.get_model("academics", "Session")
    now = timezone.now()
    qs = Session.objects.filter(status=Session.STATUS_RUNNING, end_time__lte=now)
    for s in qs:
        s.status = Session.STATUS_STOPPED
        s.save(update_fields=["status"])
        stop_cam_for_session(s.id)
        print(f"[AUTO STOP] Session {s.id} stopped")
