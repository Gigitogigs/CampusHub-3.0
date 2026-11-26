"""
universities/permissions.py
============================
DRF permission classes specific to the universities app.

These permissions enforce who is allowed to view or modify university records.
They complement the app-level IsPlatformAdmin permission from core/permissions.py.

Permission classes
------------------
UniversityDetailPermission
    Allows an authenticated, active user to view their own university's
    private details (the full UniversitySerializer response, including settings).
    The user must belong to the university being viewed (university_id must
    match the current tenant context).

UniversityUpdatePermission
    Allows updating a university record.  Two principals are authorised:
    1. Platform admins — may update any university.
    2. University admins — may update only the university they belong to and
       hold an active university_admin grant for.

Design note on tenant_mode
--------------------------
Both classes check `request.tenant_mode` to decide which DB alias to use for
the platform-admin grant lookup.  This attribute is set by TenantMiddleware:
  "platform" → use the ops alias
  "university" or None → use the default alias

This prevents the grant lookup from accidentally running on the wrong connection
(e.g. a misconfigured request running the platform check against a tenant DB).
"""

from rest_framework.permissions import BasePermission
from core.tenancy import get_current_university_id


class UniversityDetailPermission(BasePermission):
    """
    Allow an authenticated university member to view their own university.

    has_permission
        The user must be authenticated, active, and belong to the university
        currently set in the tenant context.

    has_object_permission
        The University object being accessed must be the user's own university
        (obj.pk must equal the current tenant university_id).
    """

    message = "You do not have permission to view this university's details."

    def has_permission(self, request, view):
        """
        Return True when the user is an active member of the current tenant.

        Requires:
        - Authenticated and active user.
        - A university is set in the tenant context (get_current_university_id()
          is non-None).
        - The user's university_id matches the current tenant.
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
        )

    def has_object_permission(self, request, view, obj):
        """
        Return True when the University object is the user's own university.

        Calls has_permission() first (to re-use the user-state checks) and
        then verifies that the requested object's PK matches the tenant.
        """
        return bool(
            self.has_permission(request, view)
            and obj.pk == get_current_university_id()
        )


class UniversityUpdatePermission(BasePermission):
    """
    Allow platform admins or the university's own admin to update a university.

    has_permission
        Basic liveness check only: the user must be authenticated, active, and
        not deleted.  The *scope* check (which university) is deferred to
        has_object_permission because it requires the specific object.

    has_object_permission
        Two allowed paths:
        1. Platform admin (is_platform_admin() returns True) → allow any university.
        2. University admin → user must belong to the university AND hold an
           active university_admin RoleAssignment for that university.

    The object-level check is what prevents a university admin from updating
    a *different* university — they can only update the one they are assigned to.
    """

    message = "You do not have permission to update this university."

    def has_permission(self, request, view):
        """
        Return True when the user passes the basic liveness gate.

        This is intentionally broad: it only checks that the user is active.
        The fine-grained scope check runs in has_object_permission().
        """
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.status == "active"
            and user.deleted_at is None
        )

    def has_object_permission(self, request, view, obj):
        """
        Return True when the caller is authorised to update this specific university.

        Platform admins bypass the university check entirely.
        University admins must hold an active university_admin grant for the
        university being updated and must belong to that university.
        """
        user = request.user
        using = (
            "ops"
            if getattr(request, "tenant_mode", None) == "platform"
            else None
        )

        # Platform admin path.
        if user.is_platform_admin(using=using):
            return True

        # University admin path: user must own AND admin the specific university.
        return bool(
            user.university_id == obj.pk
            and user.role_assignments.filter(
                university_id=obj.pk,
                role="university_admin",
                revoked_at__isnull=True,
            ).exists()
        )
