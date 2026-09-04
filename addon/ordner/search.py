"""Zoeken over de index (pakket 06)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from ordner.index import DocEntry, Index

_CONTEXT = 80
_WHITESPACE = re.compile(r"\s+")


@dataclass
class Treffer:
    rel: str
    titel: str
    omschrijving: str
    documentdatum: date
    snippet: str
    bron: str  # veldnaam ("titel", "omschrijving", "tags", "documentdatum", "notities") of bestandsnaam


def _velden(entry: DocEntry) -> list[tuple[str, str]]:
    """Doorzoekbare velden in vaste volgorde: metadata eerst, daarna de .txt-teksten."""
    meta = entry.meta
    return [
        ("titel", meta.titel),
        ("omschrijving", meta.omschrijving),
        ("tags", " ".join(meta.tags)),
        ("documentdatum", meta.documentdatum.isoformat()),
        ("notities", meta.notities),
    ] + [(naam, tekst) for naam, tekst in entry.teksten.items()]


def _snippet(tekst: str, i: int, woord: str) -> str:
    """±80 tekens rond positie i, whitespace samengevoegd, met '…' waar afgekapt is."""
    start = max(0, i - _CONTEXT)
    eind = i + len(woord) + _CONTEXT
    fragment = _WHITESPACE.sub(" ", tekst[start:eind]).strip()
    if start > 0:
        fragment = "…" + fragment
    if eind < len(tekst):
        fragment = fragment + "…"
    return fragment


def zoek(index: Index, query: str) -> list[Treffer]:
    """AND over alle woorden (substring, hoofdletterongevoelig) over alle velden van een document.

    Alle treffers in de volgorde van index.alle() (documentdatum desc, rel desc); afkappen doet de weergave.
    """
    woorden = query.lower().split()
    if not woorden:
        return []

    treffers: list[Treffer] = []
    for entry in index.alle():
        velden = [(bron, tekst, tekst.lower()) for bron, tekst in _velden(entry)]
        if not all(any(woord in lower for _, _, lower in velden) for woord in woorden):
            continue

        eerste = woorden[0]
        snippet, bron = "", ""
        for veld_bron, tekst, lower in velden:
            i = lower.find(eerste)
            if i >= 0:
                snippet, bron = _snippet(tekst, i, eerste), veld_bron
                break

        meta = entry.meta
        treffers.append(
            Treffer(
                rel=entry.rel,
                titel=meta.titel,
                omschrijving=meta.omschrijving,
                documentdatum=meta.documentdatum,
                snippet=snippet,
                bron=bron,
            )
        )
    return treffers
