from django.urls import path
from .views import ProfessorDashboard, StudentDashboard
from .views import bulk_assign_department_csv
from . import views_student_enroll as se
# from . import views_professor1 as pv
from . import views_professor as pv
from . import views

app_name = "academics"


urlpatterns = [
    path("prof/dashboard/", ProfessorDashboard.as_view()),

    path("student/dashboard/", StudentDashboard.as_view()),
    path("academics/bulk-assign-department", bulk_assign_department_csv, name="bulk_assign_department_csv"),


    path("home/", se.student_home, name="student_home"),  # <- add this
    path("enroll/", se.available_courses, name="student_enroll_available"),
    path("enroll/mine/", se.my_enrollments, name="student_enroll_mine"),
    path("enroll/<int:ca_id>/apply/", se.apply_enroll, name="student_enroll_apply"),
    path("enroll/<int:enroll_id>/drop/", se.drop_enrollment, name="student_enroll_drop"),


# professor
    path("prof/assignments/", pv.prof_assignments, name="prof_assignments"),
    
    path("prof/sessions/<int:ca_id>/new/", pv.session_create, name="prof_session_create"),
    path("prof/sessions/", pv.session_list, name="prof_session_list"),
    path("prof/sessions/<int:session_id>/start/", pv.session_start, name="prof_session_start"),
    path("prof/sessions/<int:session_id>/stop/", pv.session_stop, name="prof_session_stop"),
    path("prof/sessions/<int:session_id>/live/", pv.session_live, name="prof_session_live"),
    path("prof/sessions/<int:session_id>/qr.png", pv.session_qr_png, name="prof_session_qr_png"),
    path("prof/sessions/status/<int:session_id>/",views.prof_session_status, name="prof_session_status"),
    path("prof/sessions/<int:session_id>/recent/", pv.session_recent_attendance, name="prof_session_recent"),

    path("prof/sessions/<int:session_id>/stats/", pv.session_stats, name="prof_session_stats"),


    path("prof/sessions/<int:session_id>/", views.session_detail, name="session_detail"),
    path("prof/sessions/<int:session_id>/update/", views.session_update, name="session_update"),
    path("prof/sessions/<int:session_id>/attendance/bulk/", views.attendance_bulk_update, name="attendance_bulk_update"),
    path("prof/sessions/<int:session_id>/attendance/<int:student_id>/update/", views.attendance_update_one, name="attendance_update_one"),

    # apps/academics/urls.py
    path("prof/sessions/<int:session_id>/lock/", views.session_lock, name="session_lock"),
    path("prof/sessions/<int:session_id>/unlock/", views.session_unlock, name="session_unlock"),

    
    path(
        "prof/assignments/",
        views.prof_assignment_list,
        name="prof_assignment_list"
    ),

]
