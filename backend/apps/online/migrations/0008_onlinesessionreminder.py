from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("online", "0007_onlinemagiclinktoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnlineSessionReminder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hours_before", models.PositiveSmallIntegerField()),
                ("email_sent", models.BooleanField(default=False)),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                (
                    "enrollment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="session_reminders",
                        to="online.onlineenrollment",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reminders",
                        to="online.onlinesession",
                    ),
                ),
            ],
            options={
                "db_table": "online_session_reminder",
                "ordering": ("-sent_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="onlinesessionreminder",
            constraint=models.UniqueConstraint(
                fields=("enrollment", "session", "hours_before"),
                name="online_session_reminder_unique_per_offset",
            ),
        ),
        migrations.AddIndex(
            model_name="onlinesessionreminder",
            index=models.Index(fields=["hours_before"], name="online_sess_hours_b_0fddbe_idx"),
        ),
        migrations.AddIndex(
            model_name="onlinesessionreminder",
            index=models.Index(fields=["email_sent"], name="online_sess_email_s_472d2f_idx"),
        ),
    ]
