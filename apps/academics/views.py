from django.shortcuts import get_object_or_404, render

# Create your views here.
from requests import Session
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import RoleAllowed
from rest_framework import viewsets, decorators, response, status
from .models import Department, Course, Professor, Room, CourseAssignment
from .serializers import (DepartmentSerializer, CourseSerializer, ProfessorSerializer,
                          RoomSerializer, CourseAssignmentSerializer)
from .permissions import IsAdmin, IsAdminOrReadOnly
import math
import csv, io
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import render
from django.contrib import messages
from .forms import BulkDeptCSVForm
from .models import Student, Department
from contextlib import nullcontext 
from django.contrib.auth.decorators import login_required

from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.exceptions import PermissionDenied

from .models import Session, Attendance, Student
from .forms import SessionForm, AttendanceForm
from .permissions import require_prof_owner


class ProfessorDashboard(APIView):
    permission_classes = [IsAuthenticated, RoleAllowed("professor","admin")]
    def get(self, request):
        # stub data for now
        return Response({"message":"Professor dashboard visible"})

class StudentDashboard(APIView):
    permission_classes = [IsAuthenticated, RoleAllowed("student","admin")]
    def get(self, request):
        return Response({"message":"Student dashboard visible"})


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related("department").all()
    serializer_class = CourseSerializer
    permission_classes = [IsAdminOrReadOnly]

class ProfessorViewSet(viewsets.ModelViewSet):
    queryset = Professor.objects.select_related("user","department").all()
    serializer_class = ProfessorSerializer
    permission_classes = [IsAdmin]  # only admin creates/edits professors

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsAdminOrReadOnly]

    @decorators.action(detail=True, methods=["get"], url_path="validate-geo")
    def validate_geo(self, request, pk=None):
        """Quick test endpoint: /api/rooms/{id}/validate-geo?lat=..&lng=.."""
        room = self.get_object()
        try:
            lat = float(request.query_params.get("lat"))
            lng = float(request.query_params.get("lng"))
        except (TypeError, ValueError):
            return response.Response({"detail":"lat & lng required"}, status=400)
        dist_m = haversine_m(float(room.latitude), float(room.longitude), lat, lng)
        return response.Response({
            "distance_m": round(dist_m, 2),
            "radius_m": room.radius_m,
            "inside": dist_m <= room.radius_m
        })

class CourseAssignmentViewSet(viewsets.ModelViewSet):
    queryset = CourseAssignment.objects.select_related("course","professor","professor__user").all()
    serializer_class = CourseAssignmentSerializer
    permission_classes = [IsAdmin]

# --- utils ---
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    require_prof_owner(request.user, session)
    attendance = (
        Attendance.objects
        .select_related("student__user")
        .filter(session=session)
        .order_by("student__roll_no")
    )
    require_prof_owner(request.user, session, allow_locked_view=True)
    return render(request, "prof/session_detail.html", {
        "session": session,
        "attendance": attendance,
        "form": SessionForm(instance=session),
    })

@login_required
def prof_assignment_list(request):
    return render(request, "prof/assignments.html", {})

@login_required
def prof_session_list(request):
    # existing queryset/render logic...
    if request.GET.get("auto") == "1":
        messages.success(request, "Session ended automatically at its scheduled end time.")
    return render(request, "prof/session_list.html", {...})


# JSON status endpoint polled by the live page
@login_required
def prof_session_status(request, session_id):
    from .models import Session  # lazy import
    s = Session.objects.filter(id=session_id).values(
        "id", "status", "end_time", "start_time"
    ).first()
    if not s:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    now = timezone.now()
    seconds_left = None
    if s["end_time"]:
        seconds_left = int((s["end_time"] - now).total_seconds())

    return JsonResponse({
        "ok": True,
        "status": s["status"],            # "scheduled"|"running"|"stopped"
        "seconds_left": seconds_left,     # may be negative after end_time
    })


