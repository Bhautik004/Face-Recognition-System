from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.core.exceptions import PermissionDenied


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


# academics/permissions.py


from django.core.exceptions import PermissionDenied

def require_prof_owner(user, session, allow_locked_view=False):
    """
    allow_locked_view=True → professor can VIEW locked session
    allow_locked_view=False → professor cannot MODIFY locked session
    """
    if user.is_staff:
        return

    prof = getattr(user, "professor_profile", None)

    if not prof or session.course_assignment.professor_id != prof.id:
        raise PermissionDenied("You are not allowed to modify this session.")

    # if session.is_locked and not allow_locked_view:
    #     raise PermissionDenied("This session is locked.")
