from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conferences", "0004_planning_and_access"),
    ]

    operations = [
        migrations.CreateModel(
            name="Center",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=8, unique=True)),
                ("name", models.CharField(max_length=120)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="Theme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("key", models.CharField(editable=False, max_length=120, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.RenameField(model_name="conference", old_name="themes", new_name="legacy_themes"),
        migrations.AddField(
            model_name="conference",
            name="centers",
            field=models.ManyToManyField(blank=True, related_name="conferences", to="conferences.center"),
        ),
        migrations.AddField(
            model_name="conference",
            name="themes",
            field=models.ManyToManyField(blank=True, related_name="conferences", to="conferences.theme"),
        ),
    ]
