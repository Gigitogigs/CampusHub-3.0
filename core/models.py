"""
core/models.py
==============
Abstract base models shared across all domain apps.

Why abstract models in core?
----------------------------
Every tenant-owning model (Club, Event, Business, Listing, etc.) needs:
  1. A `university` FK — the tenant boundary.
  2. A fail-closed default manager that restricts queries to the active tenant.
  3. An escape-hatch manager (`all_objects`) for migrations and admin commands.

Putting these on an abstract base class means that adding a new domain model is
one line:

    class Club(TenantOwnedModel):
        ...  # just the club-specific fields

and it automatically gets tenant isolation for free.

Dependency rule
---------------
core must NOT import from domain apps (accounts, universities, clubs, etc.).
The university FK is expressed as a lazy string reference ("universities.University")
so there is no import-time dependency on the universities module.
"""

from django.db import models
from .managers import TenantScopedManager


class TenantOwnedModel(models.Model):
    """
    Abstract base class for every model that belongs to a single university.

    Fields
    ------
    university : ForeignKey
        The tenant this row belongs to.  PROTECT on delete means you cannot
        delete a university that still has associated domain rows — you must
        archive or transfer the data first.

    Managers
    --------
    objects (TenantScopedManager)
        The default manager.  get_queryset() raises TenantNotSet if no
        university context is active, and otherwise automatically filters to
        the current tenant.  Use this for all request-path code.

    all_objects (models.Manager)
        The plain, unfiltered manager.  Use ONLY in migrations, management
        commands, and admin-site overrides.  NEVER use this in views,
        selectors, or services — the import-linter rule enforces this.

    Usage
    -----
    Subclass this model for any domain entity that must be scoped to a
    university::

        class Club(TenantOwnedModel):
            name = models.TextField(max_length=255)
            ...

        # In a view (tenant context already set by TenantMiddleware):
        clubs = Club.objects.filter(status="active")  # auto-scoped ✔

        # In a migration or admin command (unscoped):
        all_clubs = Club.all_objects.all()           # explicit escape hatch ✔
    """

    university = models.ForeignKey(
        "universities.University",
        on_delete=models.PROTECT,
        help_text="The tenant (university) this row belongs to.",
    )

    objects = TenantScopedManager()
    all_objects = models.Manager()

    class Meta:
        # abstract=True means Django never creates a database table for this
        # class.  Subclasses each get their own table with the university FK
        # already included.
        abstract = True
