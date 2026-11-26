"""
accounts/models.py
==================
Core identity models for CampusHub.

Responsibility
--------------
This module owns every row that describes *who* a person is and what authority
they hold inside the platform:

  User              — the central identity record; one row = one person.
  EmailToken        — single-use, time-limited verification tokens.
  RoleAssignment    — explicit grants of elevated privilege (platform admin,
                      university admin, university moderator).

Design decisions
----------------
* AUTH_USER_MODEL = "accounts.User".  Django's built-in auth machinery
  (session authentication, password hashing, admin login) all resolve to this
  model.  Do NOT replace it with a proxy or a second custom user.

* The *authoritative* signal for platform-admin authority is an active
  RoleAssignment(role=PLATFORM_ADMIN, university=NULL).  The boolean field
  `platform_staff` is a *synchronized projection* only — it is kept in sync by
  RoleAssignment.save() / .delete() and must never be set manually.  Django
  superusers are a separate, infrastructure-level override that bypass all
  RLS policies.

* `auth_version` is an integer that is baked into Django's session-auth hash.
  Incrementing it invalidates every existing session for that user without
  needing to touch the session table.  It is bumped automatically by User.save()
  whenever password, status, is_active, or deleted_at changes, and by
  RoleAssignment._sync_platform_staff() whenever a platform-admin grant is
  created or revoked.

* University FKs point to "universities.University" (a cross-app reference).
  The accounts app never owns or defines the University model.

Table names
-----------
  accounts_user             — set explicitly on User.Meta
  accounts_email_token      — set explicitly on EmailToken.Meta
  accounts_role_assignment  — set explicitly on RoleAssignment.Meta
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models, router, transaction
from django.db.models import F, Q
from django.utils.crypto import salted_hmac
import uuid6


class UserManager(BaseUserManager):
    """
    Custom manager for the User model.

    Overrides create_user and create_superuser to:
    - enforce email (not username) as the login identifier,
    - normalize the email to lowercase,
    - guarantee that every superuser gets an active global PLATFORM_ADMIN
      RoleAssignment so that platform-admin checks work via the grant rather
      than the boolean field alone.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and return a regular (non-staff) user.

        Raises
        ------
        ValueError
            If email is empty or absent.
        """
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create a Django superuser and guarantee a global PLATFORM_ADMIN grant.

        The superuser must:
        - have is_superuser=True, is_staff=True, status='active'
        - have platform_staff=True
        - NOT be assigned to any university (platform staff are tenant-free)

        After saving the user, a RoleAssignment(PLATFORM_ADMIN, university=NULL)
        is created via get_or_create so that is_platform_admin() returns True
        through the grant-based check as well as the superuser shortcut.

        Raises
        ------
        ValueError
            If any of the above conditions are violated.
        """
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("status", "active")
        extra_fields.setdefault("platform_staff", True)
        if extra_fields["is_superuser"] is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        if extra_fields["is_staff"] is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields["status"] != "active":
            raise ValueError("A superuser must have status='active'.")
        if not extra_fields["platform_staff"]:
            raise ValueError("A superuser must have platform_staff=True.")
        if extra_fields.get("university") is not None or extra_fields.get("university_id") is not None:
            raise ValueError("A platform superuser cannot be assigned to a university.")

        user = self.create_user(email, password, **extra_fields)
        RoleAssignment.objects.get_or_create(
            user=user,
            role=RoleAssignment.Role.PLATFORM_ADMIN,
            university=None,
            revoked_at=None,
        )
        return user


