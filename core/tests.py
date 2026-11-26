from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from accounts.models import User
from universities.models import University
from core.tenancy import (
    TenantMiddleware,
    get_current_university_id,
)


class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.university = University.objects.create(
            name="Example University",
            slug="example-university",
            country_code="KE",
            timezone="Africa/Nairobi",
            default_currency="KES",
        )
        self.user = User.objects.create_user(
            email="member@example.edu",
            password="test-password",
            full_name="Example Member",
            university=self.university,
            status="active",
        )

    def _request_for(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_tenant_context_is_reset_after_successful_response(self):
        middleware = TenantMiddleware(
            lambda request: get_current_university_id()
        )

        self.assertEqual(
            middleware(self._request_for(self.user)),
            self.university.pk,
        )
        self.assertIsNone(get_current_university_id())

    def test_tenant_context_is_reset_after_response_raises(self):
        def fail(_request):
            raise RuntimeError("request failed")

        middleware = TenantMiddleware(fail)

        with self.assertRaises(RuntimeError):
            middleware(self._request_for(self.user))
        self.assertIsNone(get_current_university_id())

    def test_non_active_account_is_rejected(self):
        self.user.status = "suspended"
        self.user.save(update_fields=["status"])
        middleware = TenantMiddleware(lambda _request: None)

        with self.assertRaises(PermissionDenied):
            middleware(self._request_for(self.user))
