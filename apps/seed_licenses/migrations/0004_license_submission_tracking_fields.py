from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("seed_licenses", "0003_merge_0002_alter_eventlog_options_and_more_0002_license_submission"),
    ]

    operations = [
        migrations.AddField(
            model_name="licensesubmission",
            name="license_id",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="licensesubmission",
            name="transaction_hash",
            field=models.CharField(blank=True, db_index=True, max_length=66, null=True),
        ),
    ]
