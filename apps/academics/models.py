from django.db import models
from django.contrib.auth import get_user_model

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

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


class Course(models.Model):
    code = models.CharField(max_length=32, unique=True)  # e.g., CSE-101
    title = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="courses")
    credits = models.PositiveSmallIntegerField(default=3)
    active = models.BooleanField(default=True)

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


class CourseAssignment(models.Model):
    """Which professor teaches which course (optionally per term/section)."""
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE, related_name="assignments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    term = models.CharField(max_length=16, blank=True)    # e.g., Fall25
    section = models.CharField(max_length=8, blank=True)  # e.g., A, B
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("professor", "course", "term", "section")]
        ordering = ["course__code", "term", "section"]

    def __str__(self):
        t = f" ({self.term}-{self.section})" if (self.term or self.section) else ""
        return f"{self.course.code} - {self.professor}{t}"
