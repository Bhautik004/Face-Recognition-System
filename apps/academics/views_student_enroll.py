# apps/academics/views_student_enroll.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from apps.accounts.models import User
from .models import CourseAssignment, Enrollment

def _require_student(request):
    # expect a custom User.role; adjust if you use groups instead
    if not hasattr(request.user, "role") or request.user.role != getattr(User, "STUDENT", "student"):
        raise PermissionDenied("Student access only.")
    if not hasattr(request.user, "student_profile"):
        raise PermissionDenied("Student profile missing.")
    return request.user.student_profile

@login_required
def available_courses(request):
    student = _require_student(request)
    now = timezone.now()

    qs = CourseAssignment.objects.select_related("course", "professor", "professor__user")
    # same department as student (adjust if you want cross-dept)
    if student.department_id:
        qs = qs.filter(course__department_id=student.department_id)

    # not already enrolled in any status
    qs = qs.exclude(enrollments__student=student)

    # self-enroll only & window respected
  

    qs = qs.filter(allow_self_enroll=True).filter(
    Q(enrollment_start__isnull=True) | Q(enrollment_start__lte=now),
    Q(enrollment_end__isnull=True)   | Q(enrollment_end__gte=now),
    ).order_by("course__code", "term", "section")




    context = {
        "student": student,
        "assignments": qs,
    }
    return render(request, "student/enroll_available.html", context)


@login_required
@transaction.atomic
def apply_enroll(request, ca_id: int):
    if request.method != "POST":
        return redirect("academics:student_enroll_available")

    student = _require_student(request)
    ca = get_object_or_404(
        CourseAssignment.objects.select_related("course", "professor", "course__department"),
        id=ca_id,
        allow_self_enroll=True,
    )

    # (optional) department guard
    if student.department_id and ca.course.department_id and student.department_id != ca.course.department_id:
        messages.error(request, "This course is not available for your department.")
        return redirect("academics:student_enroll_available")

    # already enrolled?
    if Enrollment.objects.filter(student=student, course_assignment=ca).exists():
        messages.info(request, "You already have an enrollment record for this course.")
        return redirect("academics:student_enroll_mine")

    # capacity-aware auto-approval
    from .models import Enrollment as E
    status = E.APPROVED if ca.seats_available() > 0 else E.WAITLIST

    Enrollment.objects.create(student=student, course_assignment=ca, status=status)

    if status == E.APPROVED:
        messages.success(request, f"Enrolled in {ca.course.code} ({ca.term}-{ca.section}).")
    else:
        messages.warning(request, f"{ca.course.code} is full. You are waitlisted.")

    return redirect("academics:student_enroll_mine")


@login_required
def my_enrollments(request):
    student = _require_student(request)
    rows = (
        Enrollment.objects
        .select_related("course_assignment", "course_assignment__course", "course_assignment__professor__user")
        .filter(student=student)
        .order_by("-enrolled_on")
    )
    return render(request, "student/enroll_mine.html", {"student": student, "enrollments": rows})


@login_required
@transaction.atomic
def drop_enrollment(request, enroll_id: int):
    if request.method != "POST":
        return redirect("academics:student_enroll_mine")

    student = _require_student(request)
    enr = get_object_or_404(Enrollment.objects.select_related("course_assignment", "course_assignment__course"),
                            id=enroll_id, student=student)

    # policy: allow drop if session not started yet? (keep simple: always allow)
    enr.delete()
    messages.success(request, f"Dropped {enr.course_assignment.course.code}.")
    return redirect("academics:student_enroll_mine")

@login_required
def student_home(request):
    student = _require_student(request)
    return render(request, "student/home.html", {"student": student})