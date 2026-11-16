"""The law-mcp service: `uvicorn config.mcp_asgi:app --host 127.0.0.1 --port 8042` (apps/mcp/server.py)."""
import logging
import os
import threading

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
django.setup()

from apps.mcp.server import asgi  # noqa: E402

app = asgi()

# Each uvicorn worker is its own process (no --preload as gunicorn's): it reads what a search reads on first use, the
# topics' folders and the search's tables, before it answers anyone: a cold worker's first search is slow, the next
# ones are quick (3 Nov 2026). In a thread of its own: uvicorn imports this module inside its event loop, where Django
# refuses the database (SynchronousOnlyOperation would stop the worker, 3 Nov 2026). The thread closes its
# connections; the tools open theirs in their own threads.


def _warm() -> None:
    from django.core.cache import caches
    from django.db import connections

    try:
        from apps.search.services import search
        from apps.topics.services import kit

        kit.warm()
        search.warm()
    except Exception:
        logging.getLogger(__name__).exception('the MCP worker not warmed')
    finally:
        connections.close_all()
        for c in caches.all(initialized_only=True):
            c.close()


_warming = threading.Thread(target=_warm, name='mcp-warm')
_warming.start()
_warming.join()
