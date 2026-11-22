"""Custom permission classes for university-scoped API access."""
from rest_framework.permissions import BasePermission
from accounts.models import RoleAssignment, University

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

class IsStudent(BasePermission):
    """Allow users without elevated roles (students) to access their university's data."""

    message = "Actions scoped for students."

    def has_permission(self, request, view):
        """Return whether the requester is an active user in the current university."""
        user = request.user
        university = getattr(request, "university", None)

        if not (
            user
            and user.is_authenticated
            and user.is_active
            and university
            and user.university_id == university.id
        ):
            return False

        elevated_roles = (
            RoleAssignment.Role.PLATFORM_ADMIN,
            RoleAssignment.Role.UNIVERSITY_ADMIN,
            RoleAssignment.Role.UNIVERSITY_MODERATOR,
        )

        return not RoleAssignment.objects.filter(
            user=user,
            university=university,
            role__in=elevated_roles,
            revoked_at__isnull=True,
        ).exists()

    def has_object_permission(self, request, view, obj):
        """Return whether the object belongs to the current university."""
        university = getattr(request, "university", None)
        if not university:
            return False

        #for tenant owned objects
        if hasattr(obj, "university_id"):
            return obj.university_id == university.id

        #For university objects themselves
        return isinstance(obj, University) and obj.id == university.id


class IsUniversityAdmin(BasePermission):
    """Allow active university administrators to manage their university's data."""

    message = "Only university administrators or staff may perform this action."

    def has_permission(self, request, view):
        """Return whether the requester has an active admin role in the current university."""
        user = request.user
        university = getattr(request, "university", None)

        if not (
            user
            and user.is_authenticated
            and user.is_active
            and university
        ):
            return False

        if user.university_id != university.id:
            return False

        return RoleAssignment.objects.filter(
            user=user,
            university=university,
            role=RoleAssignment.Role.UNIVERSITY_ADMIN,
            revoked_at__isnull=True,
        ).exists()

    def has_object_permission(self, request, view, obj):
        """Return whether the object belongs to the current university."""
        university = getattr(request, "university", None)
        if not university:
            return False

        if hasattr(obj, "university_id"):
            return obj.university_id == university.id

        return isinstance(obj, University) and obj.id == university.id

#TODO: Add IsUniversityModerator permission class

class UniversityDetailPermission(BasePermission):
    """Allow users to view their university's details."""

    message = "You do not have permission to view this university's details."

    def has_permission(self, request, view):
        """Return whether the requester is an active user in the specific university."""

        user = request.user
        university = getattr(request, "university", None)
        #TODO: Add tenant scoping for university objects


class UniversityUpdatePermission(BasePermission):
    """Allow university adminis and platform admins and staff to update their university's details."""
    #TODO: Look into university scoping for tenancy(Middleware)

    message = "You do not have permission to update this university."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
        )

    def has_object_permission(self, request, view, obj):
        user = request.user

        if (
            user.platform_staff
            or user.is_staff
            or user.is_superuser
        ):
            return True

        return bool(
            user.university_id
            and obj.id == user.university_id
            and RoleAssignment.objects.filter(
                user=user,
                university=obj,
                role=RoleAssignment.Role.UNIVERSITY_ADMIN,
                revoked_at__isnull=True,
            ).exists()
        )