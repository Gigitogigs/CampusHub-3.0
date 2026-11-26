from django.db import migrations, models
from django.db.models import Q

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_backfill_platform_admin_grants'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='roleassignment',
            constraint=models.UniqueConstraint(
                fields=['user', 'role', 'university'],
                condition=Q(revoked_at__isnull=True),
                name='unique_active_rolegrant',
            ),
        ),
    ]
