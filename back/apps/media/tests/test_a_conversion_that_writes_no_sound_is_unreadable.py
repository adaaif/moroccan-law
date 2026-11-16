"""A recording that states three seconds of Opus and carries no frame: ffmpeg exits well and writes an MP4 with no track
at all. The check of what ffmpeg wrote let the reader's own refusal through, so the sender was told their recording held
something other than sound («one_track»), of a file whose one track the door had just proved."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.services.refusals import Refused
from apps.media.services import door
from apps.media.tests.craft import cluster, info, track, tracks, webm


@pytest.mark.needs('ffmpeg')
def test_a_conversion_that_writes_no_sound_is_unreadable():
    silent = webm(info(3000.0), tracks(track()), cluster(0))
    with pytest.raises(Refused) as refused:
        door.prepare(SimpleUploadedFile('take', silent))
    assert (refused.value.field, refused.value.code) == ('voice', 'unreadable')
