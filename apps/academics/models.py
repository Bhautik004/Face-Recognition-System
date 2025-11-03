from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import slugify

User = get_user_model()


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=16, unique=True)   # e.g. CSE, ECE
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Professor(models.Model):
    """Professor profile tied to a User with role=PROFESSOR (enforce via permission)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="professor_profile")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="professors")
    title = models.CharField(max_length=64, blank=True)  # e.g., Assistant Professor
    phone = models.CharField(max_length=32, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name"]

    def clean(self):
        # Guard in case custom User doesn't have .role
        if not hasattr(self.user, "role"):
            raise ValidationError("Selected user does not have a 'role' attribute.")
        if getattr(User, "PROFESSOR", "professor") and self.user.role != getattr(User, "PROFESSOR", "professor"):
            raise ValidationError("Selected user is not assigned as a Professor.")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


class Course(models.Model):
    code = models.CharField(max_length=32, unique=True)  # e.g., CSE-101
    title = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="courses")  # ← keep ONE dept FK
    credits = models.PositiveSmallIntegerField(default=3)
    active = models.BooleanField(default=True)
    prerequisites = models.ManyToManyField("self", symmetrical=False, blank=True)  # optional

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.title}"


class Room(models.Model):
    """For geofence: lat/lng in decimal degrees, radius in meters."""
    name = models.CharField(max_length=120, unique=True)
    building = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)   # +/- 90.000000
    longitude = models.DecimalField(max_digits=9, decimal_places=6)  # +/- 180.000000
    radius_m = models.PositiveIntegerField(default=50)
    active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["active"])]

    def __str__(self):
        return f"{self.name} ({self.latitude}, {self.longitude}) r={self.radius_m}m"


# --------- File path helpers (now safe even if roll_no missing) ----------
def student_profile_photo_path(instance, filename):
    """
    media/students/<ROLL_OR_UID>_<username>.ext
    If roll_no present use it; else fallback to user.id
    """
    ext = filename.split(".")[-1].lower()
    base_left = instance.roll_no if hasattr(instance, "roll_no") and instance.roll_no else f"uid{instance.user_id}"
    right = slugify(instance.user.username or f"user{instance.user_id}")
    return f"students/{base_left}_{right}.{ext}"


def face_gallery_path(instance, filename):
    """
    media/faces/<ROLL_OR_UID>/<timestamp>.ext
    For training/live gallery samples
    """
    import time
    ext = filename.split(".")[-1].lower()
    left = instance.roll_no if hasattr(instance, "roll_no") and instance.roll_no else f"uid{instance.user_id}"
    return f"faces/{left}/{int(time.time())}.{ext}"


class CourseAssignment(models.Model):
    """Which professor teaches which course (optionally per term/section)."""
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="assignments")
    professor = models.ForeignKey("academics.Professor", on_delete=models.PROTECT, related_name="assignments")
    term = models.CharField(max_length=32)      # e.g., Fall 2025
    section = models.CharField(max_length=16, blank=True)
    capacity = models.PositiveIntegerField(default=60)
    enrollment_start = models.DateTimeField(null=True, blank=True)
    enrollment_end   = models.DateTimeField(null=True, blank=True)
    allow_self_enroll = models.BooleanField(default=True)

    def seats_taken(self):
        return self.enrollments.filter(status=Enrollment.APPROVED).count()

    def seats_available(self):
        return max(0, self.capacity - self.seats_taken())

    class Meta:
        unique_together = [("professor", "course", "term", "section")]
        ordering = ["course__code", "term", "section"]

    def clean(self):
        # keep data consistent: prof dept must match course dept
        if self.professor and self.course and self.professor.department_id != self.course.department_id:
            raise ValidationError("Professor department must match Course department.")

    def __str__(self):
        t = f" ({self.term}-{self.section})" if (self.term or self.section) else ""
        return f"{self.course.code} - {self.professor}{t}"


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True, related_name="students")
    # If you want filenames like CS23_001_username.jpg, add roll_no:
    roll_no = models.CharField(max_length=40, unique=True, null=True, blank=True)  # ← NEW (optional but recommended)
    phone = models.CharField(max_length=20, blank=True, default="")
    profile_photo = models.ImageField(upload_to=student_profile_photo_path, null=True, blank=True)
    active = models.BooleanField(default=True)

    # Optional: a separate model/table to store many gallery images tied to a student
    # gallery_image = models.ImageField(upload_to=face_gallery_path, null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["department"]), models.Index(fields=["roll_no"])]

    def __str__(self):
        return f"{self.user.username}"


class Enrollment(models.Model):
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    WAITLIST  = "waitlist"
    STATUS_CHOICES = [(PENDING,"Pending"), (APPROVED,"Approved"), (REJECTED,"Rejected"), (WAITLIST,"Waitlisted")]

    student = models.ForeignKey("academics.Student", on_delete=models.CASCADE, related_name="enrollments")
    course_assignment = models.ForeignKey("academics.CourseAssignment", on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    enrolled_on = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = (("student", "course_assignment"),)
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"

    def __str__(self):
        return f"{self.student} → {self.course_assignment}"


# apps/academics/models.py
class Session(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_RUNNING   = "running"
    STATUS_STOPPED   = "stopped"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_RUNNING,   "Running"),
        (STATUS_STOPPED,   "Stopped"),
    ]

    course_assignment = models.ForeignKey("academics.CourseAssignment", on_delete=models.CASCADE, related_name="sessions")
    room = models.ForeignKey("academics.Room", on_delete=models.PROTECT)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    qr_step_seconds = models.PositiveIntegerField(default=10)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    title = models.CharField(max_length=200, blank=True)        # optional, for UI
    notes = models.TextField(blank=True)                         # optional, for UI
    is_locked = models.BooleanField(default=False)

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError("end_time must be after start_time.")

    def __str__(self):
        return f"{self.course_assignment} @ {self.start_time:%Y-%m-%d %H:%M}"


# class Session(models.Model):
#     STATUS_SCHEDULED = "scheduled"
#     STATUS_RUNNING   = "running"
#     STATUS_STOPPED   = "stopped"
#     STATUS_CHOICES = [(STATUS_SCHEDULED, "Scheduled"), (STATUS_RUNNING, "Running"), (STATUS_STOPPED, "Stopped")]

#     course_assignment = models.ForeignKey("academics.CourseAssignment", on_delete=models.CASCADE, related_name="sessions")
#     room = models.ForeignKey("academics.Room", on_delete=models.PROTECT)
#     start_time = models.DateTimeField()
#     end_time = models.DateTimeField()
#     qr_step_seconds = models.PositiveIntegerField(default=10)
#     status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)

#     class Meta:
#         indexes = [models.Index(fields=["course_assignment"]), models.Index(fields=["start_time", "end_time"])]

#     def clean(self):
#         if self.end_time <= self.start_time:
#             raise ValidationError("end_time must be after start_time.")

#     def __str__(self):
#         return f"{self.course_assignment} @ {self.start_time:%Y-%m-%d %H:%M}"


class Attendance(models.Model):
    # extend your choices a bit so professor can mark manually
    METHOD_CHOICES = [("face", "Face"), ("qr", "QR"), ("manual", "Manual")]
    STATUS_CHOICES = [
        ("Present","Present"),
        ("Late","Late"),
        ("Rejected","Rejected"),     # your existing
        ("Excused","Excused"),       # optional
        ("Absent","Absent"),         # optional
    ]

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="attendance")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance")
    timestamp = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="manual")
    liveness_score = models.FloatField(null=True, blank=True)
    face_conf = models.FloatField(null=True, blank=True)
    geo_ok = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="Absent")
    note = models.CharField(max_length=200, blank=True)  # optional

    class Meta:
        unique_together = (("session", "student"),)
        indexes = [
            models.Index(fields=["session"]),
            models.Index(fields=["student"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.session} - {self.status}"

