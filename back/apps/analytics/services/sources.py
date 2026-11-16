"""How a reader came to a visit's first page, read from the referring site's host when the browser did not say it
(page.shown's `source`): a search engine, an assistant, a social network or a messenger, another site, or none.
Only the host is ever sent, never the page it came from: what was searched or asked stays with the reader.

A phone's app that opens the site gives its package as the host (`android-app://com.whatsapp/`): the few that matter
are named with the sites."""

SEARCH = ('google', 'bing', 'duckduckgo', 'yahoo', 'yandex', 'ecosia', 'qwant', 'baidu', 'brave', 'startpage')
# What stands before a search engine's name in its hosts: «www.google.co.ma», «search.brave.com», «r.search.yahoo.com».
SEARCH_LEADS = ('www', 'm', 'search', 'html', 'lite', 'r', 'cn')
SEARCH_APPS = ('com.google.android.googlequicksearchbox',)
ASSISTANTS = ('chatgpt.com', 'chat.openai.com', 'claude.ai', 'perplexity.ai', 'gemini.google.com',
              'copilot.microsoft.com')
SOCIAL = ('facebook.com', 'fb.com', 'instagram.com', 'whatsapp.com', 'wa.me', 't.co', 'x.com', 'twitter.com',
          'linkedin.com', 'lnkd.in', 'youtube.com', 'youtu.be', 'tiktok.com', 'telegram.org', 't.me', 'messenger.com',
          'snapchat.com', 'threads.net', 'reddit.com',
          'com.facebook.katana', 'com.facebook.orca', 'com.instagram.android', 'com.whatsapp', 'org.telegram.messenger')


def _under(host: str, domains) -> bool:
    """`host` is one of `domains` or a host under one («l.facebook.com» under «facebook.com»)."""
    return any(host == d or host.endswith('.' + d) for d in domains)


def _search_engine(host: str) -> bool:
    """A search engine's own host: its name first once the usual leads are taken off («mail.google.com» is not)."""
    labels = host.split('.')
    while len(labels) > 2 and labels[0] in SEARCH_LEADS:
        labels = labels[1:]
    return labels[0] in SEARCH or host in SEARCH_APPS


def of(ref: str | None) -> str:
    """'search', 'assistant', 'social', 'site', or 'direct' when no host came."""
    if not ref:
        return 'direct'
    host = ref.lower()
    if _under(host, ASSISTANTS):
        return 'assistant'
    if _under(host, SOCIAL):
        return 'social'
    if _search_engine(host):
        return 'search'
    return 'site'
