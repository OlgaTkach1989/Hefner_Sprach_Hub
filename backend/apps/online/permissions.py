from rest_framework.permissions import BasePermission


class IsOnlineAdmin(BasePermission):
    message = "Admin access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and (user.is_admin or user.is_superuser))


class IsOnlineTeacher(BasePermission):
    message = "Teacher access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and hasattr(user, "lehrer_user"))


class IsOnlineStaff(BasePermission):
    message = "Staff access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and (user.is_admin or user.is_superuser or hasattr(user, "lehrer_user"))
        )


class IsOnlineStudent(BasePermission):
    message = "Online student access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and hasattr(user, "online_profile"))
