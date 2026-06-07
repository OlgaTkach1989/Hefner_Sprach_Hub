# Generated manually for online app initialization.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("employees", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OnlineCourse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("title_de", models.CharField(max_length=220)),
                ("title_en", models.CharField(max_length=220)),
                ("short_description_de", models.TextField(max_length=1000)),
                ("short_description_en", models.TextField(max_length=1000)),
                ("description_de", models.TextField()),
                ("description_en", models.TextField()),
                ("lessons_count", models.PositiveSmallIntegerField(default=12)),
                ("trial_available", models.BooleanField(default=False)),
                ("price_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("currency", models.CharField(default="EUR", max_length=8)),
                ("is_subscription", models.BooleanField(default=False)),
                ("is_published", models.BooleanField(default=True)),
                ("hero_image_url", models.URLField(blank=True, null=True)),
                ("seo_title_de", models.CharField(blank=True, default="", max_length=180)),
                ("seo_title_en", models.CharField(blank=True, default="", max_length=180)),
                ("seo_description_de", models.CharField(blank=True, default="", max_length=300)),
                ("seo_description_en", models.CharField(blank=True, default="", max_length=300)),
                ("geo_city", models.CharField(default="Berlin", max_length=100)),
                ("geo_country", models.CharField(default="DE", max_length=2)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "online_course",
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="OnlineStudentProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_name", models.CharField(max_length=120)),
                ("last_name", models.CharField(max_length=120)),
                ("phone", models.CharField(blank=True, default="", max_length=50)),
                ("preferred_language", models.CharField(choices=[("de", "German"), ("en", "English")], default="de", max_length=2)),
                ("is_trial_user", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="online_profile", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "online_student_profile",
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="OnlineCourseFaq",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question_de", models.CharField(max_length=300)),
                ("question_en", models.CharField(max_length=300)),
                ("answer_de", models.TextField()),
                ("answer_en", models.TextField()),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="faqs", to="online.onlinecourse")),
            ],
            options={
                "db_table": "online_course_faq",
                "ordering": ("sort_order", "id"),
            },
        ),
        migrations.CreateModel(
            name="OnlineCourseMaterial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "material_type",
                    models.CharField(
                        choices=[("resource", "Resource"), ("recording", "Recording"), ("condition", "Condition")],
                        default="resource",
                        max_length=20,
                    ),
                ),
                ("language", models.CharField(choices=[("de", "German"), ("en", "English")], default="de", max_length=2)),
                ("link_url", models.URLField(blank=True, null=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="materials", to="online.onlinecourse")),
            ],
            options={
                "db_table": "online_course_material",
                "ordering": ("sort_order", "id"),
            },
        ),
        migrations.CreateModel(
            name="OnlineCohort",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=220)),
                ("group_code", models.CharField(max_length=80, unique=True)),
                ("capacity", models.PositiveSmallIntegerField(default=20)),
                ("timezone", models.CharField(default="Europe/Berlin", max_length=64)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("open", "Open"), ("running", "Running"), ("finished", "Finished")],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("is_public", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cohorts", to="online.onlinecourse")),
                (
                    "teacher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="online_cohorts",
                        to="employees.lehrer",
                    ),
                ),
            ],
            options={
                "db_table": "online_cohort",
                "ordering": ("start_date", "id"),
            },
        ),
        migrations.CreateModel(
            name="OnlineSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True, default="")),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("join_url", models.URLField(blank=True, null=True)),
                ("recording_url", models.URLField(blank=True, null=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_completed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("cohort", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="online.onlinecohort")),
            ],
            options={
                "db_table": "online_session",
                "ordering": ("sort_order", "starts_at", "id"),
            },
        ),
        migrations.CreateModel(
            name="OnlineOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("paypal", "PayPal"), ("klarna", "Klarna"), ("sofort", "Sofort"), ("trial", "Trial")], max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed"), ("refunded", "Refunded"), ("trial", "Trial")], default="pending", max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=10)),
                ("currency", models.CharField(default="EUR", max_length=8)),
                ("is_trial", models.BooleanField(default=False)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("idempotency_key", models.CharField(blank=True, max_length=120, null=True, unique=True)),
                ("external_reference", models.CharField(blank=True, default="", max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("cohort", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="online.onlinecohort")),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="online.onlinecourse")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="orders", to="online.onlinestudentprofile")),
            ],
            options={
                "db_table": "online_order",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="OnlineEnrollment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("trial", "Trial"), ("active", "Active"), ("suspended", "Suspended"), ("completed", "Completed"), ("revoked", "Revoked")], default="active", max_length=20)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("cohort", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="online.onlinecohort")),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="online.onlinecourse")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="enrollments", to="online.onlineorder")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enrollments", to="online.onlinestudentprofile")),
            ],
            options={
                "db_table": "online_enrollment",
                "ordering": ("-started_at",),
                "unique_together": {("profile", "cohort")},
            },
        ),
        migrations.CreateModel(
            name="OnlineAttendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("unknown", "Unknown"), ("present", "Present"), ("absent", "Absent"), ("excused", "Excused")], default="unknown", max_length=20)),
                ("attended_seconds", models.PositiveIntegerField(default=0)),
                ("joined_at", models.DateTimeField(blank=True, null=True)),
                ("left_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.CharField(blank=True, default="", max_length=300)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_records", to="online.onlineenrollment")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_records", to="online.onlinesession")),
            ],
            options={
                "db_table": "online_attendance",
                "ordering": ("session__starts_at",),
                "unique_together": {("enrollment", "session")},
            },
        ),
        migrations.CreateModel(
            name="OnlineFeedbackMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=180)),
                ("email", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=220)),
                ("message", models.TextField()),
                ("preferred_language", models.CharField(choices=[("de", "German"), ("en", "English")], default="de", max_length=2)),
                ("source_page", models.CharField(blank=True, default="", max_length=200)),
                ("is_resolved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("course", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="feedback_messages", to="online.onlinecourse")),
            ],
            options={
                "db_table": "online_feedback_message",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="OnlineSupportMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender_type", models.CharField(choices=[("student", "Student"), ("support", "Support")], default="student", max_length=20)),
                ("message", models.TextField()),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("enrollment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="support_messages", to="online.onlineenrollment")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="support_messages", to="online.onlinestudentprofile")),
            ],
            options={
                "db_table": "online_support_message",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="onlinecourse",
            index=models.Index(fields=["is_published"], name="online_cour_is_publ_1a76ad_idx"),
        ),
        migrations.AddIndex(
            model_name="onlinecourse",
            index=models.Index(fields=["slug"], name="online_cour_slug_9f20a2_idx"),
        ),
        migrations.AddIndex(
            model_name="onlinecohort",
            index=models.Index(fields=["status"], name="online_coho_status_7fef41_idx"),
        ),
        migrations.AddIndex(
            model_name="onlinecohort",
            index=models.Index(fields=["group_code"], name="online_coho_group_c_2ad8bf_idx"),
        ),
        migrations.AddIndex(
            model_name="onlinesession",
            index=models.Index(fields=["starts_at"], name="online_sess_starts__b6ee41_idx"),
        ),
        migrations.AddIndex(
            model_name="onlinesession",
            index=models.Index(fields=["is_completed"], name="online_sess_is_comp_d154b6_idx"),
        ),
        migrations.AddIndex(
            model_name="onlineorder",
            index=models.Index(fields=["status"], name="online_orde_status_12c7d2_idx"),
        ),
        migrations.AddIndex(
            model_name="onlineorder",
            index=models.Index(fields=["provider"], name="online_orde_provide_4d9f14_idx"),
        ),
        migrations.AddIndex(
            model_name="onlineenrollment",
            index=models.Index(fields=["status"], name="online_enro_status_8eec68_idx"),
        ),
    ]
