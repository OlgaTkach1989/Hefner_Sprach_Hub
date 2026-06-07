from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("online", "0017_onlinecoursemodule_and_activity_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="onlinecourse",
            name="ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onlinecourse",
            name="starts_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onlinecoursemodule",
            name="ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onlinecoursemodule",
            name="starts_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onlinecourselesson",
            name="ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onlinecourselesson",
            name="starts_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
