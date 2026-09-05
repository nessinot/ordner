"""Openstaande uploads tussen scherm 1 (bestanden) en scherm 2 (gegevens) van de tweestaps upload (pakket 15b).

Een HTML-formulier kan gekozen bestanden niet nog eens meesturen, dus tussen de twee schermen
houdt de server de bytes, de gelezen tekst, de datum en de suggesties vast: uitsluitend in het
geheugen, onder een willekeurig token in de URL van scherm 2. Er komt niets op schijf vóór
Opslaan. Een openstaande upload verdwijnt bij opslaan, annuleren, herstart of verlopen.

Vuilnisbak, geen bewaarfunctie: wie het tabblad sluit laat bytes achter, daarom een TTL en een
maximum. Opruimen gebeurt alleen bij het aanmaken van een nieuwe; er is geen achtergrondtaak.
Alle toegang gebeurt op de event loop, dus er is geen locking nodig.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from ordner.ingest import Voorbereid
from ordner.suggestie import Suggestie

_TTL = timedelta(minutes=60)
_MAXIMUM = 10


@dataclass
class OpenstaandeUpload:
    token: str
    voorbereid: Voorbereid  # uit ingest.lees_vooraf: bestanden, teksten, datum, datumbron
    suggestie: Suggestie  # uit suggestie.stel_voor
    aangemaakt: datetime
    inbox_naam: str | None = None  # gevuld als de upload uit de inbox komt (pakket 17); het bestand blijft daar tot Opslaan


class OpenstaandeUploads:
    """Geheugenopslag voor openstaande uploads; `nu` is injecteerbaar voor tests."""

    def __init__(
        self,
        ttl: timedelta = _TTL,
        maximum: int = _MAXIMUM,
        nu: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._ttl = ttl
        self._maximum = maximum
        self._nu = nu
        self._uploads: dict[str, OpenstaandeUpload] = {}  # invoegvolgorde = oudste eerst

    def maak(
        self, voorbereid: Voorbereid, suggestie: Suggestie, inbox_naam: str | None = None
    ) -> OpenstaandeUpload:
        """Gooit eerst verlopen en overtollige (oudste eerst) uploads weg; geeft de nieuwe terug."""
        self._ruim_op()
        while len(self._uploads) >= self._maximum:
            oudste = next(iter(self._uploads))
            del self._uploads[oudste]
        token = secrets.token_urlsafe(16)
        while token in self._uploads:  # praktisch onmogelijk, maar een botsing mag nooit een upload overschrijven
            token = secrets.token_urlsafe(16)
        upload = OpenstaandeUpload(token, voorbereid, suggestie, self._nu(), inbox_naam)
        self._uploads[token] = upload
        return upload

    def haal(self, token: str) -> OpenstaandeUpload | None:
        """De openstaande upload bij `token`; None als onbekend of verlopen."""
        upload = self._uploads.get(token)
        if upload is None:
            return None
        if self._verlopen(upload):
            del self._uploads[token]
            return None
        return upload

    def verwijder(self, token: str) -> None:
        self._uploads.pop(token, None)

    def __len__(self) -> int:
        return len(self._uploads)

    def _verlopen(self, upload: OpenstaandeUpload) -> bool:
        return self._nu() - upload.aangemaakt >= self._ttl

    def _ruim_op(self) -> None:
        for token in [t for t, u in self._uploads.items() if self._verlopen(u)]:
            del self._uploads[token]
