from django.db import migrations


def seed_weights(apps, schema_editor):
    SecretWeight = apps.get_model('exchange', 'SecretWeight')
    existing = set(SecretWeight.objects.values_list('weight', flat=True))
    to_create = [SecretWeight(weight=w) for w in range(1, 6) if w not in existing]
    if to_create:
        SecretWeight.objects.bulk_create(to_create)


def remove_weights(apps, schema_editor):
    SecretWeight = apps.get_model('exchange', 'SecretWeight')
    SecretWeight.objects.filter(weight__in=[1, 2, 3, 4, 5]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('exchange', '0002_exchange_tokens'),
    ]

    operations = [
        migrations.RunPython(seed_weights, remove_weights),
    ]