class User(AbstractUser):
    """
    CampusHub's central identity record.

    Extends Django's AbstractUser with:

    - Email-based login (username field removed).
    - A `university` FK (nullable for platform staff, non-null for all others
      once their account is active — enforced by the check constraint below).
    - A `status` field that drives authentication: only 'active' users may
      log in (enforced by AccountStatusBackend).
    - `platform_staff` — a *projection* of the user's active global
      RoleAssignment; do not set this directly.
    - `auth_version` — incremented on security-sensitive field changes so that
      Django's session authentication hash changes and existing sessions are
      invalidated automatically.

    Session-invalidation contract
    ------------------------------
    Django computes a session auth hash by calling user.get_session_auth_hash().
    This implementation overrides _get_session_auth_hash() to include
    `auth_version`, so bumping the integer has the same effect as changing the
    password: every session that was issued with an older version is rejected on
    the next request.

    Fields that trigger an auth_version bump (via save()):
      - password
      - status
      - is_active
      - deleted_at

    Fields that trigger an auth_version bump (via RoleAssignment lifecycle):
      - gaining or losing an active global PLATFORM_ADMIN grant

    Check constraint
    ----------------
    `active_user_has_university` enforces:
        status != 'active'  OR  platform_staff = TRUE  OR  university IS NOT NULL

    This means an active, non-platform user MUST have a university.
    Platform staff (university IS NULL) are only allowed when platform_staff=TRUE.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DELETED = "deleted", "Deleted"

    # Remove AbstractUser's username field and use email instead
    username = None

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    email = models.EmailField(unique=True, blank=False, null=False)
    full_name = models.TextField(max_length=255, blank=True, null=False)
    university = models.ForeignKey(
        "universities.University",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
        help_text="The tenant this user belongs to. NULL only for platform staff.",
    )
    status = models.TextField(choices=Status.choices, default=Status.PENDING)
    platform_staff = models.BooleanField(
        default=False,
        help_text=(
            "Projection of the user's active global PLATFORM_ADMIN RoleAssignment. "
            "Do not set this field directly — it is managed by RoleAssignment.save()."
        ),
    )
    email_verified_at = models.DateTimeField(blank=True, null=True)
    auth_version = models.IntegerField(
        default=1,
        help_text=(
            "Incremented whenever a security-sensitive field changes. "
            "Including it in the session-auth hash invalidates all existing sessions. It forces a re-login"
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "accounts_user"

    def __str__(self):
        return self.email

    def has_platform_admin_role(self, using=None):
        """
        Return True if this user has an *active global* PLATFORM_ADMIN grant.

        Parameters
        ----------
        using : str or None
            Database alias for the query. Pass "ops" from platform-scoped
            views and middleware; pass None to use the default connection.

        Note: this checks the RoleAssignment table, not the platform_staff
        boolean.  It is the authoritative check for API-level platform authority.
        """
        assignments = self.role_assignments
        if using is not None:
            assignments = assignments.using(using)
        return assignments.filter(
            role=RoleAssignment.Role.PLATFORM_ADMIN,
            university__isnull=True,
            revoked_at__isnull=True,
        ).exists()

    def is_platform_admin(self, using=None):
        """
        Return True if this user may act as a platform administrator.

        A user is a platform admin if:
        - They are a Django superuser (infrastructure override), OR
        - They have platform_staff=True AND an active global PLATFORM_ADMIN
          RoleAssignment.

        The two-condition check on the non-superuser path ensures that the
        boolean projection and the grant are both consistent.  If they diverge
        (e.g. a stale backfill), the user is NOT considered a platform admin.

        Parameters
        ----------
        using : str or None
            Database alias forwarded to has_platform_admin_role().
        """
        return self.is_superuser or (
            self.platform_staff and self.has_platform_admin_role(using=using)
        )

    def _get_session_auth_hash(self, secret=None):
        """
        Override Django's session-auth hash to include auth_version.

        Django calls this method to validate that a session cookie still
        matches the current user state.  By including auth_version in the
        HMAC key string, any increment to that field (triggered by password
        changes, status changes, or platform-grant changes) automatically
        invalidates all previously issued sessions without requiring a session-
        table sweep.
        """
        return salted_hmac(
            "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash",
            f"{self.password}:{self.auth_version}",
            secret=secret,
            algorithm="sha256",
        ).hexdigest()

    def save(self, *args, **kwargs):
        """
        Save the user, bumping auth_version when security-sensitive fields change.

        Tracked fields: password, status, is_active, deleted_at.

        The method loads the previous values inside the same atomic transaction
        (using SELECT FOR UPDATE to avoid a lost-update race) and increments
        auth_version only when at least one tracked field has actually changed.
        This ensures that routine updates (e.g. updating full_name) do not
        invalidate existing sessions unnecessarily.

        New records (self._state.adding is True) skip the comparison entirely.
        """
        if self._state.adding:
            return super().save(*args, **kwargs)

        using = (
            kwargs.get("using")
            or self._state.db
            or router.db_for_write(type(self), instance=self)
        )
        kwargs.setdefault("using", using)
        update_fields = kwargs.get("update_fields")
        tracked_fields = {"password", "status", "is_active", "deleted_at"}
        if update_fields is not None:
            tracked_fields.intersection_update(update_fields)

        with transaction.atomic(using=using):
            previous = (
                type(self).objects.using(using)
                .select_for_update()
                .filter(pk=self.pk)
                .values(
                    "password",
                    "status",
                    "is_active",
                    "deleted_at",
                    "auth_version",
                )
                .first()
            )
            if previous:
                password_changed = (
                    "password" in tracked_fields
                    and previous["password"] != self.password
                    and getattr(self, "_password", None) is not None
                )
                account_state_changed = any(
                    field in tracked_fields and previous[field] != getattr(self, field)
                    for field in ("status", "is_active", "deleted_at")
                )
                if password_changed or account_state_changed:
                    self.auth_version = previous["auth_version"] + 1
                    if update_fields is not None:
                        kwargs["update_fields"] = set(update_fields) | {"auth_version"}

            return super().save(*args, **kwargs)


class EmailToken(models.Model):
    """
    Single-use, time-limited email verification token.

    Tokens are never stored in plain text: only a sha-256 hash of the raw
    token is persisted in `token_hash`.  The raw token is generated by the
    service layer, handed to the email provider, and immediately discarded.

    A token is considered consumed once `consumed_at` is set.  Attempts to
    use it afterwards are rejected regardless of expiry.

    Fields
    ------
    purpose   — what the token authorises (email verification, password reset,
                or email change).
    university — the tenant the token is scoped to (nullable for platform-level
                flows such as platform-admin password reset).
    attempts  — the number of failed verification attempts; the service layer
                uses this to rate-limit brute-force guessing.
    """

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify Email"
        RESET_PASSWORD = "reset_password", "Reset Password"
        CHANGE_EMAIL = "change_email", "Change Email"

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_tokens")
    university = models.ForeignKey(
        "universities.University",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="email_tokens",
        help_text="The tenant this token belongs to. NULL for platform-level flows.",
    )
    purpose = models.TextField(choices=Purpose.choices)
    token_hash = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(blank=True, null=True)
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_email_token"


class RoleAssignment(models.Model):
    """
    An explicit grant of elevated privilege to a user.

    Authority model
    ---------------
    Three role levels exist:

    PLATFORM_ADMIN
        Global authority; university MUST be NULL.  An active grant of this
        role makes the user a platform administrator; `User.platform_staff` is
        kept in sync as a projection.

    UNIVERSITY_ADMIN
        University-scoped authority; university MUST be non-NULL and MUST equal
        the user's own university_id.  University admins can manage their own
        university's data.

    UNIVERSITY_MODERATOR
        Same scoping rules as UNIVERSITY_ADMIN but with fewer privileges
        (content moderation only, not university settings).

    Active vs revoked
    -----------------
    A grant is *active* when revoked_at is NULL.  Setting revoked_at to a
    non-null timestamp revokes it.  Revoked grants are never deleted so the
    full history is preserved for audit purposes.

    Unique active grant constraint
    ------------------------------
    Migration 0007 adds `unique_active_rolegrant`:

        UNIQUE (user, role, university) WHERE revoked_at IS NULL

    This prevents duplicate active grants for the same (user, role, scope)
    combination.  When a grant is revoked (revoked_at set), the unique index
    no longer covers it, so a new active grant for the same combination can
    be created later.

    platform_staff projection
    -------------------------
    Every time a RoleAssignment row is saved or deleted, _sync_platform_staff()
    re-derives whether the affected user holds an active PLATFORM_ADMIN grant
    and updates User.platform_staff + User.auth_version accordingly.  This
    keeps the boolean projection in sync without requiring callers to remember
    to update it manually.
    """

    class Role(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", "Platform Administrator"
        UNIVERSITY_ADMIN = "university_admin", "University Administrator"
        UNIVERSITY_MODERATOR = "university_moderator", "University Moderator"

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.TextField(choices=Role.choices, max_length=50)
    university = models.ForeignKey(
        "universities.University",
        on_delete=models.CASCADE,
        related_name="role_assignments",
        null=True,
        blank=True,
        help_text="NULL for PLATFORM_ADMIN; must equal user.university_id for all other roles.",
    )
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="granted_role_assignments",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="revoked_role_assignments",
    )

    class Meta:
        db_table = "accounts_role_assignment"
        # unique_together removed; replaced by the conditional unique constraint
        # `unique_active_rolegrant` added in migration 0007:
        #   UNIQUE (user, role, university) WHERE revoked_at IS NULL

    def _sync_platform_staff(self, user_ids, using):
        """
        Re-derive and synchronize User.platform_staff for each given user.

        Called after every save() and delete() to ensure the boolean projection
        matches the actual grant state.  Also bumps auth_version so that any
        active session for an affected user is invalidated.

        Parameters
        ----------
        user_ids : iterable of UUID or None
            The user PKs to re-check.  None values are silently skipped
            (they arise when a grant has no previous user, e.g. on creation).
        using : str
            Database alias to use for all queries inside this method.
        """
        for user_id in sorted({value for value in user_ids if value is not None}, key=str):
            user = (
                User.objects.using(using)
                .select_for_update()
                .filter(pk=user_id)
                .only("platform_staff")
                .first()
            )
            if user is None:
                continue
            has_platform_grant = type(self).objects.using(using).filter(
                user_id=user_id,
                role=self.Role.PLATFORM_ADMIN,
                university__isnull=True,
                revoked_at__isnull=True,
            ).exists()
            if user.platform_staff != has_platform_grant:
                User.objects.using(using).filter(pk=user_id).update(
                    platform_staff=has_platform_grant,
                    auth_version=F("auth_version") + 1,
                )

    def save(self, *args, **kwargs):
        """
        Save this grant and synchronize the platform_staff projection.

        Wraps the super().save() call in an atomic transaction so that the
        grant row and the platform_staff update are always committed together.
        Records the previous user_id before saving so that _sync_platform_staff
        can update both the old owner (if the user changes) and the new one.
        """
        using = (
            kwargs.get("using")
            or self._state.db
            or router.db_for_write(type(self), instance=self)
        )
        kwargs.setdefault("using", using)
        with transaction.atomic(using=using):
            previous_user_id = None
            if not self._state.adding:
                previous_user_id = (
                    type(self).objects.using(using)
                    .filter(pk=self.pk)
                    .values_list("user_id", flat=True)
                    .first()
                )
            result = super().save(*args, **kwargs)
            self._sync_platform_staff((previous_user_id, self.user_id), using)
            return result

    def delete(self, *args, **kwargs):
        """
        Delete this grant and synchronize the platform_staff projection.

        Uses the same atomic + sync pattern as save() to ensure the grant row
        is removed and the boolean projection is updated in a single transaction.
        """
        using = (
            kwargs.get("using")
            or self._state.db
            or router.db_for_write(type(self), instance=self)
        )
        kwargs.setdefault("using", using)
        user_id = self.user_id
        with transaction.atomic(using=using):
            result = super().delete(*args, **kwargs)
            self._sync_platform_staff((user_id,), using)
            return result