from rest_framework import serializers
from .models import Department, Course, Professor, Room, CourseAssignment

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"

class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source="department.name")
    class Meta:
        model = Course
        fields = ["id", "code", "title", "department", "department_name", "credits", "active"]

class ProfessorSerializer(serializers.ModelSerializer):
    user_email = serializers.ReadOnlyField(source="user.email")
    user_name = serializers.SerializerMethodField()
    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    class Meta:
        model = Professor
        fields = ["id", "user", "user_email", "user_name", "department", "title", "phone", "active"]

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = "__all__"

class CourseAssignmentSerializer(serializers.ModelSerializer):
    course_code = serializers.ReadOnlyField(source="course.code")
    professor_name = serializers.ReadOnlyField(source="professor.user.get_full_name")
    class Meta:
        model = CourseAssignment
        fields = ["id", "professor", "course", "term", "section", "active", "course_code", "professor_name"]
