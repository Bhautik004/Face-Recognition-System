from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, HttpResponseForbidden
from django.core.exceptions import PermissionDenied
from django.conf import settings

import io, time
from PIL import Image
import qrcode

from apps.accounts.models import User
from .models import CourseAssignment, Session
from .forms import SessionCreateForm
from .qrsec import make_qr_token

# ----- role guard -----
def _require_prof(request):
    if not hasattr(request.user, "role") or request.user.role != getattr(User, "PROFESSOR", "professor"):
        raise PermissionDenied("Professor access only.")
    if not hasattr(request.user, "professor_profile"):
        raise PermissionDenied("Professor profile missing.")
    return request.user.professor_profile

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

# ----- 3) list sessions for this professor -----
@login_required
def session_list(request):
    prof = _require_prof(request)
    sessions = (
        Session.objects
        .select_related("course_assignment", "course_assignment__course", "room")
        .filter(course_assignment__professor=prof)
        .order_by("-start_time")
    )
    return render(request, "prof/session_list.html", {"sessions": sessions})

# ----- 4) start/stop session -----
@login_required
def session_start(request, session_id: int):
    prof = _require_prof(request)
    s = get_object_or_404(Session.objects.select_related("course_assignment__professor"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")

    s.status = Session.STATUS_RUNNING
    s.save(update_fields=["status"])
    messages.success(request, "Session started.")
    return redirect("academics:prof_session_live", session_id=s.id)

@login_required
def session_stop(request, session_id: int):
    prof = _require_prof(request)
    s = get_object_or_404(Session.objects.select_related("course_assignment__professor"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")

    s.status = Session.STATUS_STOPPED
    s.save(update_fields=["status"])
    messages.success(request, "Session stopped.")
    return redirect("academics:prof_session_list")

# ----- 5) live page (auto-refreshing QR) -----
@login_required
def session_live(request, session_id: int):
    prof = _require_prof(request)
    s = get_object_or_404(Session.objects.select_related("course_assignment__professor", "room"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")

    return render(request, "prof/session_live.html", {"session": s})

# ----- 6) QR image endpoint (rotates every step) -----
@login_required
def session_qr_png(request, session_id: int):
    prof = _require_prof(request)
    s = get_object_or_404(Session.objects.select_related("course_assignment__professor", "room"), id=session_id)
    if s.course_assignment.professor_id != prof.id:
        return HttpResponseForbidden("Not your session")
    if s.status != Session.STATUS_RUNNING:
        return HttpResponseForbidden("Session not running")

    # Generate rolling token per slot
    secret = getattr(settings, "QR_SERVER_SECRET", "change-me")
    tok, payload = make_qr_token(s.id, s.room_id, s.qr_step_seconds, secret)

    # Make QR PNG
    img = qrcode.make(tok)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")
