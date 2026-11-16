import django.db.models.deletion
from django.db import migrations, models


def bm25(apps, schema_editor):
    """The BM25 index (ParadeDB): whitespace tokens, since ma_law has already folded and stemmed the words."""
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('CREATE EXTENSION IF NOT EXISTS pg_search')
    schema_editor.execute(
        'CREATE INDEX search_entry_bm25 ON search_entry USING bm25 '
        '(id, (terms::pdb.whitespace), (title_terms::pdb.whitespace))')


def drop_bm25(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP INDEX IF EXISTS search_entry_bm25')


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('corpus', '0003_article_printed_page_text_bo_section'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(max_length=300)),
                ('folded', models.CharField(max_length=300)),
                ('results', models.PositiveIntegerField()),
                ('understood_as', models.CharField(blank=True, db_default='', default='', help_text='citation, repaired (keyboard), words, some_words.', max_length=40)),
                ('at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'search_log',
                'indexes': [models.Index(fields=['results', 'at'], name='search_log_results_fe7392_idx')],
            },
        ),
        migrations.CreateModel(
            name='SearchEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('article', 'Article'), ('text', 'Text (its title)')], max_length=10)),
                ('terms', models.TextField(blank=True, db_default='', default='', help_text="The article's words, folded and stemmed (ma_law.index_terms).")),
                ('title_terms', models.TextField(blank=True, db_default='', default='', help_text="The text's title, number and popular names, folded and stemmed.")),
                ('title_folded', models.TextField(blank=True, db_default='', default='', help_text='The title folded, not stemmed: what as-you-type matches a prefix in.')),
                ('text_type', models.CharField(max_length=20)),
                ('year', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('in_force', models.BooleanField(db_default=True, default=True, help_text='False only for a text known to be repealed.')),
                ('weight', models.FloatField(db_default=1.0, default=1.0, help_text='Laws and codes above decrees, decrees above orders and decisions.')),
                ('order', models.PositiveIntegerField(db_default=0, default=0, help_text="The article's place in its text.")),
                ('article', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='corpus.article')),
                ('text', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='corpus.text')),
            ],
            options={
                'db_table': 'search_entry',
                'indexes': [models.Index(fields=['kind', 'text_type', 'year'], name='search_entr_kind_0c4f54_idx')],
            },
        ),
        migrations.RunPython(bm25, drop_bm25),
    ]
