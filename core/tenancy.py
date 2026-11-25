import contextvars
from contextlib import contextmanager

from django.db import connection, transaction
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

_current_university_id = contextvars.ContextVar("current_university_id", default=None)


class TenantNotSet(Exception):
    """Tenant scoped data was read while no university was set."""


def get_current_university_id():
    return _current_university_id.get()


@contextmanager
def tenant_scope(university_id):
    """Run a block as one university: Python-side value + database-side SET LOCAL.
    For top-level use (middleware, workers, registration) not nested inside another scope."""
    token = _current_university_id.set(university_id)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.university_id', %s, true)",
                    [str(university_id)],
                )
            yield
    finally:
        _current_university_id.reset(token)


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        #anonymous users and platform staff have no university scoping; tenant is not set
        if user is None or not user.is_active or user.university_id is None:
            return self.get_response(request)

        with tenant_scope(user.university_id):
            return self.get_response(request)


    @staticmethod
    def _get_user(request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return user

        try:
            result = TokenAuthentication().authenticate(request)
        except AuthenticationFailed:
            return None
        return result[0] if result else None