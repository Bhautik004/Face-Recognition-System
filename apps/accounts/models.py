from django.contrib.auth.models import AbstractUser
from django.db import models

def user_photo_path(instance, filename):
    """
    Save uploaded profile photos as:
    profiles/<username>.jpg

    Example:
        media/profiles/bhautik.jpg
    """
    import os
    from django.utils.text import slugify

    # get file extension safely (e.g. .jpg, .png)
    ext = os.path.splitext(filename)[1] or ".jpg"

    # make username safe for filesystem (no spaces, etc.)
    username = slugify(instance.username or "user")

    return f"profiles/{username}{ext}"


class User(AbstractUser):
    ADMIN = "admin"
    PROFESSOR = "professor"
    STUDENT = "student"
    ROLE_CHOICES = [(ADMIN,"Admin"),(PROFESSOR,"Professor"),(STUDENT,"Student")]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STUDENT)
    employee_code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    photo = models.ImageField(upload_to=user_photo_path, blank=True, null=True)  # <—
    phone = models.CharField(max_length=30, null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

