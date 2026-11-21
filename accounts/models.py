from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models import Q
from django.utils.text import slugify
import uuid6

# Create your models here.
class University(models.Model):
    

    class Status(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    slug = models.SlugField(unique=True, help_text= "Publice URL segment")
    name = models.TextField(max_length=255)
    short_name = models.TextField(max_length=100, blank=True, null=True)
    country_code = models.CharField(max_length=2, help_text="ISO 3166-1")
    timezone = models.TextField(max_length=10, blank=False, help_text="IANA")
    default_currency = models.CharField(max_length=3, help_text="One per tenant")
    status = models.TextField(choices=Status.choices, default=Status.ONBOARDING)
    settings = models.JSONField(default=dict, blank=True, null=True, help_text="Branding, feature flags")
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
        db_table = "university"

    def __str__(self):
        return self.name

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DELETED = "deleted", "Deleted"

    #Remove AbstractUser's username field and use email instead
    username = None

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    email = models.EmailField(unique=True, blank=False, null=False)
    full_name = models.TextField(max_length=255, blank=True, null=False)
    university = models.ForeignKey(University, null=True, blank=True, on_delete=models.PROTECT, related_name="users")
    status = models.TextField(choices=Status.choices, default=Status.PENDING)
    platform_staff = models.BooleanField(default=False, help_text="Platform staff can access all universities")
    email_verified_at = models.DateTimeField(blank=True, null=True)
    auth_version = models.IntegerField(default=1, help_text="Incremented to kill sessions and force re-login")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "accounts_user"
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~Q(status="active") | Q(platform_staff=True) | Q(university__isnull=False)
                ),
                name="active_user_has_university",
            ),
        ]

    def __str__(self):
        return self.email


class EmailDomain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name="email_domains")
    domain = models.TextField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_domain"


class EmailToken:
    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify Email"
        RESET_PASSWORD = "reset_password", "Reset Password"
        CHANGE_EMAIL = "change_email", "Change Email"

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_tokens")
    university = models.ForeignKey(University, on_delete=models.CASCADE)
    purpose = models.TextField(choices=Purpose.choices)
    token_hash= models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(blank=True, null=True)
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_token"


class RoleAssignment(models.Model):
    class Role(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", "Platform Administrator",
        UNIVERSITY_ADMIN = "university_admin", "University Administrator",
        UNIVERSITY_MODERATOR = "university_moderator", "University Moderator",
    

    id = models.UUIDField(primary_key=True, default=uuid6.uuid7, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.TextField(choices=Role.choices, max_length=50)
    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name="role_assignments")
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="granted_role_assignments")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="revoked_role_assignments")

    class Meta:
        db_table = "role_assignment"
        unique_together = ("user", "role", "university", "revoked_at")