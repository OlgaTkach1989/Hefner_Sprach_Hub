from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("online", "0010_onlinesession_provider_meeting_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="onlinesession",
            name="attendance_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="onlinesession",
            index=models.Index(fields=["attendance_synced_at"], name="online_sess_attendan_14696f_idx"),
        ),
    ]

