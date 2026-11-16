"""The explanations already written, read in the new shape: the state readers see is the newest revision whose words
are the explanation's own, checked when the explanation was; an explanation nobody checked waits on its newest
revision. Earlier states keep no mark of a check (none was kept), so readers no longer see them in the history."""
from django.db import migrations


def forward(apps, schema_editor):
    Explanation = apps.get_model('explain', 'Explanation')
    Revision = apps.get_model('explain', 'Revision')
    by_explanation: dict[int, list] = {}
    for r in Revision.objects.order_by('-created_at', '-id'):
        by_explanation.setdefault(r.explanation_id, []).append(r)
    checked, waiting = [], []
    for e in Explanation.objects.all():
        rows = by_explanation.get(e.pk, [])
        if e.reviewed_at is not None:
            same = next((r for r in rows if (r.body, r.headline, r.sources) == (e.body, e.headline, e.sources)), None)
            if same is not None:
                same.checked_at, same.checked_by_id = e.reviewed_at, e.reviewed_by_id
                checked.append(same)
        elif rows:
            e.pending_id = rows[0].pk
            waiting.append(e)
    Revision.objects.bulk_update(checked, ['checked_at', 'checked_by'])
    Explanation.objects.bulk_update(waiting, ['pending'])


class Migration(migrations.Migration):

    dependencies = [('explain', '0002_gates')]

    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
