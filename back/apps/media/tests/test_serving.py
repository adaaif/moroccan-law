"""Serving the files: a voice by its signed link, in byte ranges; a picture openly once live, by its link before; a 404
for whatever is gone or outside its folder."""
from itertools import islice
from types import SimpleNamespace

import pytest
from django.core import signing

from apps.discussion.tests.conftest import make_user
from apps.media.models import Clip, Picture, State
from apps.media.services import files, links, ranged, store

pytestmark = pytest.mark.django_db

DATA = bytes(range(256)) * 600          # 153,600 bytes: three reads of 64 KB
UNCACHED = {'Accept-Ranges': 'bytes', 'Cache-Control': 'private, no-store, max-age=0', 'Content-Type': 'audio/mp4'}


@pytest.fixture(autouse=True)
def uploads(settings, tmp_path):
    settings.UPLOADS_DIR = tmp_path / 'uploads'


@pytest.fixture
def author():
    return make_user('writer')


def voice(author, data: bytes = b'', name: str | None = None) -> Clip:
    return Clip.objects.create(owner=author, duration_ms=2000, size=len(data), state=State.LIVE,
                               file_name=store.write('voices', data, 'm4a') if name is None else name)


def headers(r, *names) -> dict:
    return {name: r[name] for name in names}


def test_a_voice_opens_by_its_own_link_for_thirty_minutes(api, author, monkeypatch):
    now = [1_800_000_000.0]
    monkeypatch.setattr(signing, 'time', SimpleNamespace(time=lambda: now[0]))     # the signer's clock
    clip, other = voice(author, b'voice'), voice(author, b'other')
    src, door = links.clip(clip)['src'], f'/api/media/clips/{clip.pk}/audio/'
    token = src.split('?t=')[1]
    picture = Picture.objects.create(id=clip.pk, owner=author, width=1, height=1)     # a draft: its link is signed
    for wrong in (door, f'{door}?t=', f'{door}?t={token}x',
                  door + '?' + links.clip(other)['src'].split('?')[1],              # another voice's link
                  door + '?' + links.picture(picture)['full'].split('?')[1]):       # a picture's, of the same id
        assert api.get(wrong).status_code == 404, wrong
    now[0] += 1800
    r = api.get(src)
    assert r.status_code == 200 and b''.join(r.streaming_content) == b'voice'
    assert headers(r, *UNCACHED) == UNCACHED
    now[0] += 1
    assert api.get(src).status_code == 404


@pytest.mark.parametrize('header, first, last, reads', [
    ('bytes=10-19', 10, 19, [10]),
    ('bytes=1000-', 1000, len(DATA) - 1, [65536, 65536, 21528]),     # never more than 64 KB in memory
])
def test_a_voice_answers_the_bytes_of_the_range_asked_64_kb_at_a_time(api, author, header, first, last, reads):
    r = api.get(links.clip(voice(author, DATA))['src'], HTTP_RANGE=header)
    assert r.status_code == 206 and headers(r, *UNCACHED) == UNCACHED
    assert headers(r, 'Content-Range', 'Content-Length') == {'Content-Range': f'bytes {first}-{last}/{len(DATA)}',
                                                             'Content-Length': str(last - first + 1)}
    chunks = list(r.streaming_content)
    assert b''.join(chunks) == DATA[first:last + 1] and [len(c) for c in chunks] == reads


def test_a_file_cut_short_while_it_is_served_ends_its_answer(api, author):
    clip = voice(author, DATA[:1000])
    r = api.get(links.clip(clip)['src'], HTTP_RANGE='bytes=0-99')
    with store.path_of('voices', clip.file_name).open('r+b') as fh:
        fh.truncate(40)
    assert list(islice(r.streaming_content, 5)) == [DATA[:40]]


@pytest.mark.parametrize('header, size, span', [
    ('bytes=-', 1000, None), ('bytes=-5', 0, None),                                # nothing to send of an empty file
    ('bytes=990-5000', 1000, (990, 999)), ('bytes=-5000', 1000, (0, 999)),      # a range past the file is cut to it
    ('bytes=-0', 1000, None), ('bytes=-1', 1000, (999, 999)),                  # the last 0 bytes, the last one
    ('bytes=1000-', 1000, None), ('bytes=999-', 1000, (999, 999)),             # from past the end, from the last byte
    ('bytes=' + '0' * 14 + '1-', 1000, (1, 999)), ('bytes=' + '0' * 15 + '1-', 1000, None),    # 15 digits, not 16
])
def test_a_range_is_read_within_the_file(header, size, span):
    assert ranged.span(header, size) == span


def test_an_erased_voice_answers_404_by_a_link_minted_before(api, author):
    clip = voice(author, b'voice')
    src = links.clip(clip)['src']
    assert b''.join(api.get(src).streaming_content) == b'voice'
    files.erase([clip])
    assert api.get(src).status_code == 404


@pytest.mark.parametrize('outside', [False, True])
def test_a_voice_whose_file_is_gone_or_leads_out_of_its_folder_answers_404(api, author, tmp_path, outside):
    if outside:
        (tmp_path / 'secret').write_bytes(b'not a voice')
        voices = tmp_path / 'uploads' / 'voices'
        voices.mkdir(parents=True)
        (voices / 'link.m4a').symlink_to(tmp_path / 'secret')
    assert api.get(links.clip(voice(author, name='link.m4a'))['src']).status_code == 404


def test_a_live_picture_is_open_and_a_draft_only_by_its_link(api, author):
    live, draft = (Picture.objects.create(owner=author, state=state, width=1, height=1,
                                          full_name=store.write('pictures', b'full', 'webp'),
                                          thumb_name=store.write('pictures', b'thumb', 'webp'))
                   for state in (State.LIVE, State.DRAFT))
    r = api.get(f'/api/media/pictures/{live.pk}/thumb/')
    assert (b''.join(r.streaming_content), r['Cache-Control'], r['Content-Type']) == (
        b'thumb', 'public, max-age=600', 'image/webp')
    assert api.get(f'/api/media/pictures/{live.pk}/large/').status_code == 404
    assert api.get(f'/api/media/pictures/{draft.pk}/full/').status_code == 404
    other = Picture.objects.create(owner=author, width=1, height=1)
    assert api.get(f'/api/media/pictures/{draft.pk}/full/?' + links.picture(other)['full'].split('?')[1]
                   ).status_code == 404                                            # another draft's link
    r = api.get(links.picture(draft)['full'])
    assert (b''.join(r.streaming_content), r['Cache-Control'], r['Content-Type']) == (
        b'full', 'private, no-store, max-age=0', 'image/webp')


def test_a_picture_whose_file_is_gone_answers_404(api, author):
    gone = Picture.objects.create(owner=author, state=State.LIVE, width=1, height=1, full_name='gone.webp',
                                  thumb_name='gone.webp')
    assert api.get(f'/api/media/pictures/{gone.pk}/full/').status_code == 404


def test_a_name_never_leads_out_of_its_folder(tmp_path):
    for name in ('', '..'):
        with pytest.raises(ValueError, match='escapes its folder'):
            store.path_of('voices', name)
    assert store.path_of('voices', '../../x.m4a') == (tmp_path / 'uploads' / 'voices' / 'x.m4a').resolve()
