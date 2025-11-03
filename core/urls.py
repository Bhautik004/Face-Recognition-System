"""core URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from apps.accounts.views import LandingView, RoleLoginView, role_redirect, professor_home
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static
from apps.biometrics import admin_views
from apps.biometrics.admin_views import train_all_view 
from django.contrib import admin
from django.urls import path, include
from apps.biometrics.admin_views import train_all_view 
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.academics.views import (DepartmentViewSet, CourseViewSet, ProfessorViewSet,
                             RoomViewSet, CourseAssignmentViewSet)
from apps.academics.views import bulk_assign_department_csv 

router = DefaultRouter()
router.register(r"departments", DepartmentViewSet)
router.register(r"courses", CourseViewSet)
router.register(r"professors", ProfessorViewSet)
router.register(r"rooms", RoomViewSet)
router.register(r"assignments", CourseAssignmentViewSet)

@login_required
def route_after_login(request):
    role = getattr(request.user, "role", "student")
    if role in ("admin","professor"):
        return HttpResponse("Professor/Admin Home (build me)")
    return HttpResponse("Student Home (build me)")


urlpatterns = [
    
    path("", LandingView.as_view(), name="landing"),
    path("login/", RoleLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="landing"), name="logout"),

    # where we bounce after successful login
    path("route-after-login/", role_redirect, name="route_after_login"),

    # role homes (stub pages; replace with your real dashboards)
   
    path("prof/home/", professor_home, name="prof_home"),
    # path("student/home/", student_home, name="student_home"),

    path('admin/biometrics/train-all/', admin.site.admin_view(admin_views.train_all_view), name='biometrics_train_all'),
    # path("academics/bulk-assign-department", bulk_assign_department_csv, name="bulk_assign_department_csv"),

    path("admin/", admin.site.urls),
    
    path('accounts/', include('apps.accounts.urls')),

    # path('academics/', include('apps.academics.urls')),
    # path("",include("apps.academics.urls")),
    path("academics/", include(("apps.academics.urls", "academics"), namespace="academics")),

    path("student/home", include(("apps.academics.urls", "academics"), namespace="academics")),




]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)