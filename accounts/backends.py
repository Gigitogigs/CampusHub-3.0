"""
accounts/backends.py
====================
Custom Django authentication backend for CampusHub.

Why we need a custom backend
----------------------------
Django's default ModelBackend allows any user whose `is_active` flag is True
to authenticate.  CampusHub adds a `status` field and a `deleted_at` soft-delete
timestamp that the default backend knows nothing about.

This backend extends ModelBackend with a stricter user_can_authenticate() check
so that:
  - Suspended users (status='suspended') cannot log in even if is_active=True.
  - Soft-deleted users (deleted_at is set) are blocked at the authentication
    boundary rather than further downstream.
  - Pending users (status='pending', e.g. waiting for email verification) are
    also blocked until their status transitions to 'active'.

Configuration
-------------
Registered in config/settings.py:
    AUTHENTICATION_BACKENDS = ["accounts.backends.AccountStatusBackend"]

The standard ModelBackend is NOT listed separately; this subclass inherits its
full implementation (password check, permission lookups, etc.) and only
overrides the user_can_authenticate gate.
"""

from django.contrib.auth.backends import ModelBackend


class AccountStatusBackend(ModelBackend):
    """
    Authentication backend that enforces CampusHub's User.status lifecycle.

    Inherits all standard authentication behaviour from ModelBackend (password
    hashing, permission checks, is_active gate) and adds a stricter guard on
    top:

    A user may authenticate if and only if:
      1. ModelBackend.user_can_authenticate() returns True (is_active=True), AND
      2. user.status == 'active', AND
      3. user.deleted_at is None (the account has not been soft-deleted).

    This is called by django.contrib.auth.authenticate() before the password
    is verified, so a suspended or deleted user never reaches the password-
    comparison step.
    """

    def user_can_authenticate(self, user):
        """
        Return True only for users who are active in every sense CampusHub requires.

        Called by Django's authenticate() after finding the User row but before
        verifying the password.  Returning False here causes authenticate() to
        return None, which translates to a 403 from DRF's SessionAuthentication.
        """
        return bool(
            super().user_can_authenticate(user)
            and user.status == user.Status.ACTIVE
            and user.deleted_at is None
        )
