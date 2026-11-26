"""
core/tenancy.py
===============
Tenant-scoping infrastructure for CampusHub.

What is a "tenant"?
-------------------
CampusHub is a multi-tenant system where each university is an isolated tenant.
Every piece of user-generated data (posts, orders, clubs, etc.) belongs to
exactly one university.  The goal of this module is to make it *impossible* for
a request that is meant to serve University A to accidentally read or write data
belonging to University B.

How it works — two layers
--------------------------
1. Python-side ContextVar (`_current_university_id`)
   A ContextVar is like a thread-local, but it works correctly with Django's
   async views and with Python's contextvars module.  Setting it stores the
   active university UUID for the duration of the current request.

2. Database-side `SET LOCAL app.university_id = '...'`
   This sets a PostgreSQL session-local variable that RLS (Row-Level Security)
   policies will read to decide which rows a query may see.  `SET LOCAL` means
   the value is automatically cleared at the end of the current transaction,
   so there is no risk of it leaking into the next request.

Together, the two layers mean:
  - Application code can call get_current_university_id() to find the active
    tenant without touching the database.
  - PostgreSQL's RLS policies enforce the same boundary at the database level,
    even if application code has a bug that forgets to filter.

TenantMiddleware
----------------
This middleware runs after Django's AuthenticationMiddleware (which sets
request.user) and before the view.  It:
  1. Allows anonymous requests through without setting a tenant (for login,
     public endpoints, etc.).
  2. Rejects authenticated requests from inactive/suspended/deleted accounts
     with PermissionDenied.
  3. Identifies platform admins and routes them to the `ops` DB alias without
     entering a university scope.
  4. Enters tenant_scope(university_id) for all other authenticated requests
     and passes the request on to the view.

Usage in service code
---------------------
    from core.tenancy import tenant_scope, get_current_university_id

    # In a worker or management command:
    with tenant_scope(university.pk):
        # All ORM queries inside this block are scoped to `university`.
        orders = Order.objects.all()

    # In a view or selector (scope is already set by middleware):
    university_id = get_current_university_id()  # returns UUID or None
"""

import contextvars
from contextlib import contextmanager

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction

# Module-level ContextVar.  Stores the UUID of the university that is active
# for the current request/task.  Default is None (no tenant set).
_current_university_id = contextvars.ContextVar("current_university_id", default=None)


class TenantNotSet(Exception):
    """
    Raised when tenant-scoped data is accessed while no university is set.

    TenantScopedManager raises this in get_queryset() if the ContextVar is
    None.  This is intentional: "fail closed" is safer than returning all rows.
    """


def get_current_university_id():
    """
    Return the UUID of the currently active tenant university, or None.

    Safe to call from anywhere (models, selectors, services, middleware).
    Returns None for anonymous requests and for platform-admin requests that
    are intentionally unscoped.
    """
    return _current_university_id.get()


@contextmanager
def tenant_scope(university_id):
    """
    Context manager: execute a block scoped to a single university.

    Sets both the Python-side ContextVar and the PostgreSQL session variable
    `app.university_id` (used by future RLS policies).  The PostgreSQL variable
    is set inside a transaction using `SET LOCAL`, which means it is
    automatically cleared when the transaction ends.

    Parameters
    ----------
    university_id : UUID
        The PK of the university to scope to.

    Usage
    -----
    For top-level use only (middleware, background workers, management
    commands).  Do NOT nest tenant_scope() inside another tenant_scope() —
    the inner call would silently override the outer scope without warning.

    Example::

        with tenant_scope(university.pk):
            # All TenantScopedManager queries here see only university's rows.
            clubs = Club.objects.all()
    """
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
        # Always reset the ContextVar, even if the block raised an exception.
        # This prevents the value from leaking into code that runs after the
        # context manager exits in the same async frame.
        _current_university_id.reset(token)


class TenantMiddleware:
    """
    Django middleware that establishes the tenant scope for every request.

    Position in MIDDLEWARE stack (config/settings.py)
    --------------------------------------------------
    Must come AFTER AuthenticationMiddleware (which sets request.user) and
    BEFORE any view that accesses tenant-scoped data.  Current order:

        SecurityMiddleware
        CorsMiddleware
        SessionMiddleware
        CommonMiddleware
        CsrfViewMiddleware
        AuthenticationMiddleware   ← sets request.user
        TenantMiddleware           ← this class; uses request.user
        MessageMiddleware
        XFrameOptionsMiddleware

    Request lifecycle
    -----------------
    1. Anonymous request → pass through without setting a tenant.
       Public endpoints (login, university public detail, etc.) need this.

    2. Authenticated but inactive / suspended / deleted → PermissionDenied.
       The view never runs; the user gets a 403.

    3. Platform admin (is_platform_admin() returns True) → set
       request.tenant_mode = "platform" and pass through WITHOUT entering a
       university scope.  Platform views use the ops DB alias explicitly.

    4. University-scoped user → enter tenant_scope(user.university_id), set
       request.university_id and request.tenant_mode = "university", then run
       the view inside that scope.  The scope is cleaned up in the `finally`
       block of tenant_scope() even if the view raises an exception.

    5. Authenticated user with no university and no platform grant → the
       `university_id is None` guard raises PermissionDenied.
    """

    def __init__(self, get_response):
        """Standard Django middleware __init__; store the next layer."""
        self.get_response = get_response

    def __call__(self, request):
        """
        Process the request, establish tenant scope, then call the view.

        Sets request.university_id (UUID or None) and request.tenant_mode
        ("platform", "university", or None) so downstream views and permission
        classes can inspect the current scope without calling
        get_current_university_id() themselves.
        """
        user = request.user
        request.university_id = None
        request.tenant_mode = None

        # 1. Anonymous → no tenant required.
        if not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        # 2. Inactive / suspended / deleted → reject before the view runs.
        if (
            not user.is_active
            or getattr(user, "status", None) != "active"
            or getattr(user, "deleted_at", None) is not None
        ):
            raise PermissionDenied("This account is inactive.")

        # 3. Platform admin → unscoped, routed via ops alias.
        using = "ops" if "ops" in settings.DATABASES else None
        if user.is_platform_admin(using=using):
            request.tenant_mode = "platform"
            return self.get_response(request)

        # 4. University-scoped user.
        university_id = user.university_id
        if university_id is None:
            # 5. Active, non-platform user without a university → reject.
            raise PermissionDenied("No university is assigned to this account.")

        request.university_id = university_id
        request.tenant_mode = "university"

        with tenant_scope(university_id):
            return self.get_response(request)
