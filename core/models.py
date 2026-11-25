from django.db import models
from .managers import TenantScopedManager

# Create your models here.
class TenantOwnedModel(models.Model): #Abstract; creates no table
    university = models.ForeignKey("universities.University", on_delete=models.PROTECT)

    objects = TenantScopedManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True