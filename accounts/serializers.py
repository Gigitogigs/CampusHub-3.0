"""
accounts/serializers.py
=======================
DRF serializers for the accounts app.

Serializers sit at the boundary between the HTTP layer and the domain model.
They are responsible for:
  - Validating incoming JSON (field types, required fields, business rules
    that can be checked without a database transaction).
  - Converting model instances to JSON for responses.
  - Deciding which fields are writable vs. read-only.

Serializer inventory
--------------------
UserSerializer
    Full representation of a User, intended for authenticated self-view.
    Includes university (via UniversityPublicSerializer — the public subset,
    so private settings are never leaked through the user endpoint).
    All system-managed fields (status, platform_staff, auth_version, etc.)
    are read-only.

UserPublicSerializer
    Minimal public representation: id, full_name, and university name only.
    Safe to return in list views visible to any authenticated user in the
    same tenant.

UserCreateSerializer
    Used during registration.  Accepts email, full_name, and password only.
    Explicitly rejects any payload that includes a `university` key — university
    assignment is resolved by the registration flow (email-domain lookup), not
    by the caller.

RoleAssignmentSerializer
    Read-only representation of a RoleAssignment.  Every field is read-only
    because grants are created and revoked through dedicated service functions,
    not through a writable API endpoint.
"""

from rest_framework import serializers
from .models import User, RoleAssignment
from universities.serializers import UniversityPublicSerializer
from django.contrib.auth.password_validation import validate_password


class UserSerializer(serializers.ModelSerializer):
    """
    Full authenticated-user representation.

    The nested `university` field uses UniversityPublicSerializer to expose
    only the public university fields (name, slug, country, etc.).  The private
    `settings` JSON (feature flags, branding) is intentionally excluded from
    the public serializer and therefore never reaches this endpoint.

    All fields except `email` and `full_name` are read-only; those two can be
    updated via UserUpdateView.
    """

    university = UniversityPublicSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "university",
            "status",
            "platform_staff",
            "email_verified_at",
            "auth_version",
            "is_active",
            "date_joined",
            "created_at",
            "updated_at",
            "deleted_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "platform_staff",
            "email_verified_at",
            "auth_version",
            "is_active",
            "date_joined",
            "created_at",
            "updated_at",
            "deleted_at",
        ]


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Minimal safe representation for user listings.

    Returned by UserListView and UserPublicDetailView.  Exposes only
    id, full_name, and university name — no email, no status, no internal
    flags.
    """

    university_name = serializers.CharField(source="university.name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "university_name"]
        read_only_fields = fields


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Registration serializer — email + full_name + password only.

    Security rules enforced here:
    - `password` is validated against Django's AUTH_PASSWORD_VALIDATORS
      (minimum length, common-password list, etc.).
    - `email` is normalised to lowercase and checked for uniqueness.
    - Any payload that includes a `university` key is rejected with a 400.
      University assignment happens automatically via email-domain lookup in
      the registration flow, not via caller-supplied values.

    On success, `create()` calls User.objects.create_user() so the password is
    hashed with Argon2 (configured in settings.PASSWORD_HASHERS) rather than
    stored in plain text.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        """
        Normalise and uniqueness-check the submitted email address.

        Raises
        ------
        serializers.ValidationError
            If another User with the same normalised email already exists.
        """
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        """
        Reject payloads that try to supply a university directly.

        The registration flow resolves the university from the email domain;
        allowing callers to bypass that would let a user register in an
        arbitrary tenant.
        """
        if "university" in self.initial_data:
            raise serializers.ValidationError(
                {"university": "University assignment is resolved by the registration flow."}
            )
        return attrs

    def create(self, validated_data):
        """Create the User via the manager so the password is hashed correctly."""
        password = validated_data.pop("password")
        return User.objects.create_user(
            password=password, **validated_data,
        )


class RoleAssignmentSerializer(serializers.ModelSerializer):
    """
    Read-only representation of a RoleAssignment grant.

    All fields are read-only.  Grants are created and revoked through
    dedicated service functions (not yet exposed as API endpoints) to ensure
    the proper audit trail and platform_staff synchronization logic runs.
    Exposing a writable endpoint here would bypass those guarantees.
    """

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "user",
            "role",
            "university",
            "granted_at",
            "granted_by",
            "revoked_at",
            "revoked_by",
        ]
        read_only_fields = fields
