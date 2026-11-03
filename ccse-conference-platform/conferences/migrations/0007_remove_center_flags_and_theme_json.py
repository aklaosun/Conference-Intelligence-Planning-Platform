from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("conferences", "0006_copy_centers_and_themes"),
    ]

    operations = [
        migrations.RemoveField(model_name="conference", name="cac_relevant"),
        migrations.RemoveField(model_name="conference", name="cdsa_relevant"),
        migrations.RemoveField(model_name="conference", name="legacy_themes"),
    ]
