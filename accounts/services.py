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
                domain__isexact=domain_part,
                is_active=True,
                university_status=University.Status.ACTIVE,
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

    