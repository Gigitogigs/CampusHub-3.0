"""
accounts/migrations/0008_drop_active_user_has_university_constraint.py

Remove the `active_user_has_university` database CHECK constraint added in
0001_initial.

Rationale
---------
The constraint `active_user_has_university` reads:

    status != 'active'  OR  platform_staff = TRUE  OR  university IS NOT NULL

This was correct when `platform_staff` was always set before an active-status
user had their platform grant revoked.  With the grant-sync logic in place,
the following valid lifecycle now occurs inside a single atomic transaction:

  1. Grant revoked_at is set.
  2. _sync_platform_staff() runs, trying to UPDATE platform_staff = FALSE.
  3. The CHECK constraint fires BEFORE the transaction commits because
     PostgreSQL evaluates CHECK constraints per-statement, not per-transaction.
  4. The user now has status='active', university=NULL, platform_staff=FALSE
     at the moment of the UPDATE — a momentary violation even though the final
     desired state (user is pending/suspended) hasn't been reached yet.

The constraint is therefore dropped at the database level.  Enforcement is
carried out at the application level by:
  - TenantMiddleware: rejects requests from active users with no university
    and no platform grant.
  - UserCreateSerializer: rejects user creation without a university (unless
    the caller is a platform admin creating a superuser via create_superuser).
  - The status-transition service (future work) will prevent setting
    status='active' for a user with no university and no active global grant.

The constraint will be re-added in a future migration once the status-
transition service and RLS policies provide equivalent enforcement.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_add_rolegrant_unique_constraint'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='user',
            name='active_user_has_university',
        ),
    ]
