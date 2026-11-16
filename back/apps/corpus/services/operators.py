"""The network operator an address belongs to, for the day of reading's READING_OPERATOR_CEILING
(apps/corpus/services/reading.py): its number (ASN) from DB-IP's free «IP to ASN Lite» database (CC BY 4.0, NOTICE),
read locally from GEOIP_DIR, where `fetch_geoip` writes it. Nothing is kept of the address."""
from pathlib import Path

from django.conf import settings

ASN = 'dbip-asn-lite.mmdb'

_readers: dict = {}


def _reader(name: str):
    """The database, opened once a process; a missing one is looked for again (fetch_geoip may come after the start)."""
    if name not in _readers:
        path = Path(settings.GEOIP_DIR) / name
        if not path.exists():
            return None
        import maxminddb

        _readers[name] = maxminddb.open_database(str(path))
    return _readers[name]


def operator(ip: str) -> int | None:
    """The number (ASN) of the network operator an address belongs to, from DB-IP's database; None when unknown."""
    reader = _reader(ASN)
    try:
        found = reader.get(ip) if reader else None
    except ValueError:
        return None
    return (found or {}).get('autonomous_system_number')
