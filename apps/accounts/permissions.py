from rest_framework.permissions import BasePermission


class IsHR(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_hr)


class IsHROrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user and request.user.is_authenticated
        return bool(request.user and request.user.is_authenticated and request.user.is_hr)


class IsOwnerOrHR(BasePermission):
    """Object-level: owner (employee.user) or HR can access."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_hr:
            return True
        # obj may be User, Employee, Reimbursement
        user = request.user
        if hasattr(obj, "user") and obj.user_id == user.id:
            return True
        if hasattr(obj, "employee") and getattr(obj.employee, "user_id", None) == user.id:
            return True
        if obj.__class__.__name__ == "User" and obj.id == user.id:
            return True
        return False
