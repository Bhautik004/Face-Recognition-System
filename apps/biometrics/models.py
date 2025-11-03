from django.db import models
from django.conf import settings
import time
import os


def face_upload_path(instance, filename):
    # Get extension
    ext = os.path.splitext(filename)[1] or ".jpg"
    # Build new name: <timestamp><ext>
    new_name = f"{int(time.time())}{ext}"
    # Store under media/faces/<user_id>/<timestamp>.jpg
    return f"faces/{instance.user.id}/{new_name}"

class UserFace(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="faces")
    image = models.ImageField(upload_to=face_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.created_at:%Y-%m-%d %H:%M}"

class UserFaceEmbedding(models.Model):
    # student = models.OneToOneField("academics.Student", on_delete=models.CASCADE, related_name="embedding")
    # student = models.OneToOneField("academics.Student", on_delete=models.CASCADE, related_name="embedding", null=True, blank=True)
    face = models.OneToOneField(UserFace, on_delete=models.CASCADE, related_name="embedding")
    vector = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class UserEmbeddingTemplate(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="face_template")
    centroid = models.JSONField()
    count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
