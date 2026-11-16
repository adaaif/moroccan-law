"""A text's and an article's address on the site: its Akoma Ntoso work address under /ma, so a link stays the
same across reloads (a text's database id does not). /akn/ma/act/loi/60-24 → /ma/loi/60-24, and
its article 8 → /ma/loi/60-24/art_8."""

PREFIX = '/akn/ma/act'


def text_path(akn_uri: str) -> str:
    return '/ma' + akn_uri.removeprefix(PREFIX)


def article_path(akn_uri: str, eid: str) -> str:
    return f'{text_path(akn_uri)}/{eid}'


def split_path(path: str) -> tuple[str, str]:
    """A site address → (the text's akn_uri, the article's eid or '')."""
    parts = path.strip('/').removeprefix('ma/').split('/')
    eid = parts.pop() if parts and (parts[-1].startswith('art_') or parts[-1] in ('annex', 'preamble')) else ''
    return f'{PREFIX}/' + '/'.join(parts), eid
