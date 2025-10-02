from django.contrib import admin, messages
from django.urls import path, reverse
from django import forms
from django.http import HttpResponseRedirect
from .models import UserFace
from . import services
# reuse your widget template: accounts/widgets/capture_file.html
class CaptureImageWidget(forms.ClearableFileInput):
    template_name = "accounts/widgets/capture_file.html"

class UserFaceInlineForm(forms.ModelForm):
    class Meta:
        model = UserFace
        fields = ("image",)
        widgets = {"image": CaptureImageWidget}

class UserFaceInline(admin.TabularInline):
    model = UserFace
    form = UserFaceInlineForm
    extra = 3   # show 3 rows ready to capture/upload


