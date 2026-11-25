from django.db import models
from .tenancy import get_current_university_id, TenantNotSet

class TenantScopedManager(models.Manager):

    def get_queryset(self):
        university_id = get_current_university_id()
        if university_id is None:
            raise TenantNotSet("No tenant set; refusing to return unscoped rows.")
        return super().get_queryset().filter(university_id=university_id)