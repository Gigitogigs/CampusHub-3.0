"""
core/permissions.py
====================
Generic DRF permission classes used across multiple apps.

These live in `core` because they express platform-level authority concepts
(e.g. "is this user a platform admin?") that are not specific to any single
domain app.  Domain-specific permission classes (university admin, student)
live in their respective apps (accounts/permissions.py,
universities/permissions.py).

Dependency rule
---------------
core must NOT import from any domain app (accounts, universities, clubs, etc.).
Permissions here only use the user object's own methods (is_platform_admin,
is_authenticated, etc.) which are defined on accounts.User but accessed via
the standard Django auth contract — no direct import of the User model is needed.

Permission classes
------------------
IsPlatformAdmin
    Grants access to users who hold an active global PLATFORM_ADMIN
    RoleAssignment (university=NULL, revoked_at=NULL).  Django superusers
    also pass because User.is_platform_admin() returns True for superusers.
    Django is_staff alone is NOT sufficient.
"""

from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    """
    Allow access to platform administrators only.

    The authoritative check is User.is_platform_admin(), which returns True if:
      - The user is a Django superuser (infrastructure override), OR
      - The user has platform_staff=True AND an active global PLATFORM_ADMIN
        RoleAssignment (university=NULL, revoked_at=NULL).

    The `using` parameter passed to is_platform_admin() is "ops" when the
    request is already flagged as a platform request (request.tenant_mode ==
    "platform") and None otherwise.  This ensures the grant lookup runs on
    the right database connection.

    Important: Django `is_staff` alone does NOT grant platform admin access.
    A user must hold the explicit RoleAssignment.
    """

    message = "Only platform administrators may onboard universities."

    def has_permission(self, request, view):
        """
        Return True when the requesting user is an active platform administrator.

        Checks (all must be True):
          - user is not None and is authenticated
          - user.is_active is True
          - user.status == 'active'
          - user.deleted_at is None
          - user.is_platform_admin(using=...) is True
        """
        user = request.user
        using = (
            "ops"
            if getattr(request, "tenant_mode", None) == "platform"
            else None
        )
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.status == "active"
            and user.deleted_at is None
            and user.is_platform_admin(using=using)
        )
