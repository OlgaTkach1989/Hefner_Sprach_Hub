from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("online", "0008_onlinesessionreminder"),
    ]

    operations = [
        migrations.AlterField(
            model_name="onlinesession",
            name="join_url",
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name="onlinesession",
            name="recording_url",
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
    ]

