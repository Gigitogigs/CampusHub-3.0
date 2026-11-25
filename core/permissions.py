"""Custom permission classes for university-scoped API access."""
from rest_framework.permissions import BasePermission

class IsPlatformAdminOrStaff(BasePermission):
    """Allow platform administrators or staff to onboard universities."""

    message = "Only platform administrators or staff may onboard universities."

    def has_permission(self, request, view):
        """Return whether the requester is an active platform staff member."""
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                user.platform_staff
                or user.is_staff
                or user.is_superuser
            )
        )