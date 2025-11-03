# apps/academics/forms.py
from django import forms
from .models import Session, Attendance


class BulkDeptCSVForm(forms.Form):
    file = forms.FileField(help_text="CSV with columns: roll_no, dept_code")
    dry_run = forms.BooleanField(required=False, initial=True, help_text="Validate only, no changes")



class SessionCreateForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ["room", "start_time", "end_time", "qr_step_seconds"]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ["course_assignment", "title", "start_time", "end_time", "room","qr_step_seconds", "notes", "is_locked","status"]
        # fields = ["course_assignment", "room", "start_time", "end_time", "qr_step_seconds", "status"]

        
class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        # keep this small; professor changes status/method, not keys/timestamps
        fields = ["status", "method"] 