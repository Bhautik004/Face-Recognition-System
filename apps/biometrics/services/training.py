# apps/biometrics/services/training.py
from typing import Iterable, Optional
import numpy as np

from django.contrib.auth import get_user_model
from apps.biometrics.models import UserFace, UserFaceEmbedding, UserEmbeddingTemplate
from apps.biometrics.services.face import embed_from_image_bytes

User = get_user_model()

def train_users(user_ids: Optional[Iterable[int]] = None) -> dict:
    """
    Build embeddings from photos & update centroids.
    If user_ids is None -> train all users who have UserFace images.
    Returns a summary dict for admin messages.
    """
    if user_ids is None:
        qs_faces = UserFace.objects.select_related("user").all()
    else:
        qs_faces = UserFace.objects.select_related("user").filter(user_id__in=list(user_ids))

    # wipe embeddings for chosen users so we rebuild cleanly
    target_user_ids = set(qs_faces.values_list("user_id", flat=True))
    if target_user_ids:
        UserFaceEmbedding.objects.filter(face__user_id__in=target_user_ids).delete()

    created_emb = 0
    skipped_no_face = 0
    users_touched = set()

    for face in qs_faces:
        with face.image.open("rb") as f:
            emb = embed_from_image_bytes(f.read())
        if emb is None:
            skipped_no_face += 1
            continue
        UserFaceEmbedding.objects.create(face=face, vector=emb.tolist())
        created_emb += 1
        users_touched.add(face.user_id)

    # rebuild centroids
    for uid in users_touched:
        vecs = list(UserFaceEmbedding.objects.filter(face__user_id=uid).values_list("vector", flat=True))
        if not vecs:
            continue
        arr = np.array(vecs, dtype=np.float32)
        cent = arr.mean(axis=0, keepdims=True)
        cent /= (np.linalg.norm(cent, axis=1, keepdims=True) + 1e-12)
        UserEmbeddingTemplate.objects.update_or_create(
            user_id=uid,
            defaults={"centroid": cent[0].tolist(), "count": len(vecs)},
        )

    return {
        "users": len(users_touched),
        "embeddings": created_emb,
        "skipped": skipped_no_face,
    }
