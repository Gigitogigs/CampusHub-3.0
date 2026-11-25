from rest_framework.permissions import BasePermission

from core.tenancy import get_current_university_id


class UniversityDetailPermission(BasePermission):
    message = "You do not have permission to view this university's details."

    def has_permission(self, request, view):
        user = request.user
        university_id = get_current_university_id()
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and university_id
            and user.university_id == university_id
        )

    def has_object_permission(self, request, view, obj):
        return bool(
            self.has_permission(request, view)
            and obj.pk == get_current_university_id()
        )


class UniversityUpdatePermission(BasePermission):
    message = "You do not have permission to update this university."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.platform_staff or user.is_staff or user.is_superuser:
            return True

        return bool(
            user.university_id == obj.pk
            and user.role_assignments.filter(
                university_id=obj.pk,
                role="university_admin",
                revoked_at__isnull=True,
            ).exists()
        )
