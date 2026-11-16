"""The checks of a topic's items move from `checked.yaml` beside the topic's files into the database (a deploy replaces
the code's folder, and every check made on the live desk went with it). The checks files a folder holds are read once
here; the code reads none after. The review desk's right moves onto the new model with its grants, its name unchanged
(`topics.review_topic`)."""
from pathlib import Path

import django.db.models.deletion
import yaml
from django.conf import settings
from django.db import migrations, models

TOPICS = Path(__file__).resolve().parent.parent


def files_into_rows(ItemCheck, base: Path = TOPICS) -> int:
    """Each `<topic>/checked.yaml` under `base`, as rows; a ref already a row is left as it is."""
    made = 0
    for path in sorted(base.glob('*/checked.yaml')):
        topic = path.parent.name.replace('_', '-')
        checks = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        if not isinstance(checks, dict):
            continue
        have = set(ItemCheck.objects.filter(topic=topic).values_list('ref', flat=True))
        rows = [ItemCheck(topic=topic, ref=str(ref)[:120], by=str(c.get('by') or '')[:80], on=str(c.get('on')),
                          digests=c.get('digests') if isinstance(c.get('digests'), dict) else {})
                for ref, c in checks.items() if isinstance(c, dict) and c.get('on') and str(ref) not in have]
        ItemCheck.objects.bulk_create(rows)
        made += len(rows)
    return made


def read_files(apps, schema_editor):
    files_into_rows(apps.get_model('topics', 'ItemCheck'))


def move_the_right(apps, schema_editor):
    """The permission row declared on Helped (0004), if this database made it, now names ItemCheck: whoever was given
    it keeps it, and no second row with its name is made."""
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    old = Permission.objects.filter(codename='review_topic', content_type__app_label='topics',
                                    content_type__model='helped').first()
    if old is None:
        return
    new, _ = ContentType.objects.get_or_create(app_label='topics', model='itemcheck')
    if Permission.objects.filter(codename='review_topic', content_type=new).exists():
        return
    old.content_type = new
    old.save(update_fields=['content_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('topics', '0004_review_permission'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='helped',
            options={},
        ),
        migrations.CreateModel(
            name='ItemCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('topic', models.CharField(max_length=40)),
                ('ref', models.CharField(max_length=120)),
                ('by', models.CharField(max_length=80)),
                ('on', models.DateField()),
                ('digests', models.JSONField(blank=True, default=dict)),
                ('at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(blank=True, help_text='Who checked it on the desk; none for `manage.py approve_topic`.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'topics_item_check',
                'permissions': [('review_topic', "Can mark a topic's items checked")],
                'constraints': [models.UniqueConstraint(fields=('topic', 'ref'), name='topics_item_check_once')],
            },
        ),
        migrations.RunPython(move_the_right, migrations.RunPython.noop),
        migrations.RunPython(read_files, migrations.RunPython.noop),
    ]
