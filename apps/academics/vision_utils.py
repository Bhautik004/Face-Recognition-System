# apps/academics/vision_utils.py
import numpy as np
from django.apps import apps as django_apps

def load_whitelist_for_session(session):
    """
    Returns: [(student_id, np_vector, display_name), ...] for students
    enrolled in session.course_assignment and having an embedding.
    """
    Enrollment = django_apps.get_model("academics", "Enrollment")
    UserFaceEmbedding = django_apps.get_model("academics", "UserFaceEmbedding")

    # enrolled students for this assignment
    student_ids = list(
        Enrollment.objects.filter(course_assignment=session.course_assignment)
        .values_list("student_id", flat=True)
    )
    if not student_ids:
        return []

    # get their embeddings
    emb_rows = (
        UserFaceEmbedding.objects
        .select_related("student__user")
        .filter(student_id__in=student_ids)
    )

    whitelist = []
    for row in emb_rows:
        vec = np.frombuffer(row.vector, dtype=np.float32)
        name = row.student.user.get_full_name() or row.student.user.username
        whitelist.append((row.student_id, vec, name))
    return whitelist

def cosine_sim(a, b):
    # a: (D,), b: (N,D) or (D,)
    if b.ndim == 1:
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
        return float(np.dot(a, b) / denom)
    # vectorized
    denom = (np.linalg.norm(a) * np.linalg.norm(b, axis=1) + 1e-8)
    return np.dot(b, a) / denom
