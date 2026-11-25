from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_emailtoken_university_alter_user_university_and_more'),
        ('universities', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='university',
            table='universities_university',
        ),
        migrations.AlterModelTable(
            name='emaildomain',
            table='universities_email_domain',
        ),
    ]
