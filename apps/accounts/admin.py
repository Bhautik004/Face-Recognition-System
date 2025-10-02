# apps/accounts/admin.py
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, CHANGE
from apps.biometrics.admin import UserFaceInline 
from import_export.admin import ImportExportModelAdmin
from apps.biometrics.services.training import train_users
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from apps.biometrics.admin_views import biometrics_admin_urls
from django.urls import include, path
admin.site.site_header = "Face Attendance — Admin"
admin.site.site_title  = "Face Attendance"
admin.site.index_title = "Control Panel"
from django.urls import path
from django.contrib import admin
from apps.biometrics.admin_views import train_all_view


_original_get_urls = admin.site.get_urls

def get_urls_with_biometrics():
    original_get_urls = admin.site.get_urls

    def new_get_urls():
        urls = original_get_urls()
        my_urls = [
            path(
                "biometrics/train-all/",
                admin.site.admin_view(train_all_view),
                name="biometrics_train_all",
            ),
        ]
        return my_urls + urls

    return new_get_urls()




class PatchedImportExportAdmin(ImportExportModelAdmin):
    """Bypass django-import-export's old log signature on Django 5.1."""
    def _create_log_entry(self, *args, **kwargs):
        try:
            return super()._create_log_entry(*args, **kwargs)
        except TypeError:
            request_obj = None
            for a in args:
                if hasattr(a, "user"):
                    request_obj = a; break
            if request_obj is None:
                for v in kwargs.values():
                    if hasattr(v, "user"):
                        request_obj = v; break
            user_pk = getattr(getattr(request_obj, "user", None), "pk", 0)
            try:
                ct = ContentType.objects.get_for_model(self.model)
                LogEntry.objects.log_action(
                    user_id=user_pk or 0,
                    content_type_id=ct.pk,
                    object_id=None,
                    object_repr=f"Import run on {self.model._meta.label}",
                    action_flag=CHANGE,
                    change_message="import_export import executed (patched logging).",
                )
            except Exception:
                pass
            return None

@admin.register(User)
class UserAdmin(PatchedImportExportAdmin, BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    inlines = [UserFaceInline]  # <— add the inline here
    actions = ["admin_train_selected"]
    list_display = ("id", "username", "email", "role", "is_active", "is_staff", "photo_thumb")
    list_filter  = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "phone")
    ordering = ("id",)

    fieldsets = (
            (None, {"fields": ("username", "password")}),
            ("Personal info", {"fields": ("first_name","last_name","email","phone","photo")}), # optional single photo
            ("Roles", {"fields": ("role",)}),
            ("Permissions", {"fields": ("is_active","is_staff","is_superuser","groups","user_permissions")}),
            ("Important dates", {"fields": ("last_login","date_joined")}),
        )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username","email","role","password1","password2","photo"), # optional
        }),
    )

    def response_add(self, request, obj, post_url_continue=None):
        from django.shortcuts import redirect
        self.message_user(request, "User created. Now add photos below (capture or upload).")
        return redirect(f"/admin/accounts/user/{obj.pk}/change/")


    def photo_thumb(self, obj):
        if obj.photo:
            return f"✅"
        return "—"
    photo_thumb.short_description = "Photo"

    # inside your UserAdmin class:
    @admin.action(description="Train model for selected users")
    def admin_train_selected(self, request, queryset):
        ids = list(queryset.values_list("id", flat=True))
        summary = train_users(ids)
        messages.success(
            request,
            f"Training done: users={summary['users']}, embeddings={summary['embeddings']}, skipped(no-face)={summary['skipped']}"
        )

    

