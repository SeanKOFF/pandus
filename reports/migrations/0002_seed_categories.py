"""Стартовый набор категорий, включая «Прочее»."""

from django.db import migrations

CATEGORIES = [
    ("no_ramp", "Нет пандуса", "#C4292E", 10),
    ("broken_sidewalk", "Разбитый тротуар", "#B9760A", 20),
    ("blocked", "Перекрыт проезд", "#546670", 30),
    ("other", "Прочее", "#7B5EA7", 40),
]


def seed(apps, schema_editor):
    Category = apps.get_model("reports", "Category")
    for code, label, color, order in CATEGORIES:
        Category.objects.get_or_create(
            code=code,
            defaults={"label_ru": label, "color_hex": color, "sort_order": order},
        )


def unseed(apps, schema_editor):
    Category = apps.get_model("reports", "Category")
    Category.objects.filter(code__in=[c[0] for c in CATEGORIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("reports", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
