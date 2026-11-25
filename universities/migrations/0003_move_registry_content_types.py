from django.conf import settings
from django.db import migrations


def _copy_permission_grants(through, owner_field, permission_field, old_permission_id, new_permission_id):
    owner_id_field = f"{owner_field}_id"
    permission_id_field = f"{permission_field}_id"
    owner_ids = through.objects.filter(
        **{permission_id_field: old_permission_id}
    ).values_list(owner_id_field, flat=True)
    for owner_id in owner_ids:
        through.objects.get_or_create(
            **{
                owner_id_field: owner_id,
                permission_id_field: new_permission_id,
            }
        )


def move_registry_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    LogEntry = apps.get_model("admin", "LogEntry")

    group_permissions = Group._meta.get_field("permissions")
    user_permissions = User._meta.get_field("user_permissions")
    grant_relations = (
        (
            group_permissions.remote_field.through,
            group_permissions.m2m_field_name(),
            group_permissions.m2m_reverse_field_name(),
        ),
        (
            user_permissions.remote_field.through,
            user_permissions.m2m_field_name(),
            user_permissions.m2m_reverse_field_name(),
        ),
    )

    for model_name in ("university", "emaildomain"):
        old_type = ContentType.objects.filter(
            app_label="accounts",
            model=model_name,
        ).first()
        if old_type is None:
            continue

        new_type = ContentType.objects.filter(
            app_label="universities",
            model=model_name,
        ).first()
        if new_type is None:
            old_type.app_label = "universities"
            old_type.save(update_fields=["app_label"])
            continue

        for old_permission in Permission.objects.filter(content_type=old_type):
            new_permission = Permission.objects.filter(
                content_type=new_type,
                codename=old_permission.codename,
            ).first()
            if new_permission is None:
                old_permission.content_type = new_type
                old_permission.save(update_fields=["content_type"])
                continue

            for through, owner_field, permission_field in grant_relations:
                _copy_permission_grants(
                    through,
                    owner_field,
                    permission_field,
                    old_permission.pk,
                    new_permission.pk,
                )
            old_permission.delete()

        LogEntry.objects.filter(content_type=old_type).update(content_type=new_type)
        old_type.delete()


def restore_registry_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model_name in ("university", "emaildomain"):
        content_type = ContentType.objects.filter(
            app_label="universities",
            model=model_name,
        ).first()
        if content_type is not None:
            content_type.app_label = "accounts"
            content_type.save(update_fields=["app_label"])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_rename_identity_tables'),
        ('admin', '0003_logentry_add_action_flag_choices'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('universities', '0002_rename_registry_tables'),
    ]

    operations = [
        migrations.RunPython(
            move_registry_content_types,
            restore_registry_content_types,
        ),
    ]
