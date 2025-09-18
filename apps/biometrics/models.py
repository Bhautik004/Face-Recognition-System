from django.db import models
from django.conf import settings

def face_upload_path(instance, filename):
    # /faces/<user_id>/<timestamp>.jpg
    return f"faces/{instance.user_id}/{int(instance.created_at.timestamp())}.jpg"

class UserFace(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="faces")
    image = models.ImageField(upload_to=face_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.created_at:%Y-%m-%d %H:%M}"
