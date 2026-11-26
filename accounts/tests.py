from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth import authenticate, get_user_model, get_user
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone

from accounts.models import RoleAssignment
from accounts.serializers import UserCreateSerializer
from accounts.selectors import users_visible_to
from universities.models import University


class AccountAuthenticationTests(TestCase):
    def setUp(self):
        self.university = University.objects.create(
            name="Example University",
            slug="example-university",
            country_code="KE",
            timezone="Africa/Nairobi",
            default_currency="KES",
        )
        self.user = get_user_model().objects.create_user(
            email="member@example.edu",
            password="test-password",
            full_name="Example Member",
            university=self.university,
            status="active",
        )

    def test_only_active_non_deleted_accounts_authenticate(self):
        self.assertIsNotNone(
            authenticate(email="member@example.edu", password="test-password")
        )

        self.user.status = "suspended"
        self.user.save(update_fields=["status"])
        self.assertIsNone(
            authenticate(email="member@example.edu", password="test-password")
        )

        pending_user = get_user_model().objects.create_user(
            email="pending@example.edu",
            password="test-password",
            full_name="Pending Member",
        )
        self.assertIsNone(
            authenticate(email=pending_user.email, password="test-password")
        )

        inactive_user = get_user_model().objects.create_user(
            email="inactive@example.edu",
            password="test-password",
            full_name="Inactive Member",
            university=self.university,
            status="active",
            is_active=False,
        )
        deleted_user = get_user_model().objects.create_user(
            email="deleted@example.edu",
            password="test-password",
            full_name="Deleted Member",
            university=self.university,
            status="deleted",
            deleted_at=timezone.now(),
        )
        for account in (inactive_user, deleted_user):
            self.assertIsNone(
                authenticate(email=account.email, password="test-password")
            )

    def test_password_and_account_state_changes_increment_auth_version(self):
        original_version = self.user.auth_version

        self.user.status = "suspended"
        self.user.save(update_fields=["status"])
        self.assertEqual(self.user.auth_version, original_version + 1)

        self.user.set_password("new-test-password")
        self.user.save(update_fields=["password"])
        self.assertEqual(self.user.auth_version, original_version + 2)

    def test_create_serializer_rejects_client_supplied_university(self):
        serializer = UserCreateSerializer(
            data={
                "email": "new-member@example.edu",
                "full_name": "New Member",
                "password": "LongRandomish#Z8qv2",
                "university": str(self.university.pk),
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("university", serializer.errors)

    def test_auth_version_change_invalidates_existing_session(self):
        client = Client()
        client.force_login(
            self.user,
            backend="accounts.backends.AccountStatusBackend",
        )

        request = RequestFactory().get("/")
        request.session = client.session
        self.assertEqual(get_user(request).pk, self.user.pk)

        self.user.auth_version += 1
        self.user.save(update_fields=["auth_version"])

        request = RequestFactory().get("/")
        request.session = client.session
        self.assertFalse(get_user(request).is_authenticated)


class PlatformRoleTests(TestCase):
    def test_global_platform_grant_updates_derived_flag_on_grant_and_revoke(self):
        user = get_user_model().objects.create_user(
            email="platform@example.edu",
            password="test-password",
            full_name="Platform Admin",
        )
        grant = RoleAssignment.objects.create(
            user=user,
            role=RoleAssignment.Role.PLATFORM_ADMIN,
            university=None,
        )

        user.refresh_from_db()
        self.assertTrue(user.platform_staff)
        self.assertEqual(user.auth_version, 2)
        self.assertTrue(user.has_platform_admin_role())

        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])

        user.refresh_from_db()
        self.assertFalse(user.platform_staff)
        self.assertEqual(user.auth_version, 3)
        self.assertFalse(user.has_platform_admin_role())

    def test_superuser_creation_adds_global_platform_grant(self):
        user = get_user_model().objects.create_superuser(
            email="root@example.edu",
            password="test-password",
            full_name="Root Admin",
        )

        self.assertEqual(user.status, "active")
        self.assertIsNone(user.university_id)
        self.assertTrue(user.platform_staff)
        self.assertTrue(user.has_platform_admin_role())

    def test_backfill_migrates_existing_platform_staff_flags(self):
        user = get_user_model().objects.create_user(
            email="legacy-platform@example.edu",
            password="test-password",
            full_name="Legacy Platform Admin",
            platform_staff=True,
        )
        migration = import_module(
            "accounts.migrations.0006_backfill_platform_admin_grants"
        )

        migration.backfill_platform_admin_grants(
            django_apps,
            None,
        )

        self.assertTrue(
            RoleAssignment.objects.filter(
                user=user,
                role=RoleAssignment.Role.PLATFORM_ADMIN,
                university__isnull=True,
                revoked_at__isnull=True,
            ).exists()
        )

    def test_platform_user_selector_uses_operations_connection(self):
        user = get_user_model().objects.create_superuser(
            email="selector-root@example.edu",
            password="test-password",
            full_name="Selector Root",
        )

        self.assertEqual(users_visible_to(user).db, "ops")
