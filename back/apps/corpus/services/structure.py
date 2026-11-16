"""From a page's text to the records `corpus` keeps: texts, their numbers and dates, articles,
citations and amendments. Claude reads; nothing is guessed: what the page does not say stays empty.
"""
import json
import time

from apps.sources.services import ocr

PROMPT_VERSION = 'v1'

SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['texts'],
    'properties': {'texts': {'type': 'array', 'items': {
        'type': 'object',
        'additionalProperties': False,
        'required': ['type', 'number_as_printed', 'signed_on_gregorian', 'signed_on_hijri', 'title',
                     'authority', 'promulgates', 'starts_on_page', 'ends_on_page', 'articles', 'cites', 'amends'],
        'properties': {
            'type': {'type': 'string', 'enum': ['dahir', 'law', 'organic_law', 'decree_law', 'decree', 'order',
                                                'decision', 'circular', 'convention', 'other']},
            'number_as_printed': {'type': 'string'},
            'signed_on_gregorian': {'type': 'string', 'description': 'YYYY-MM-DD, or empty'},
            'signed_on_hijri': {'type': 'string', 'description': 'exactly as printed, or empty'},
            'title': {'type': 'string'},
            'authority': {'type': 'string'},
            'promulgates': {'type': 'string', 'description': 'the law a dahir promulgates, or empty'},
            'starts_on_page': {'type': 'boolean'},
            'ends_on_page': {'type': 'boolean'},
            'articles': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['label', 'first_words'],
                'properties': {'label': {'type': 'string'}, 'first_words': {'type': 'string'}}}},
            'cites': {'type': 'array', 'items': {'type': 'string'}},
            'amends': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['target', 'words'],
                'properties': {'target': {'type': 'string'}, 'words': {'type': 'string'}}}},
        }}}},
}

SYSTEM = (
    'You read the text of one page of the Moroccan Bulletin Officiel (or an official legal document) '
    'and list the legal texts on it. For each: its type, its number exactly as printed, its dates '
    '(the Gregorian one as YYYY-MM-DD, the Hijri one exactly as printed), its title, the authority '
    'that issued it, the law it promulgates if it is a promulgating dahir, whether it starts and ends '
    'on this page, its articles (label as printed and the first words), the texts it cites (as printed) '
    'and the amendments it makes (target article or text, and the instruction\'s words). '
    'Use only what the page says; leave a field empty rather than guess.'
)


def extract(text: str, *, model: str = 'claude-sonnet-5-5') -> tuple[dict, dict]:
    """The page's texts as data, and what reading it cost: inside the shared budget, its worst case held while it is
    out and its cost in the ledger as soon as it answers."""
    ocr.check_model(model)
    client = ocr._client()
    started = time.monotonic()
    with ocr.reserve('structure', ocr.call_worst(model, len(SYSTEM) + len(text), 8000)):
        message = client.messages.create(
            model=model, max_tokens=8000, system=SYSTEM,
            output_config={'effort': 'low', 'format': {'type': 'json_schema', 'schema': SCHEMA}},
            messages=[{'role': 'user', 'content': text}],
        )
        cost = ocr.record_call('structure', model, message.usage, prompt_version=PROMPT_VERSION)
    body = ''.join(b.text for b in message.content if getattr(b, 'type', '') == 'text')
    usage = {'model': model, 'input_tokens': message.usage.input_tokens, 'output_tokens': message.usage.output_tokens,
             'cost_usd': float(cost), 'seconds': round(time.monotonic() - started, 1)}
    return json.loads(body), usage
