import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Lehrer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("Nachname", models.CharField(max_length=255, verbose_name="Nachname")),
                ("Vorname", models.CharField(max_length=255, verbose_name="Vorname")),
                ("Schule_Email", models.EmailField(max_length=254, unique=True)),
                ("Private_Email", models.EmailField(blank=True, default="", max_length=254)),
                ("KurzName", models.CharField(max_length=20, unique=True)),
                ("Telefonnummer", models.CharField(blank=True, max_length=25, null=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="lehrer_user", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Lehrer",
                "verbose_name_plural": "Lehrer",
                "db_table": "Lehrer",
                "ordering": ["user_id"],
            },
        ),
    ]
