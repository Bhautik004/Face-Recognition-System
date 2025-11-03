# academics/services.py
from django.db import transaction
from .models import Attendance, Enrollment

def create_session_with_attendance(session, enrolled_student_ids):
    """
    session: a saved Session instance
    enrolled_student_ids: list[int] for that course/section
    """
    with transaction.atomic():
        Attendance.objects.bulk_create([
            Attendance(session=session, student_id=sid, status="absent", method="manual")
            for sid in enrolled_student_ids
        ])


def seed_session_attendance_from_enrollments(session):
    ca = session.course_assignment
    student_ids = list(
        ca.enrollments.filter(status=Enrollment.APPROVED).values_list("student_id", flat=True)
    )
    existing = set(
        Attendance.objects.filter(session=session, student_id__in=student_ids)
        .values_list("student_id", flat=True)
    )
    to_create = [
        Attendance(session=session, student_id=sid, status="Absent", method="manual")
        for sid in student_ids if sid not in existing
    ]
    if to_create:
        with transaction.atomic():
            Attendance.objects.bulk_create(to_create)