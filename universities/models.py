"""
universities/models.py
======================
Registry models: University and EmailDomain.

Ownership
---------
These models are owned and administered by the `universities` app.  The
`accounts` app holds a FK *to* University but does not define it.  See
`docs/implementation plan.md` Phase 1 for the rationale.

Table names (explicitly set)
----------------------------
  universities_university   — University
  universities_email_domain — EmailDomain

RLS note
--------
Unlike the identity tables in `accounts`, these two tables are intentionally
NOT protected by Row-Level Security.  A new user's email must be resolved to
a university *before* any identity exists, so the lookup must be possible
without a tenant context.  See §1.7 of Diagrams-and-Django-Apps.md.
"""

import uuid6
from django.db import models
from django.utils.text import slugify


class University(models.Model):
    """
    A single university tenant.

    Every piece of user-generated data in CampusHub belongs to exactly one
    University.  The University row *is* the tenant boundary.

    Fields
    ------
    slug
        A URL-safe identifier used in public endpoints like
        `/api/v1/universities/public/<slug>/`.  Auto-generated from `name` on
        first save if not supplied.  Must be globally unique.

    country_code
        ISO 3166-1 alpha-2 code (e.g. "KE" for Kenya).  Used for locale-
        dependent formatting in the frontend.

    timezone
        IANA timezone string (e.g. "Africa/Nairobi").  Stored here so the
        frontend can render event times in the university's local wall clock.
        Note: the current max_length=10 is too short for many IANA strings
        (deferred fix, see §9.1 F11 in the implementation plan).

    default_currency
        ISO 4217 three-letter currency code (e.g. "KES").  One per tenant;
        all monetary amounts in this tenant's tables are in this currency.

    settings
        Arbitrary JSON for branding and feature flags.  Nullable (NULL == {}).
        Never exposed through the public serializer to prevent private config
        from leaking.

    Status lifecycle
    ----------------
    onboarding → active → suspended → archived
    A university is never deleted; archiving is the terminal state.

    Slug generation
    ---------------
    If slug is not provided on creation, generate_slug() derives one from
    `name` using Django's slugify() and appends a counter to avoid collisions.
    """

    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    slug = models.SlugField(unique=True, help_text="Public URL segment")
    name = models.TextField(max_length=255)
    short_name = models.TextField(max_length=100, blank=True, null=True)
    country_code = models.CharField(max_length=2, help_text="ISO 3166-1")
    timezone = models.TextField(max_length=10, blank=False, help_text="IANA")
    default_currency = models.CharField(max_length=3, help_text="One per tenant")
    status = models.TextField(choices=Status.choices, default=Status.ONBOARDING)
    settings = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Branding, feature flags — never expose via public API.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "universities_university"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate a slug from name if one is not already set."""
        if not self.slug:
            self.slug = self.generate_slug()
        super().save(*args, **kwargs)

    def generate_slug(self):
        """
        Return a unique slug derived from self.name.

        Applies Django's slugify() to get a base slug, then appends an
        incrementing counter until a unique value is found.  This is safe for
        creation; it is NOT safe to call on update (the slug is read-only after
        creation).
        """
        base_slug = slugify(self.name)
        slug = base_slug
        counter = 1
        while University.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug


class EmailDomain(models.Model):
    """
    An email domain that maps to a University.

    Used during registration: when a new user signs up with
    student@example.ac.ke, the system looks up the domain "example.ac.ke"
    in this table to find which University to assign them to.

    Invariants
    ----------
    - `domain` must be globally unique (enforced by unique=True).
    - `domain` should be normalised to lowercase before saving (the D2 diagram
      specifies this but current code does not enforce it — deferred, see §9.1
      F11).  The registration service must normalise before lookup.

    RLS
    ---
    This table is NOT RLS-protected (see module docstring).
    """

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name="email_domains",
        help_text="The university that owns this email domain.",
    )
    domain = models.TextField(
        max_length=255,
        unique=True,
        help_text="e.g. 'example.ac.ke' — must be globally unique and lowercase.",
    )
    is_active = models.BooleanField(default=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "universities_email_domain"

    def __str__(self):
        return self.domain
