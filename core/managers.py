"""
core/managers.py
================
Custom Django ORM manager that enforces tenant isolation at the query level.

Why a custom manager?
---------------------
Django's default Manager.get_queryset() returns *all* rows in the table.  In a
multi-tenant system that is a footgun: a developer who forgets to filter by
university_id could accidentally expose data from every tenant.

TenantScopedManager makes the safe path the default path: calling `.objects.*`
on a model that uses this manager *automatically* restricts the queryset to the
active tenant.  Forgetting to filter is no longer dangerous — the manager does
it for you.

Fail-closed design
------------------
If no tenant is set (get_current_university_id() returns None) the manager
raises TenantNotSet rather than returning an empty queryset or all rows.
This is deliberate: an empty queryset would silently mask bugs (code would
"work" but show no data), while raising an exception surfaces the problem
immediately.

Escape hatch
------------
Every model that uses TenantScopedManager also exposes `all_objects`, a plain
Django Manager, for the rare cases where truly unscoped access is needed
(e.g. migration data operations, management commands, admin list views).
The import-linter rule `*/api/* → all_objects` is FORBIDDEN so that the
escape hatch never reaches the request path.
"""

from django.db import models
from .tenancy import get_current_university_id, TenantNotSet


class TenantScopedManager(models.Manager):
    """
    ORM manager that restricts queries to the currently active tenant.

    Attach this as the default `objects` manager on any model that has a
    `university_id` FK and should be isolated per tenant::

        class Club(TenantOwnedModel):   # TenantOwnedModel already does this
            ...

    get_queryset() raises TenantNotSet if called outside a tenant context so
    that missing tenant setup surfaces immediately as an error rather than
    silently returning an empty or unfiltered result.
    """

    def get_queryset(self):
        """
        Return a queryset filtered to the active university.

        Raises
        ------
        TenantNotSet
            If no university is active in the current context (i.e.
            get_current_university_id() returns None).  This prevents
            accidental cross-tenant data leaks when tenant setup is missing.
        """
        university_id = get_current_university_id()
        if university_id is None:
            raise TenantNotSet("No tenant set; refusing to return unscoped rows.")
        return super().get_queryset().filter(university_id=university_id)
