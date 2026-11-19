from django.db import migrations

CENTERS = [
    ("CAC", "Center for Applied Computing"),
    ("CDSA", "Center for Data Science and Analytics"),
    ("CCSE", "CCSE-wide"),
]


def clean(name):
    return " ".join(str(name).split())


def copy_forward(apps, schema_editor):
    Center = apps.get_model("conferences", "Center")
    Theme = apps.get_model("conferences", "Theme")
    Conference = apps.get_model("conferences", "Conference")
    centers = {}
    for code, name in CENTERS:
        centers[code], _ = Center.objects.get_or_create(code=code, defaults={"name": name})
    themes = {}
    for conference in Conference.objects.all():
        if conference.cac_relevant:
            conference.centers.add(centers["CAC"])
        if conference.cdsa_relevant:
            conference.centers.add(centers["CDSA"])
        values = conference.legacy_themes or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            label = clean(value)
            if not label:
                continue
            key = label.casefold()
            if key not in themes:
                themes[key], _ = Theme.objects.get_or_create(key=key, defaults={"name": label[:120]})
            conference.themes.add(themes[key])


def copy_backward(apps, schema_editor):
    Conference = apps.get_model("conferences", "Conference")
    for conference in Conference.objects.all():
        codes = set(conference.centers.values_list("code", flat=True))
        conference.cac_relevant = "CAC" in codes
        conference.cdsa_relevant = "CDSA" in codes
        conference.legacy_themes = list(conference.themes.order_by("name").values_list("name", flat=True))
        conference.save(update_fields=["cac_relevant", "cdsa_relevant", "legacy_themes"])


class Migration(migrations.Migration):

    dependencies = [
        ("conferences", "0005_center_theme_tables"),
    ]

    operations = [
        migrations.RunPython(copy_forward, copy_backward),
    ]
