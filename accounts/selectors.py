"""
accounts/selectors.py
=====================
Read-only query composition for the accounts app.

Selectors are thin functions that return a QuerySet.  They contain no business
logic, never open transactions, and never write data.  Views and services call
selectors to get the data they need; they never build raw querysets themselves.

Tenant-scoping rules
--------------------
Every selector in this module enforces one of two scoping modes:

  UNIVERSITY scope (normal authenticated users)
      Only rows belonging to the requesting user's own university are returned.
      This maps directly onto the RLS tenant policy that will be enabled in a
      later release.

  PLATFORM scope (global platform admins)
      Platform administrators can see users across all tenants.  To avoid
      accidentally running a cross-tenant query through the default database
      connection, platform selectors MUST use the `ops` database alias.  If
      the ops alias is not configured (e.g. in development or tests), queries
      will raise OperationalError rather than silently returning all users
      through the default connection.

Fail-closed design
------------------
If neither condition is met (the actor has no university and is not a platform
admin) the selector returns QuerySet.none().  This means a misconfigured user
gets zero rows, never all rows.
"""

from .models import User


def users_visible_to(actor):
    """
    Return an undeleted User queryset scoped to what `actor` is allowed to see.

    Parameters
    ----------
    actor : User
        The currently authenticated user making the request.

    Returns
    -------
    QuerySet[User]
        - For platform admins: all undeleted users, routed through the `ops`
          database alias.
        - For university-scoped users: undeleted users belonging to the same
          university as the actor.
        - For anyone else (no university, not a platform admin): an empty
          queryset (fail-closed).

    Notes
    -----
    The `ops` database alias is defined in config/settings.py via the
    OPS_DATABASE_URL environment variable.  It is optional in development but
    required before platform-admin views are exposed in production.

    The queryset is NOT yet filtered by RLS (Row-Level Security is a future
    release gate); the selector itself provides the equivalent safeguard.
    """
    qs = User.objects.filter(deleted_at__isnull=True)

    # Platform-admin path: must have both the boolean projection AND an active
    # global grant.  If either is missing we fall through and return none().
    if actor.is_superuser or actor.platform_staff:
        if not actor.is_platform_admin(using="ops"):
            return qs.none()
        return qs.using("ops")

    # University-scoped path: actor must have an assigned university.
    if actor.university_id is None:
        return qs.none()

    return qs.filter(university_id=actor.university_id)
