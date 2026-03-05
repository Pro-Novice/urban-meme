from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("seed_licenses", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LicenseSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("license_number", models.CharField(db_index=True, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
