"""The development's addresses move to the code's plain name (15 Nov 2026: the code carries no brand): every
«…@demo.matn.invalid» and «…@load.matn.invalid» ends «@demo.law.invalid» and «@load.law.invalid», the part before the
@ unchanged. One UPDATE a domain, never a row at a time. Neither new domain could be held before this: sign-up refuses
every «.invalid» address (services/addresses.py, RESERVED_TLDS), so no address can collide."""
from django.db import migrations
from django.db.models import Value
from django.db.models.functions import Concat, Length, Substr

MOVES = (('@demo.matn.invalid', '@demo.law.invalid'), ('@load.matn.invalid', '@load.law.invalid'))


def _move(apps, pairs):
    User = apps.get_model('accounts', 'User')
    for old, new in pairs:
        User.objects.filter(email__iendswith=old).update(
            email=Concat(Substr('email', 1, Length('email') - len(old)), Value(new)))


def forward(apps, schema_editor):
    _move(apps, MOVES)


def backward(apps, schema_editor):
    _move(apps, [(new, old) for old, new in MOVES])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_google_sub'),
    ]

    operations = [migrations.RunPython(forward, backward)]
