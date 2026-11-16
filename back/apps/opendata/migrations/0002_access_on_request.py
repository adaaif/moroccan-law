"""Access on request: requests, accesses, their days and downloads; a key now belongs to an access.

Keys made before this had no holder (a person issued them in the admin). None can be given one, so they are removed:
their holders ask for an access and make a new key."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def drop_keys_without_a_holder(apps, schema_editor):
    apps.get_model('opendata', 'ApiKey').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('opendata', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Request',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('kind', models.CharField(choices=[('person', 'A person'), ('school', 'A university or a school'), ('newsroom', 'A newsroom'), ('association', 'An association'), ('public', 'A public body'), ('company', 'A company')], max_length=12)),
                ('purpose', models.TextField(max_length=600)),
                ('wants_api', models.BooleanField(default=False)),
                ('wants_data', models.BooleanField(default=False)),
                ('runs_at', models.CharField(blank=True, db_default='', default='', max_length=200)),
                ('volume', models.CharField(choices=[('small', 'Small'), ('medium', 'Medium'), ('large', 'Large')], max_length=6)),
                ('commercial', models.BooleanField(default=False)),
                ('terms', models.CharField(max_length=10)),
                ('state', models.CharField(choices=[('waiting', 'Waiting for an answer'), ('more', 'More was asked of the person'), ('accepted', 'Accepted'), ('declined', 'Declined')], db_default='waiting', default='waiting', max_length=8)),
                ('asked', models.CharField(blank=True, db_default='', default='', max_length=300)),
                ('answer', models.TextField(blank=True, db_default='', default='', max_length=600)),
                ('reason', models.CharField(blank=True, choices=[('unclear', 'The use is not clear: say more'), ('identity', 'We cannot tell who asks'), ('scope', 'More is asked than the use needs'), ('terms', 'The use breaks the terms'), ('later', 'Not now')], db_default='', default='', max_length=8)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'opendata_request'},
        ),
        migrations.CreateModel(
            name='Access',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api', models.BooleanField(default=False)),
                ('data', models.BooleanField(default=False)),
                ('size', models.CharField(choices=[('try', 'Try'), ('app', 'App'), ('partner', 'Partner (its own numbers)')], db_default='try', default='try', max_length=8)),
                ('minute', models.PositiveIntegerField(blank=True, null=True)),
                ('calls', models.PositiveIntegerField(blank=True, null=True)),
                ('articles', models.PositiveIntegerField(blank=True, null=True)),
                ('ends_on', models.DateField()),
                ('state', models.CharField(choices=[('live', 'Live'), ('ended', 'Ended')], db_default='live', default='live', max_length=6)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('ended_reason', models.CharField(blank=True, choices=[('asked', 'The holder asked'), ('terms', 'The terms'), ('leaked', 'A key leaked'), ('unused', 'Unused'), ('expired', 'Its end date passed'), ('account', 'The account was deleted')], db_default='', default='', max_length=8)),
                ('renewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ended_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('request', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='access', to='opendata.request')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accesses', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'opendata_access', 'verbose_name_plural': 'accesses'},
        ),
        migrations.CreateModel(
            name='AccessDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField()),
                ('calls', models.PositiveIntegerField(db_default=0, default=0)),
                ('articles', models.PositiveIntegerField(db_default=0, default=0)),
                ('doors', models.JSONField(default=dict)),
                ('access', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='days', to='opendata.access')),
            ],
            options={'db_table': 'opendata_access_day'},
        ),
        migrations.CreateModel(
            name='Download',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('edition', models.CharField(max_length=10)),
                ('file', models.CharField(max_length=60)),
                ('sha256', models.CharField(blank=True, db_default='', default='', max_length=64)),
                ('by', models.CharField(choices=[('account', 'Signed in, from the account page'), ('key', 'With a key')], max_length=7)),
                ('at', models.DateTimeField(auto_now_add=True)),
                ('access', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='downloads', to='opendata.access')),
            ],
            options={'db_table': 'opendata_download'},
        ),
        migrations.RunPython(drop_keys_without_a_holder, migrations.RunPython.noop),
        migrations.RemoveField(model_name='apikey', name='active'),
        migrations.AlterField(
            model_name='apikey', name='name',
            field=models.CharField(blank=True, db_default='', default='', help_text='What its holder calls it: «the server», «tests».', max_length=60),
        ),
        migrations.AlterField(
            model_name='apikey', name='prefix',
            field=models.CharField(help_text='The first characters, to recognise it.', max_length=12),
        ),
        migrations.AddField(
            model_name='apikey', name='access',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='keys', to='opendata.access'),
            preserve_default=False,
        ),
        migrations.AddField(model_name='apikey', name='last_used_on', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='apikey', name='ended_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddConstraint(
            model_name='request',
            constraint=models.UniqueConstraint(condition=models.Q(('state__in', ('waiting', 'more'))), fields=('user',), name='opendata_request_one_open'),
        ),
        migrations.AddIndex(model_name='request', index=models.Index(fields=['state', 'created_at'], name='opendata_request_queue_idx')),
        migrations.AddConstraint(
            model_name='access',
            constraint=models.UniqueConstraint(condition=models.Q(('state', 'live')), fields=('user',), name='opendata_access_one_live'),
        ),
        migrations.AddIndex(model_name='access', index=models.Index(fields=['state', 'ends_on'], name='opendata_access_ends_idx')),
        migrations.AddIndex(model_name='apikey', index=models.Index(fields=['access', 'ended_at'], name='opendata_key_access_idx')),
        migrations.AddConstraint(
            model_name='accessday',
            constraint=models.UniqueConstraint(fields=('access', 'day'), name='opendata_access_day_unique'),
        ),
        migrations.AddIndex(model_name='download', index=models.Index(fields=['access', 'at'], name='opendata_download_access_idx')),
    ]
