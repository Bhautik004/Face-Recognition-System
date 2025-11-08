# apps/academics/views_professor.py
import io, qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from apps.accounts.models import User
from .models import Session
from .qrsec import make_qr_token
from apps.accounts.models import User
from .models import CourseAssignment, Session
from .forms import SessionCreateForm
from .cam_worker_insight import start_cam_for_session, stop_cam_for_session
from django.http import JsonResponse
from django.utils import timezone
from django.apps import apps as django_apps
from django.core.cache import cache
from apps.biometrics.session_worker import launch_face_worker, stop_face_worker


def _require_prof(request):
    if getattr(request.user, "role", None) != getattr(User, "PROFESSOR", "professor"):
        return None
    return getattr(request.user, "professor_profile", None)

# ----- 1) list prof assignments -----
@login_required
def prof_assignments(request):
    prof = _require_prof(request)
    rows = (
        CourseAssignment.objects
        .select_related("course")
        .filter(professor=prof)
        .order_by("course__code", "term", "section")
    )
    return render(request, "prof/assignments.html", {"assignments": rows})




# apps/academics/views.py
from django.core.paginator import Paginator
from django.utils.http import urlencode

@login_required
def session_list(request):
    """Professor dashboard: list their sessions with search (by ID) and pagination."""
    q = (request.GET.get("q") or "").strip()
    try:
        per_page = int(request.GET.get("per_page", 15))
    except ValueError:
        per_page = 15
    per_page = max(5, min(per_page, 100))  # safety bounds

    base_qs = Session.objects.select_related(
        "course_assignment__course", "room", "course_assignment__professor__user"
    ).order_by("-start_time")

    if request.user.is_staff:
        qs = base_qs
    else:
        prof = getattr(request.user, "professor_profile", None)
        qs = base_qs.filter(course_assignment__professor=prof)

    # Search by Session No (ID)
    if q:
        # allow partial: "58" → id__icontains doesn't exist; do exact or "starts with" style
        # We'll accept either exact int match OR a "string contains" filter via cast.
        # Easiest: exact match if q is int; otherwise return empty.
        if q.isdigit():
            qs = qs.filter(id=int(q))
        else:
            qs = qs.none()

    paginator = Paginator(qs, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # keep current querystring (minus 'page') for pagination links
    qs_params = request.GET.copy()
    qs_params.pop('page', None)
    preserved_qs = urlencode(qs_params)
    per_page_choices = [10, 15, 20, 30, 50]

    context = {
        "sessions": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "per_page": per_page,
        "preserved_qs": preserved_qs,
        "total": qs.count(),
        "per_page_choices": per_page_choices,
    }
    return render(request, "prof/session_list.html", context)



@never_cache
# ----- 2) create session for an assignment -----
@login_required
def session_create(request, ca_id: int):
    prof = _require_prof(request)
    ca = get_object_or_404(CourseAssignment.objects.select_related("course", "professor"), id=ca_id, professor=prof)

    if request.method == "POST":
        form = SessionCreateForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.course_assignment = ca
            obj.status = Session.STATUS_SCHEDULED
            obj.save()
            messages.success(request, "Session created.")
            return redirect("academics:prof_session_list")
    else:
        form = SessionCreateForm()

    return render(request, "prof/session_create.html", {"form": form, "ca": ca})


@never_cache
@login_required
def session_start(request, session_id: int):
    prof = _require_prof(request)
    if not prof:
        messages.error(request, "Professor access only.")
        return redirect("academics:prof_session_list")

    s = get_object_or_404(Session.objects.select_related("course_assignment__professor"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        messages.error(request, "You do not own this session.")
        return redirect("academics:prof_session_list")

    # Flip to running unless already stopped
    if s.status == Session.STATUS_STOPPED:
        messages.error(request, "Session is already stopped.")
        return redirect("academics:prof_session_list")

    if s.status != Session.STATUS_RUNNING:
        s.status = Session.STATUS_RUNNING
        s.save(update_fields=["status"])
        start_cam_for_session(s.id, cam_source=0)
        cam_source = 1
        launch_face_worker(s.id, cam_source=cam_source)

   
    # Redirect to LIVE page
    # context = {"session": s,"is_running": s.status == Session.STATUS_RUNNING}

    return redirect("academics:prof_session_live", session_id=s.id)

@never_cache
@login_required
def session_stop(request, session_id: int):
    prof = _require_prof(request)
    if not prof:
        return HttpResponseForbidden("Professor access only")

    s = get_object_or_404(Session.objects.select_related("course_assignment__professor"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")

    s.status = Session.STATUS_STOPPED
    s.save(update_fields=["status"])
    stop_cam_for_session(s.id)
    stop_face_worker(session_id)
    messages.success(request, "Session stopped.")
    return redirect("academics:prof_session_list")

@never_cache
@login_required
def session_live(request, session_id: int):
    prof = _require_prof(request)
    if not prof:
        return HttpResponseForbidden("Professor access only")

    s = get_object_or_404(Session.objects.select_related("course_assignment__professor", "room"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")

    return render(request, "prof/session_live.html", {"session": s})

@never_cache
@login_required
def session_qr_png(request, session_id: int):
    prof = _require_prof(request)
    if not prof:
        return HttpResponseForbidden("Professor access only")

    s = get_object_or_404(Session.objects.select_related("course_assignment__professor", "room"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")
    if s.status != Session.STATUS_RUNNING:
        return HttpResponseForbidden("Session not running")

    tok, _payload = make_qr_token(
        session_id=s.id,
        room_id=s.room_id,
        step_seconds=s.qr_step_seconds,
        secret=getattr(settings, "QR_SERVER_SECRET", "change-me"),
    )

    img = qrcode.make(tok)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")

@never_cache
@login_required
def prof_session_status(request, session_id: int):
    prof = _require_prof(request)
    if not prof:
        return HttpResponseForbidden("Professor access only")
    s = get_object_or_404(Session, id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")
    now = timezone.now()
    seconds_left = int((s.end_time - now).total_seconds()) if s.end_time else None
    return JsonResponse({"ok": True, "status": s.status, "seconds_left": seconds_left})



@login_required
def session_recent_attendance(request, session_id: int):
    prof = _require_prof(request)
    if not prof:
        return HttpResponseForbidden("Professor access only")
    s = get_object_or_404(Session.objects.select_related("course_assignment__professor"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")

    Attendance = django_apps.get_model("academics", "Attendance")
    rows = (Attendance.objects
            .select_related("student__user")
            .filter(session_id=session_id)
            .order_by("-timestamp")[:10])

    data = [{
        "student_id": r.student_id,
        "name": (r.student.user.get_full_name() or r.student.user.username),
        "ts": r.timestamp.isoformat(timespec="seconds"),
        "method": r.method,
        "conf": r.face_conf,
        "status": r.status,
    } for r in rows]
    return JsonResponse({"ok": True, "recent": data})


@login_required
def session_stats(request, session_id: int):
    Session = django_apps.get_model("academics", "Session")
    Attendance = django_apps.get_model("academics", "Attendance")

    s = get_object_or_404(Session, id=session_id)
    
    total_face = Attendance.objects.filter(session_id=session_id, method="face").count()
    total_qr   = Attendance.objects.filter(session_id=session_id, method="qr").count()
    total_all  = total_face + total_qr
    last_seen = cache.get(f"sess:{session_id}:last_seen")


    last = (Attendance.objects
            .filter(session_id=session_id)
            .order_by("-timestamp")
            .values("student_id","method","timestamp","face_conf")
            .first())

    return JsonResponse({
        "ok": True,
        "status": s.status,
        "counts": {"face": total_face, "qr": total_qr, "total": total_all},
        "last": last,
        "last_seen": last_seen
    })