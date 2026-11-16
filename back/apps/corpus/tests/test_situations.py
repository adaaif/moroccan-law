"""Situations reach readers only once approved; a draft's articles are only the candidates' (never invented)."""
import json

import pytest

from apps.corpus.services import situations

pytestmark = pytest.mark.django_db


def test_only_approved_situations_are_published(tmp_path, monkeypatch):
    approved = tmp_path / 'approved.json'
    drafts = tmp_path / 'drafts.json'
    monkeypatch.setattr(situations, 'APPROVED', approved)
    monkeypatch.setattr(situations, 'DRAFTS', drafts)
    drafts.write_text(json.dumps({'situations': [{'slug': 'birth', 'intro': {'ar': 'م', 'fr': 'b'}, 'articles': []}]}))
    assert situations.published() == []
    assert [s['slug'] for s in situations.published(include_drafts=True)] == ['birth']
    assert situations.published(include_drafts=True)[0]['draft'] is True
    approved.write_text(json.dumps({'situations': [{'slug': 'birth', 'intro': {'ar': 'م', 'fr': 'b'}, 'articles': []}]}))
    assert [(s['slug'], s['draft']) for s in situations.published()] == [('birth', False)]
