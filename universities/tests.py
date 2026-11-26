from importlib import import_module
from types import SimpleNamespace

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from django.urls import resolve

from .models import University
from .permissions import UniversityUpdatePermission
from .serializers import UniversityPublicSerializer
from accounts.models import RoleAssignment
from core.permissions import IsPlatformAdmin


class UniversityPublicSerializerTests(SimpleTestCase):
    def test_public_representation_does_not_expose_private_settings(self):
        university = University(
            name="Example University",
            slug="example-university",
            country_code="KE",
            timezone="Africa/Nairobi",
            default_currency="KES",
            settings={"feature_flags": {"private": True}},
        )

        self.assertNotIn("settings", UniversityPublicSerializer(university).data)


class UniversityRouteTests(SimpleTestCase):
    def test_canonical_and_legacy_list_paths_use_universities_view(self):
        from .views import UniversityListView

        for path in ("/api/v1/universities/", "/api/accounts/universities/"):
            self.assertIs(resolve(path).func.view_class, UniversityListView)


class UniversityUpdatePermissionTests(TestCase):
    def setUp(self):
        self.university = University.objects.create(
            name="Example University",
            slug="example-university",
            country_code="KE",
            timezone="Africa/Nairobi",
            default_currency="KES",
        )
        self.user = get_user_model().objects.create_user(
            email="admin@example.edu",
            password="test-password",
            full_name="University Admin",
            university=self.university,
            status="active",
        )
        RoleAssignment.objects.create(
            user=self.user,
            university=self.university,
            role=RoleAssignment.Role.UNIVERSITY_ADMIN,
        )

    def test_university_admin_can_update_own_university(self):
        permission = UniversityUpdatePermission()
        request = SimpleNamespace(user=self.user)

        self.assertTrue(permission.has_permission(request, None))
        self.assertTrue(
            permission.has_object_permission(request, None, self.university)
        )

    def test_student_cannot_update_university(self):
        self.user.role_assignments.all().delete()
        permission = UniversityUpdatePermission()
        request = SimpleNamespace(user=self.user)

        self.assertFalse(
            permission.has_object_permission(request, None, self.university)
        )

    def test_global_platform_admin_can_update_university(self):
        platform_user = get_user_model().objects.create_user(
            email="platform@example.edu",
            password="test-password",
            full_name="Platform Admin",
            status="active",
            platform_staff=True,
        )
        RoleAssignment.objects.create(
            user=platform_user,
            university=None,
            role=RoleAssignment.Role.PLATFORM_ADMIN,
        )
        permission = UniversityUpdatePermission()

        self.assertTrue(
            permission.has_object_permission(
                SimpleNamespace(user=platform_user),
                None,
                self.university,
            )
        )

    def test_django_staff_without_application_grant_is_not_platform_admin(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        permission = IsPlatformAdmin()

        self.assertFalse(
            permission.has_permission(SimpleNamespace(user=self.user), None)
        )

    def test_revoked_platform_grant_no_longer_authorizes_global_update(self):
        platform_user = get_user_model().objects.create_user(
            email="former-platform@example.edu",
            password="test-password",
            full_name="Former Platform Admin",
            status="active",
            platform_staff=True,
        )
        grant = RoleAssignment.objects.create(
            user=platform_user,
            university=None,
            role=RoleAssignment.Role.PLATFORM_ADMIN,
        )
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])

        self.assertFalse(
            UniversityUpdatePermission().has_object_permission(
                SimpleNamespace(user=platform_user),
                None,
                self.university,
            )
        )


class RegistryContentTypeMigrationTests(TestCase):
    def test_relabels_legacy_content_type_in_place_without_destination(self):
        ContentType.objects.filter(
            app_label="universities",
            model="emaildomain",
        ).delete()
        legacy_type = ContentType.objects.create(
            app_label="accounts",
            model="emaildomain",
        )
        legacy_id = legacy_type.pk

        migration = import_module(
            "universities.migrations.0003_move_registry_content_types"
        )
        migration.move_registry_content_types(apps, None)

        legacy_type.refresh_from_db()
        self.assertEqual(legacy_type.pk, legacy_id)
        self.assertEqual(legacy_type.app_label, "universities")

    def test_merges_legacy_permission_grants_and_admin_log_references(self):
        user = get_user_model().objects.create_user(
            email="content-type@example.edu",
            password="test-password",
            full_name="Content Type User",
        )
        legacy_type = ContentType.objects.create(
            app_label="accounts",
            model="university",
        )
        destination_type = ContentType.objects.get(
            app_label="universities",
            model="university",
        )
        legacy_permission = Permission.objects.create(
            content_type=legacy_type,
            codename="custom_university_permission",
            name="Can use a custom university permission",
        )
        destination_permission = Permission.objects.create(
            content_type=destination_type,
            codename="custom_university_permission",
            name="Can use a custom university permission",
        )
        group = Group.objects.create(name="university-permission-test")
        group.permissions.add(legacy_permission)
        user.user_permissions.add(legacy_permission)
        log_entry = LogEntry.objects.create(
            user=user,
            content_type=legacy_type,
            object_id="legacy-object",
            object_repr="Legacy University",
            action_flag=ADDITION,
        )

        migration = import_module(
            "universities.migrations.0003_move_registry_content_types"
        )
        migration.move_registry_content_types(apps, None)

        self.assertFalse(
            ContentType.objects.filter(
                app_label="accounts",
                model="university",
            ).exists()
        )
        self.assertTrue(
            group.permissions.filter(pk=destination_permission.pk).exists()
        )
        self.assertTrue(
            user.user_permissions.filter(pk=destination_permission.pk).exists()
        )
        log_entry.refresh_from_db()
        self.assertEqual(log_entry.content_type_id, destination_type.pk)

        migration.restore_registry_content_types(apps, None)
        self.assertTrue(
            ContentType.objects.filter(
                app_label="accounts",
                model="university",
            ).exists()
        )
