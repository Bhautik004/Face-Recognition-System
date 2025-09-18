from django.contrib import admin
from django import forms
from .models import UserFace
from .forms import CaptureImageWidget

class UserFaceAdminForm(forms.ModelForm):
    class Meta:
        model = UserFace
        fields = "__all__"
        widgets = {
            "image": CaptureImageWidget,  # inject our capture widget
        }

@admin.register(UserFace)
class UserFaceAdmin(admin.ModelAdmin):
    form = UserFaceAdminForm
    list_display = ("id", "user", "created_at")
    autocomplete_fields = ("user",)

    def has_module_permission(self, request):
        # Only superusers can see/manage faces (adjust if you want staff too)
        return request.user.is_superuser
