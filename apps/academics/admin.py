from django.contrib import admin
from .models import Department, Professor, Course, Room, CourseAssignment

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")

@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ("__str__", "department", "active")
    list_filter = ("department", "active")
    search_fields = ("user__username", "user__first_name", "user__last_name", "user__email")

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
    list_display = ("course", "professor", "term", "section", "active")
    list_filter = ("active", "term", "course__department")
    search_fields = ("course__code", "professor__user__username", "professor__user__email")
