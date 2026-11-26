"""
universities/serializers.py
============================
DRF serializers for the universities app.

Serializer inventory
--------------------
UniversitySerializer
    Full representation including the private `settings` JSON field.
    Used only for platform-admin and university-admin endpoints.
    `slug`, `id`, and timestamps are read-only; all other fields are writable.

UniversityPublicSerializer
    Restricted public representation: no `settings`, no `status`.
    Safe to return to any authenticated user (or even anonymous visitors for
    the public detail endpoint).  Also embedded inside UserSerializer so that
    a user's university information never leaks the private settings.

EmailDomainSerializer
    Full representation of an EmailDomain row.  Currently used for
    platform-admin domain management; `id` and `created_at` are read-only.
"""

from rest_framework import serializers
from .models import EmailDomain, University


class UniversitySerializer(serializers.ModelSerializer):
    """
    Full university representation for admin use.

    Writable fields: name, short_name, country_code, timezone,
    default_currency, status, settings.

    Read-only fields: id, slug (auto-generated on creation), created_at,
    updated_at.

    Note: `settings` is a JSON field and can hold arbitrary branding/feature-
    flag data.  It MUST NOT be exposed through any public endpoint.  Use
    UniversityPublicSerializer for public or user-facing responses.
    """

    class Meta:
        model = University
        fields = [
            "id",
            "slug",
            "name",
            "short_name",
            "country_code",
            "timezone",
            "default_currency",
            "status",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class UniversityPublicSerializer(serializers.ModelSerializer):
    """
    Safe public subset of University fields.

    Excludes `settings` (private config), `status` (internal lifecycle), and
    timestamps.  Used in:
    - UniversityDetailView (public endpoint, AllowAny)
    - UserSerializer.university (embedded, so user responses never leak settings)

    All fields are read-only because this serializer is never used for writes.
    """

    class Meta:
        model = University
        fields = [
            "id",
            "slug",
            "name",
            "short_name",
            "country_code",
            "timezone",
            "default_currency",
        ]
        read_only_fields = fields


class EmailDomainSerializer(serializers.ModelSerializer):
    """
    Serializer for EmailDomain management.

    Allows platform admins to create and inspect the email domain → university
    mappings used during user registration.

    Read-only: id, created_at.
    Writable: university, domain, is_active, verified_at.
    """

    class Meta:
        model = EmailDomain
        fields = [
            "id",
            "university",
            "domain",
            "is_active",
            "verified_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
