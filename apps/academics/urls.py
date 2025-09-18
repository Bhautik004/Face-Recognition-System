from django.urls import path
from .views import ProfessorDashboard, StudentDashboard
urlpatterns = [
    path("prof/dashboard/", ProfessorDashboard.as_view()),
    path("student/dashboard/", StudentDashboard.as_view()),
]
