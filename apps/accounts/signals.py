# apps/accounts/signals.py
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from django.core.files.storage import default_storage
from django.apps import apps as django_apps
import os, shutil




# def _safe_delete_file(field_file):
#     """Delete a single FileField/ImageField file if it exists (works with any storage)."""
#     try:
#         if field_file and field_file.name and default_storage.exists(field_file.name):
#             default_storage.delete(field_file.name)
#     except Exception:
#         pass


# def _remove_dir_fs(abs_path: Path):
#     """
#     Remove a directory on local filesystem if it exists (even if empty).
#     Uses shutil.rmtree for safety; falls back to rmdir.
#     """
#     try:
#         if abs_path.exists():
#             shutil.rmtree(abs_path, ignore_errors=True)
#             # If anything still left, try rmdir
#             if abs_path.exists():
#                 try:
#                     abs_path.rmdir()
#                 except Exception:
#                     pass
#     except Exception:
#         pass


# def _prune_empty_parents(abs_dir: Path, stop_at: Path):
#     """
#     Recursively prune empty parent directories up to (but NOT including) stop_at.
#     Example: prune 'media/face/29' up to 'media/face', but never delete 'media/face' itself.
#     """
#     try:
#         current = abs_dir
#         stop_at = stop_at.resolve()
#         while True:
#             if not current.exists():
#                 current = current.parent
#             # stop if we are at or above stop_at
#             if current == stop_at or stop_at in current.parents:
#                 break
#             # remove if empty
#             try:
#                 current.rmdir()  # only works if empty
#             except Exception:
#                 break  # stop pruning if not empty
#             current = current.parent
#     except Exception:
#         pass


# @receiver(pre_save, sender=User)
# def delete_old_profile_on_change(sender, instance: User, **kwargs):
#     """When a profile photo is replaced, delete the old file so no orphans remain."""
#     if not instance.pk:
#         return
#     try:
#         old = User.objects.get(pk=instance.pk)
#     except User.DoesNotExist:
#         return
#     if old.photo and instance.photo and old.photo.name != instance.photo.name:
#         _safe_delete_file(old.photo)


# @receiver(post_delete, sender=User)
# def delete_user_media_on_delete(sender, instance: User, **kwargs):
#     """
#     After a user is deleted:
#       1) delete their profile photo (media/profiles/<username>.<ext>)
#       2) delete their face folder (media/face/<user_id>/...)
#       3) prune empty directories after all cascades finish
#     """
#     # 1) profile photo file
#     _safe_delete_file(instance.photo)

#     # 2) schedule face folder cleanup AFTER all cascading deletes complete
#     user_id = instance.id  # keep a copy before closure

#     def _cleanup():
#         storage = default_storage
#         faces_rel = f"faces/{user_id}"
#         if isinstance(storage, FileSystemStorage):
#             # local FS: remove entire directory
#             abs_dir = (Path(settings.MEDIA_ROOT) / faces_rel).resolve()
#             _remove_dir_fs(abs_dir)
#             # prune empty parents up to media/face
#             _prune_empty_parents(abs_dir, (Path(settings.MEDIA_ROOT) / "faces").resolve())
#         else:
#             # non-local storage backends: recursively delete objects with this prefix
#             try:
#                 if storage.exists(faces_rel):
#                     dirs, files = storage.listdir(faces_rel)
#                     # delete files at root
#                     for f in files:
#                         storage.delete(f"{faces_rel}/{f}")
#                     # delete subdirs
#                     for d in dirs:
#                         sub = f"{faces_rel}/{d}"
#                         _stack = [sub]
#                         while _stack:
#                             prefix = _stack.pop()
#                             d2, f2 = storage.listdir(prefix)
#                             for ff in f2:
#                                 storage.delete(f"{prefix}/{ff}")
#                             for dd in d2:
#                                 _stack.append(f"{prefix}/{dd}")
#                         # attempt to delete the now-empty dir
#                         try:
#                             storage.delete(sub)
#                         except Exception:
#                             pass
#                     # finally attempt to delete the top folder
#                     try:
#                         storage.delete(faces_rel)
#                     except Exception:
#                         pass
#             except Exception:
#                 pass

#     # ensure cleanup happens after cascading deletes (folders will be empty)
#     transaction.on_commit(_cleanup)


# apps/accounts/signals.py

def get_student_model():
    # 'academics' is the app label; by default it's the last part of the dotted path
    # of AcademicsConfig.name = "apps.academics"
    return django_apps.get_model("academics", "Student")

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_student_profile(sender, instance, created, **kwargs):
    if not created:
        return
    if getattr(instance, "role", None) == "student":
        Student = get_student_model()
        Student.objects.get_or_create(
            user=instance,
            defaults={"roll_no": f"AUTO-{instance.id}"}
        )

@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def cleanup_user_media(sender, instance, **kwargs):
    if getattr(instance, "role", None) != "student":
        return
    Student = get_student_model()
    try:
        sp = Student.objects.get(user=instance)
    except Student.DoesNotExist:
        return

    # delete profile photo
    if sp.profile_photo and default_storage.exists(sp.profile_photo.name):
        default_storage.delete(sp.profile_photo.name)

    # delete faces/<ROLL_NO> dir
    roll = (sp.roll_no or "").strip()
    if roll:
        try:
            faces_dir_abs = default_storage.path(os.path.join("faces", roll))
            shutil.rmtree(faces_dir_abs, ignore_errors=True)
        except Exception:
            # fallback: best-effort delete by prefix
            prefix = os.path.join("faces", roll)
            try:
                dirs, files = default_storage.listdir(prefix)
                for f in files:
                    default_storage.delete(os.path.join(prefix, f))
            except Exception:
                pass

    # optional: prune empty roll folders (FileSystemStorage only)
    try:
        base = default_storage.path("faces")
        for name in os.listdir(base):
            full = os.path.join(base, name)
            if os.path.isdir(full) and not os.listdir(full):
                os.rmdir(full)
    except Exception:
        pass
