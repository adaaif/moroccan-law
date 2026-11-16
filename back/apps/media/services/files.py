"""A voice's or a picture's state follows the contribution carrying it: live with it, evidence while it is removed or
frozen for the reviewers, erased with it. Who may hear or see a file is decided before a link is minted
(`links.py`); live pictures are public."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.media.models import Clip, Picture, State
from apps.media.services import door, store


def upload_clip(user, file, peaks) -> Clip:
    audio = door.prepare(file)
    name = store.write('voices', audio.data, 'm4a')
    return Clip.objects.create(owner=user, duration_ms=audio.duration_ms, size=len(audio.data),
                               peaks=door.clean_peaks(peaks), file_name=name)


def draft_of(model, user, pk) -> Clip | Picture:
    """A draft the person uploaded and has not published yet."""
    try:
        row = model.objects.filter(pk=pk, owner=user, state=State.DRAFT).first()
    except (ValueError, TypeError):
        row = None
    if row is None:
        raise Refused('voice' if model is Clip else 'pictures', 'not_found', 404)
    return row


def set_state(rows, state: str) -> None:
    now = timezone.now()
    for row in rows:
        if row is None or row.state == State.ERASED:
            continue
        row.state = state
        fields = ['state']
        if state == State.LIVE and row.published_at is None:
            row.published_at = now
            fields.append('published_at')
        row.save(update_fields=fields)


def erase(rows) -> None:
    """The bytes go at once; the rows stay, emptied: the voices in one update and the pictures in another, whatever
    their number (one a row before), and the discussion's kept answers renewed once, as each row's save renewed them
    (apps.discussion.apps)."""
    from apps.corpus.services import generation

    now = timezone.now()
    clips, pictures = [], []
    for row in rows:
        if row is None or row.state == State.ERASED:
            continue
        if isinstance(row, Clip):
            transaction.on_commit(lambda name=row.file_name: store.delete('voices', name))
            row.file_name = ''
            clips.append(row)
        else:
            for name in (row.full_name, row.thumb_name):
                transaction.on_commit(lambda name=name: store.delete('pictures', name))
            row.full_name = row.thumb_name = ''
            pictures.append(row)
        row.state, row.erased_at = State.ERASED, now
    if clips:
        Clip.objects.bulk_update(clips, ['file_name', 'state', 'erased_at'])
    if pictures:
        Picture.objects.bulk_update(pictures, ['full_name', 'thumb_name', 'state', 'erased_at'])
    if clips or pictures:
        generation.bump('talk')
