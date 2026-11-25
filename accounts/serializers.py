#Converts model instances to JSON and validates incoming JSON
from rest_framework import serializers
from .models import User, RoleAssignment
from universities.serializers import UniversityPublicSerializer
from django.contrib.auth.password_validation import validate_password

class UserSerializer(serializers.ModelSerializer):
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
    university_name = serializers.CharField(source="university.name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "university_name"]
        read_only_fields = fields


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "university", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        """
        Validate that the email is unique and not already in use.
        """
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(
            password=password, **validated_data,
        )


class RoleAssignmentSerializer(serializers.ModelSerializer):
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
        read_only_fields = ["id", "granted_at", "granted_by", "revoked_at", "revoked_by"]