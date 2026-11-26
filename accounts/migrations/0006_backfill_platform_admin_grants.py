from django.db import migrations, models
import django.db.models.deletion


def backfill_platform_admin_grants(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    RoleAssignment = apps.get_model("accounts", "RoleAssignment")
    # Use provided schema_editor if available, otherwise default to the 'default' database
    if schema_editor is not None:
        database = schema_editor.connection.alias
    else:
        from django.db import connections
        database = connections['default'].alias

    platform_users = User.objects.using(database).filter(platform_staff=True)
    existing_global_admin_ids = RoleAssignment.objects.using(database).filter(
        role="platform_admin",
        university__isnull=True,
        revoked_at__isnull=True,
    ).values("user_id")
    if User.objects.using(database).filter(
        models.Q(pk__in=platform_users.values("pk"))
        | models.Q(pk__in=existing_global_admin_ids),
        university__isnull=False,
    ).exists():
        raise RuntimeError(
            "Cannot backfill platform administrators assigned to a university; "
            "resolve those accounts before applying this migration."
        )

    for user_id in platform_users.values_list("pk", flat=True).iterator():
        active_grant = RoleAssignment.objects.using(database).filter(
            user_id=user_id,
            role="platform_admin",
            university__isnull=True,
            revoked_at__isnull=True,
        )
        if not active_grant.exists():
            RoleAssignment.objects.using(database).create(
                user_id=user_id,
                role="platform_admin",
                university_id=None,
            )

    for user_id, platform_staff in User.objects.using(database).values_list(
        "pk",
        "platform_staff",
    ).iterator():
        has_platform_grant = RoleAssignment.objects.using(database).filter(
            user_id=user_id,
            role="platform_admin",
            university__isnull=True,
            revoked_at__isnull=True,
        ).exists()
        if platform_staff != has_platform_grant:
            User.objects.using(database).filter(pk=user_id).update(
                platform_staff=has_platform_grant
            )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_rename_identity_tables"),
        ("universities", "0003_move_registry_content_types"),
    ]

    operations = [
        migrations.AlterField(
            model_name="roleassignment",
            name="university",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="role_assignments",
                to="universities.university",
            ),
        ),
        migrations.RunPython(
            backfill_platform_admin_grants,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
