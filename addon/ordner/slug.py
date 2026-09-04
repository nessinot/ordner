"""Slug-generatie voor mapnamen (pakket 02)."""

from __future__ import annotations

import re
import unicodedata

MAX_LENGTE = 60
FALLBACK = "document"


def maak_slug(titel: str) -> str:
    """Zet een titel om naar een veilige, korte mapnaam-component.

    Regels: NFKD-normalisatie, combining characters strippen, lowercase,
    alles buiten [a-z0-9] wordt '-', herhaalde '-' samenvoegen, '-' aan de
    randen strippen, max 60 tekens, leeg -> 'document'.
    """
    genormaliseerd = unicodedata.normalize("NFKD", titel)
    zonder_accenten = "".join(c for c in genormaliseerd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", zonder_accenten.lower()).strip("-")
    slug = slug[:MAX_LENGTE].strip("-")
    return slug or FALLBACK
