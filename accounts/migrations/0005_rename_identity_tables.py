from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_emailtoken_university_alter_user_university_and_more'),
        ('universities', '0002_rename_registry_tables'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='emailtoken',
            table='accounts_email_token',
        ),
        migrations.AlterModelTable(
            name='roleassignment',
            table='accounts_role_assignment',
        ),
    ]
