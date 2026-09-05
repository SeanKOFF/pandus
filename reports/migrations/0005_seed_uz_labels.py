"""Узбекские названия для стартовых категорий."""

from django.db import migrations

UZ = {
    "no_ramp": "Pandus yo‘q",
    "broken_sidewalk": "Buzilgan piyodalar yo‘lkasi",
    "blocked": "Yo‘l to‘silgan",
    "other": "Boshqa",
}


def seed(apps, schema_editor):
    Category = apps.get_model("reports", "Category")
    for code, label in UZ.items():
        Category.objects.filter(code=code, label_uz="").update(label_uz=label)


def unseed(apps, schema_editor):
    Category = apps.get_model("reports", "Category")
    Category.objects.filter(code__in=UZ).update(label_uz="")


class Migration(migrations.Migration):
    dependencies = [("reports", "0004_category_label_uz_reporter_language_and_more")]
    operations = [migrations.RunPython(seed, unseed)]
