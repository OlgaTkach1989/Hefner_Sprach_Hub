from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("online", "0006_online_payment_event_and_order_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnlineMagicLinkToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cohort",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="magic_link_tokens",
                        to="online.onlinecohort",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="magic_link_tokens",
                        to="online.onlinestudentprofile",
                    ),
                ),
            ],
            options={
                "db_table": "online_magic_link_token",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="onlinemagiclinktoken",
            index=models.Index(fields=["expires_at"], name="online_magi_expires_77bf6a_idx"),
        ),
        migrations.AddIndex(
            model_name="onlinemagiclinktoken",
            index=models.Index(fields=["revoked_at"], name="online_magi_revoked_9ad860_idx"),
        ),
    ]
