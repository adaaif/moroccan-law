"""A whole-page correction (a column lost in a reading, 6 Nov 2026) is longer than a btree index row may be: the
uniqueness of a correction is kept on the hash of «wrong» instead of its text."""
from django.db import migrations, models
from django.db.models.functions import MD5


class Migration(migrations.Migration):
    dependencies = [('quality', '0009_suspect_reread')]
    operations = [
        migrations.RemoveConstraint(model_name='correction', name='quality_correction_once'),
        migrations.AddConstraint(
            model_name='correction',
            constraint=models.UniqueConstraint(models.F('path'), MD5('wrong'), models.F('before'), models.F('after'),
                                               name='quality_correction_once'),
        ),
    ]
