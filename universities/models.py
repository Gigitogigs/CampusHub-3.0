import uuid6
from django.db import models
from django.utils.text import slugify


class University(models.Model):
    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    slug = models.SlugField(unique=True, help_text="Publice URL segment")
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
        help_text="Branding, feature flags",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_slug()
        super().save(*args, **kwargs)

    def generate_slug(self):
        base_slug = slugify(self.name)
        slug = base_slug
        counter = 1

        while University.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    class Meta:
        db_table = "universities_university"

    def __str__(self):
        return self.name


class EmailDomain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name="email_domains",
    )
    domain = models.TextField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "universities_email_domain"
