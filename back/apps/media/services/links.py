"""The signed links an <audio> or an <img> carries: they cannot carry a Bearer header. Who may have one is decided
before minting; a link only proves "this file, for the next VOICE_LINK_SECONDS". A live picture needs no link."""
from datetime import timedelta

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils import timezone

from apps.media.models import Clip, Picture, State

_clips = TimestampSigner(salt='media.clip')
_pictures = TimestampSigner(salt='media.picture')
_cards = TimestampSigner(salt='media.card')


def clip(row: Clip) -> dict:
    expires = timezone.now() + timedelta(seconds=settings.VOICE_LINK_SECONDS)
    return {'src': f'/api/media/clips/{row.pk}/audio/?t={_clips.sign(str(row.pk))}',
            'expires_at': expires.isoformat()}


def picture(row: Picture) -> dict:
    """Both sizes: plain addresses when the picture is live, signed ones otherwise (its author, a reviewer)."""
    query = '' if row.state == State.LIVE else f'?t={_pictures.sign(str(row.pk))}'
    return {'id': str(row.pk), 'full': f'/api/media/pictures/{row.pk}/full/{query}',
            'thumb': f'/api/media/pictures/{row.pk}/thumb/{query}', 'width': row.width, 'height': row.height}


def _valid(signer: TimestampSigner, token: str, pk) -> bool:
    try:
        return signer.unsign(token or '', max_age=settings.VOICE_LINK_SECONDS) == str(pk)
    except (BadSignature, SignatureExpired):
        return False


def clip_valid(token: str, pk) -> bool:
    return _valid(_clips, token, pk)


def picture_valid(token: str, pk) -> bool:
    return _valid(_pictures, token, pk)