@staff_member_required
def bulk_assign_department_csv(request):
    """
    Upload CSV with columns: user_id, dept_code
      - user_id: accounts.User.id
      - dept_code: Department.code (e.g., 'CS')
    If a Student row does not exist for that user, it will be created.
    """
    context = {"title": "Bulk Assign Department to Students"}  # used by admin base

    if request.method == "POST" and request.FILES.get("file"):
        dry_run = bool(request.POST.get("dry_run"))
        f = request.FILES["file"]

        # Parse CSV
        try:
            decoded = f.read().decode("utf-8", errors="ignore")
        except Exception:
            messages.error(request, "Could not read the uploaded file.")
            return render(request, "admin/academics/student/bulk_assign_department.html", context)

        try:
            reader = csv.DictReader(io.StringIO(decoded))
            # Validate headers exist
            headers = {h.strip().lower() for h in reader.fieldnames or []}
            if not {"user_id", "dept_code"}.issubset(headers):
                messages.error(request, "CSV must have headers: user_id, dept_code")
                return render(request, "admin/academics/student/bulk_assign_department.html", context)
        except Exception:
            messages.error(request, "Invalid CSV format.")
            return render(request, "admin/academics/student/bulk_assign_department.html", context)

        # Prefetch lookups
        dept_by_code = {d.code: d for d in Department.objects.all()}
        student_by_userid = {s.user_id: s for s in Student.objects.select_related("user")}

        updated = 0
        created_students = 0
        missing_depts, missing_userids, bad_rows = [], [], []

        # Use a no-op context manager for dry run; DB transaction for real run
        ctx = nullcontext() if dry_run else transaction.atomic()

        with ctx:
            for i, row in enumerate(reader, start=2):  # start=2 (header is line 1)
                raw_uid = (row.get("user_id") or "").strip()
                dept_code = (row.get("dept_code") or "").strip()

                # Validate row
                try:
                    user_id = int(raw_uid)
                except ValueError:
                    bad_rows.append(f"Line {i}: invalid user_id '{raw_uid}'")
                    continue
                if not dept_code:
                    bad_rows.append(f"Line {i}: missing dept_code")
                    continue

                dept = dept_by_code.get(dept_code)
                if not dept:
                    missing_depts.append(f"{dept_code} (line {i})")
                    continue

                stu = student_by_userid.get(user_id)
                if stu is None:
                    # Optional: ensure the user exists & is student role
                    # try:
                    #     u = User.objects.get(id=user_id)
                    #     if getattr(u, "role", "") != "student":
                    #         missing_userids.append(f"{user_id} (not a student)")
                    #         continue
                    # except User.DoesNotExist:
                    #     missing_userids.append(f"{user_id} (no such user)")
                    #     continue

                    if not dry_run:
                        try:
                            stu = Student.objects.create(user_id=user_id, department=dept)
                            student_by_userid[user_id] = stu
                            created_students += 1
                        except Exception:
                            missing_userids.append(f"{user_id} (line {i})")
                            continue
                    else:
                        created_students += 1  # simulate creation in dry run
                else:
                    if not dry_run:
                        stu.department = dept
                        stu.save(update_fields=["department"])

                updated += 1

        # Messages (admin style)
        if dry_run:
            messages.info(request, f"[DRY RUN] Would update {updated} rows. Would create {created_students} student profiles.")
        else:
            messages.success(request, f"Updated {updated} rows. Created {created_students} student profiles (if missing).")

        if missing_depts:
            messages.warning(request, f"Unknown dept codes (first few): {', '.join(missing_depts[:10])}")
        if missing_userids:
            messages.warning(request, f"Unknown/invalid user_ids (first few): {', '.join(missing_userids[:10])}")
        if bad_rows:
            messages.warning(request, f"Malformed rows (first few): {', '.join(bad_rows[:10])}")

    return render(request, "admin/academics/student/bulk_assign_department.html", context)


@login_required
@require_http_methods(["POST"])
def session_update(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    require_prof_owner(request.user, session)
    form = SessionForm(request.POST, instance=session)
    if form.is_valid():
        form.save()
    return redirect("academics:prof_session_list")
    # return redirect("academics:prof_session_list", session_id=session.id)

@login_required
@require_http_methods(["POST"])
def attendance_update_one(request, session_id, student_id):
    session = get_object_or_404(Session, id=session_id)
    require_prof_owner(request.user, session)
    att = get_object_or_404(Attendance, session=session, student_id=student_id)
    form = AttendanceForm(request.POST, instance=att)
    if form.is_valid():
        form.save()
    return redirect("academics:session_detail", session_id=session.id)

@login_required
@require_http_methods(["POST"])
def attendance_bulk_update(request, session_id):
    """
    Expect payload like:
    status_present[]=123&status_absent[]=124&status_late[]=200
    """
    session = get_object_or_404(Session, id=session_id)
    require_prof_owner(request.user, session)

    present_ids = request.POST.getlist("status_present[]")
    absent_ids  = request.POST.getlist("status_absent[]")
    late_ids    = request.POST.getlist("status_late[]")
    excused_ids = request.POST.getlist("status_excused[]")

    mapping = []
    for sid in present_ids: mapping.append((sid, "present"))
    for sid in absent_ids:  mapping.append((sid, "absent"))
    for sid in late_ids:    mapping.append((sid, "late"))
    for sid in excused_ids: mapping.append((sid, "excused"))

    with transaction.atomic():
        for student_id, status in mapping:
            Attendance.objects.filter(session=session, student_id=student_id).update(status=status, method="manual")

    return redirect("academics:session_detail", session_id=session.id)


@login_required
@require_http_methods(["POST"])
def session_lock(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    require_prof_owner(request.user, session)  # professor can lock their own
    session.is_locked = True
    session.save(update_fields=["is_locked"])
    return redirect("academics:prof_session_list", session_id=session.id)

@login_required
@require_http_methods(["POST"])
def session_unlock(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    # Only staff may unlock (or relax this to the owning prof if you prefer)
    if not request.user.is_staff:
        raise PermissionDenied("Only staff can unlock a session.")
    session.is_locked = False
    session.save(update_fields=["is_locked"])
    return redirect("academics:session_detail", session_id=session.id)