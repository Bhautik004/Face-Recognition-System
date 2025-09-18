from rest_framework.permissions import BasePermission

class RoleAllowed(BasePermission):
    def __init__(self, *roles): self.roles = roles
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in self.roles
