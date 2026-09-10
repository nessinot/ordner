"""Dubbele bestanden herkennen aan hun SHA-256-vingerafdruk (pakket 16).

De hash van elk bronbestand staat in `meta.md` (`sha256:`); de index houdt er een opzoektabel van
bij. Upload, bestand-toevoegen en inbox vragen hier vóór het opslaan of een aangeboden bestand al
ergens in het archief staat. Alleen byte-identieke bestanden worden herkend.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from ordner.index import Index

_BLOK = 1024 * 1024


def sha256_van(data: bytes) -> str:
    """Hex-hash (lowercase) van bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_van_bestand(pad: Path) -> str:
    """Hex-hash van een bestand op schijf, gelezen in blokken van 1 MiB."""
    h = hashlib.sha256()
    with open(pad, "rb") as f:
        for blok in iter(lambda: f.read(_BLOK), b""):
            h.update(blok)
    return h.hexdigest()


@dataclass(frozen=True)
class Dubbel:
    """Een aangeboden bestand dat al in het archief staat."""

    naam: str  # naam van het aangeboden bestand
    rel: str  # document waar het al staat, bv. "2026/2026-03-01_slug"
    bestand: str  # bestandsnaam daar
    titel: str
    documentdatum: date

    @property
    def jaar(self) -> str:
        return self.rel.partition("/")[0]

    @property
    def map(self) -> str:
        return self.rel.partition("/")[2]


def zoek_dubbelen(index: Index, bestanden: Iterable[tuple[str, bytes]]) -> list[Dubbel]:
    """Voor elk aangeboden (naam, bytes) met een treffer in de index één `Dubbel`, in aangeboden volgorde."""
    return zoek_dubbelen_van_hashes(index, ((naam, sha256_van(data)) for naam, data in bestanden))


def zoek_dubbelen_van_hashes(index: Index, hashes: Iterable[tuple[str, str]]) -> list[Dubbel]:
    """Als `zoek_dubbelen`, maar met al berekende (naam, sha256)-paren; voor terugzetten uit de prullenbak (pakket 20)."""
    dubbelen: list[Dubbel] = []
    for naam, h in hashes:
        treffer = index.zoek_hash(h)
        if treffer is None:
            continue
        entry, bestand = treffer
        dubbelen.append(Dubbel(naam, entry.rel, bestand, entry.meta.titel, entry.meta.documentdatum))
    return dubbelen
