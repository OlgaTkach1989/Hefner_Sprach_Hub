from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("online", "0009_expand_online_session_url_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="onlinesession",
            name="provider_meeting_id",
            field=models.CharField(blank=True, default="", max_length=220),
        ),
    ]

