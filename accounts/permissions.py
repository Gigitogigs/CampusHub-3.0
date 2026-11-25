from rest_framework.permissions import BasePermission

from core.tenancy import get_current_university_id


class IsStudent(BasePermission):
    message = "Actions scoped for students."

    def has_permission(self, request, view):
        user = request.user
        university_id = get_current_university_id()
        if not (
            user
            and user.is_authenticated
            and user.is_active
            and university_id
            and user.university_id == university_id
        ):
            return False

        elevated_roles = (
            "platform_admin",
            "university_admin",
            "university_moderator",
        )
        return not user.role_assignments.filter(
            university_id=university_id,
            role__in=elevated_roles,
            revoked_at__isnull=True,
        ).exists()

    def has_object_permission(self, request, view, obj):
        university_id = get_current_university_id()
        if not university_id:
            return False
        if hasattr(obj, "university_id"):
            return obj.university_id == university_id
        return (
            getattr(getattr(obj, "_meta", None), "label_lower", None)
            == "universities.university"
            and obj.pk == university_id
        )


class IsUniversityAdmin(BasePermission):
    message = "Only university administrators or staff may perform this action."

    def has_permission(self, request, view):
        user = request.user
        university_id = get_current_university_id()
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and university_id
            and user.university_id == university_id
            and user.role_assignments.filter(
                university_id=university_id,
                role="university_admin",
                revoked_at__isnull=True,
            ).exists()
        )

    def has_object_permission(self, request, view, obj):
        university_id = get_current_university_id()
        if not university_id:
            return False
        if hasattr(obj, "university_id"):
            return obj.university_id == university_id
        return (
            getattr(getattr(obj, "_meta", None), "label_lower", None)
            == "universities.university"
            and obj.pk == university_id
        )
