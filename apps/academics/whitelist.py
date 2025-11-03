# apps/academics/whitelist.py
import numpy as np
from django.apps import apps as django_apps

def load_session_whitelist(session):
    """
    Returns:
      student_ids: [int, ...]         # academic Student ids
      user_ids:    [int, ...]         # auth User ids (for embedding table)
      emb_matrix:  np.ndarray shape (N, D)
      display:     dict student_id -> display string
    """
    Enrollment = django_apps.get_model("academics", "Enrollment")
    Student    = django_apps.get_model("academics", "Student")
    UserEmb    = django_apps.get_model("biometrics", "UserEmbeddingTemplate")  # user_id -> centroid (list)

    # enrolled students in this assignment
    stu_ids = list(
        Enrollment.objects.filter(course_assignment=session.course_assignment)
        .values_list("student_id", flat=True)
    )
    if not stu_ids:
        return [], [], None, {}

    # map Student -> User ids
    rows = Student.objects.select_related("user").filter(id__in=stu_ids)
    user_by_student = {s.id: s.user_id for s in rows}
    display = {s.id: (s.user.get_full_name() or s.user.username) for s in rows}

    # fetch centroids for those users
    emb_rows = UserEmb.objects.filter(user_id__in=list(user_by_student.values()))
    # build aligned arrays: only keep students that actually have a centroid
    v_student_ids, v_user_ids, vecs = [], [], []
    for e in emb_rows:
        # find the student id(s) for this user_id (there should be exactly one)
        for sid, uid in user_by_student.items():
            if uid == e.user_id:
                v_student_ids.append(sid)
                v_user_ids.append(uid)
                v = np.array(e.centroid, dtype=np.float32)
                v = v / (np.linalg.norm(v) + 1e-8)
                vecs.append(v)
                break

    if not vecs:
        return [], [], None, {}

    emb_matrix = np.vstack(vecs)  # (N, D)
    return v_student_ids, v_user_ids, emb_matrix, display
