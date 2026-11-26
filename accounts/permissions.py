"""
accounts/permissions.py
=======================
DRF permission classes specific to the accounts app.

These permissions extend BasePermission to enforce CampusHub's role-based
access model at the view level.  They are designed to be composed via
permission_classes on individual views, not used as global defaults.

Scoping model reminder
-----------------------
  - `get_current_university_id()` returns the university UUID that
    TenantMiddleware stored in the ContextVar for this request.  It is
    None for anonymous requests and for platform-admin requests (which are
    deliberately unscoped).

  - Every check here gates on BOTH the university context AND the user's
    role within it.  This prevents a university admin from one tenant from
    calling an endpoint that is momentarily resolving in another tenant's
    context (defence-in-depth; RLS will add the database-level guard later).

Permission classes
------------------
IsStudent
    Passes for authenticated, active users who belong to the current
    university and do NOT hold an elevated role (university_admin,
    university_moderator, or platform_admin) for that university.
    Object-level check verifies the object belongs to the same university.

IsUniversityAdmin
    Passes for authenticated, active users who hold an active
    university_admin grant scoped to the current university.
    Object-level check verifies the object belongs to the same university.
"""

from rest_framework.permissions import BasePermission
from core.tenancy import get_current_university_id


class IsStudent(BasePermission):
    """
    Allow requests from active users who are regular students.

    A student is an authenticated, active user belonging to the current
    university who does NOT hold any elevated role (platform_admin,
    university_admin, or university_moderator) for that university.

    has_permission  — checks user state and role absence.
    has_object_permission — checks the object belongs to the same university
                           as the requesting user.
    """

    message = "Actions scoped for students."

    def has_permission(self, request, view):
        """
        Return True when:
          - The user is authenticated, active (status='active'), and not deleted.
          - A university is set in the current tenant context.
          - The user belongs to that university.
          - The user has no elevated role in that university.
        """
        user = request.user
        university_id = get_current_university_id()
        if not (
            user
            and user.is_authenticated
            and user.is_active
            and user.status == "active"
            and user.deleted_at is None
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
        """
        Return True when the target object belongs to the current university.

        Works for any model that exposes a `university_id` attribute.
        Special-cases the University model itself (the PK is the university_id).
        """
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
    """
    Allow requests from active university administrators.

    A university admin is an authenticated, active user who holds an active
    `university_admin` RoleAssignment scoped to the current university.

    has_permission  — checks user state and grant existence.
    has_object_permission — checks the object belongs to the same university.
    """

    message = "Only university administrators may perform this action."

    def has_permission(self, request, view):
        """
        Return True when:
          - The user is authenticated, active, and not deleted.
          - A university is set in the current tenant context.
          - The user belongs to that university.
          - The user holds an active university_admin grant for that university.
        """
        user = request.user
        university_id = get_current_university_id()
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.status == "active"
            and user.deleted_at is None
            and university_id
            and user.university_id == university_id
            and user.role_assignments.filter(
                university_id=university_id,
                role="university_admin",
                revoked_at__isnull=True,
            ).exists()
        )

    def has_object_permission(self, request, view, obj):
        """
        Return True when the target object belongs to the current university.

        Uses the same logic as IsStudent.has_object_permission.
        """
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
