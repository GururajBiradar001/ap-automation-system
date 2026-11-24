from rest_framework.permissions import BasePermission


def roles_required(*roles):
    """Factory: permission class allowing only the given roles (admin always allowed)."""
    class _P(BasePermission):
        def has_permission(self, request, view):
            u = request.user
            return bool(u and u.is_authenticated and u.has_role(*roles, "ADMIN"))
    return _P
