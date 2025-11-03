from django.contrib import admin
from .models import Department, Professor, Course, Room, CourseAssignment, Student, User
from .models import Enrollment, Session, Attendance
from .views import bulk_assign_department_csv
from django.contrib import admin
from django.urls import path
from .models import Student
from .views import bulk_assign_department_csv
from django.contrib.auth import get_user_model

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "title", "active")
    list_filter = ("department", "active")
    search_fields = ("user__username", "user__first_name", "user__last_name")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Only include users whose role is professor
        return qs.filter(user__role="professor")
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(role="professor")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "department", "credits", "active")
    list_filter = ("department", "active")
    search_fields = ("code", "title")

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "latitude", "longitude", "radius_m", "active")
    list_filter = ("active",)
    search_fields = ("name", "building")

@admin.register(CourseAssignment)
class CourseAssignmentAdmin(admin.ModelAdmin):
    list_display = ("course", "professor", "term", "section", )
    list_filter = ( "term", "course__department")
    search_fields = ("course__code", "professor__user__username", "professor__user__email")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    change_list_template = "admin/academics/student/change_list.html"  # <-- add this
    list_display = ("user", "department", "active")
    list_filter  = ("department", "active")   # ← add this
    search_fields = ("user__username", "user__email", "department__code")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "bulk-assign-department/",
                self.admin_site.admin_view(bulk_assign_department_csv),
                name="academics_student_bulk_assign_department",
            ),
        ]
        return custom + urls
    

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course_assignment", "enrolled_on")
    search_fields = ("student__roll_no","student__user__username","course_assignment__course__code")

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("course_assignment","room","start_time","end_time","status")
    list_filter = ("status", "course_assignment__term", "course_assignment__section")

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("session","student","status","timestamp","method","geo_ok")
    list_filter = ("status","method","session__course_assignment__term")
    search_fields = ("student__roll_no","student__user__username")

