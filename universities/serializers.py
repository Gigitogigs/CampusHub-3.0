from rest_framework import serializers
from .models import EmailDomain, University


class UniversitySerializer(serializers.ModelSerializer):
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
