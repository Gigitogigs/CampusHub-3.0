#Owns Transactions, invariants, orderinng of side effects.
import hashlib

import secrets
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from universities.models import EmailDomain, University
from .models import EmailToken, User


class UnkownEmailDomain(ValueError):
    """Raised when no active university claims the user's email domain """
    
    @transaction.atomic()
    def register_user(*, email:str, full_name: str, password: str) -> tuple[User, str]:
        normalized_email = User.objects.normalize_email(email).strip().lower()
        domain_part = normalized_email.rsplit("@", 1)[-1]

        email_domain = (
            EmailDomain.objects.select_related("university").filter(
                domain__iexact=domain_part,
                is_active=True,
                university__status=University.Status.ACTIVE,
            ).first()
        )
        if email_domain is None:
            raise UnkownEmailDomain("This email domain is not registered with an active university.")

        user = User.objects.create_user(
            email=normalized_email,
            password=password,
            full_name=full_name,
            university=email_domain.university,
            status=User.Status.PENDING,
        )

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        EmailToken.objects.create(
            user=user,
            university=user.university,
            purpose=EmailToken.Purpose.VERIFY_EMAIL,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        return user, raw_token 


class EmailVerificationError(ValueError):
    """Raised when email verification fails due to invalid or expired token."""

    #wrap in tenant_scope(user.university_id) since RLS is on for accounts_user table.
    @transaction.atomic()
    def verify_email_token(raw_token: str) -> User:
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token = (EmailToken.objects.select_for_update().filter(token_hash=digest, purpose=EmailToken.Purpose.VERIFY_EMAIL).first())
        now = timezone.now()

        if token is None:
            raise EmailVerificationError("The provided email verification token is invalid.")
        if token.consumed_at is not None:
            raise EmailVerificationError("The provided email verification token has been used.")
        if token.expires_at < now:
            raise EmailVerificationError("The provided email verification token has expired.")

        user = User.objects.select_for_update().get(pk=token.user_id)
        if user.status == User.Status.ACTIVE:
            token.consumed_at = now; token.save(update_fields=["consumed_at"])
            return user
        if user.status != User.Status.PENDING:
            raise EmailVerificationError("User status not pending")
        if user.university is None:
            raise EmailVerificationError("User has no university")

        
        token.consumed_at = now; token.save(update_fields=["consumed_at"])
        user.status = User.Status.ACTIVE
        user.email_verified_at = now

        if user.university != token.university:
            raise EmailVerificationError("Token university does not match user university")
        else:
            user.save(update_fields=["status", "email_verified_at"])