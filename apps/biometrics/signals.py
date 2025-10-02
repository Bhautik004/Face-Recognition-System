from django.db.models.signals import post_save
from django.dispatch import receiver
import numpy as np
from .models import UserFace, UserFaceEmbedding, UserEmbeddingTemplate
from .services.face import embed_from_image_bytes

@receiver(post_save, sender=UserFace)
def build_embedding(sender, instance, created, **kwargs):
    if not created: return
    with instance.image.open("rb") as f:
        emb = embed_from_image_bytes(f.read())
    if emb is None:
        return  # optionally delete instance.image if no face was found
    UserFaceEmbedding.objects.create(face=instance, vector=emb.tolist())
    # recompute centroid
    all_vecs = list(UserFaceEmbedding.objects.filter(face__user=instance.user)
                    .values_list("vector", flat=True))
    if not all_vecs: return
    arr = np.array(all_vecs, dtype=np.float32)
    cent = arr.mean(axis=0, keepdims=True)
    cent = cent / (np.linalg.norm(cent, axis=1, keepdims=True) + 1e-12)
    UserEmbeddingTemplate.objects.update_or_create(
        user=instance.user,
        defaults={"centroid": cent[0].tolist(), "count": len(all_vecs)}
    )
