"""Documenten aanmaken uit uploads en inbox, met de documentdatum uit de tekst (pakket 14, twee fasen sinds 15a).

Eén codepad voor het uploadformulier en de inbox, in twee fasen: `lees_vooraf` leest zonder
opgegeven datum de tekst van de extraheerbare bestanden *vóór* het aanmaken van de map (zodat
de map de gevonden datum in zijn naam krijgt en nooit hernoemd hoeft te worden) en
`maak_document_uit_voorbereid` maakt daarna de map en schrijft alles weg. Tussen die fasen kan
de aanroeper de tekst gebruiken voor een titel- en tagsuggestie (`suggestie.py`).
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from ordner.datum import vind_datum
from ordner.extract import ExtractieFout, extract_bestand
from ordner.meta import DatumBron, bepaal_ocr_status, is_extraheerbaar, lees_meta, schrijf_meta, schrijf_txt
from ordner.storage import Archief

log = logging.getLogger(__name__)

LeesTekst = Callable[[Path], "str | None"]  # synchroon; None als extractie mislukt
QueueFn = Callable[[Path, str], None]


def maak_tekstlezer(talen: str) -> LeesTekst:
    """Synchrone wrapper om `extract_bestand`, met een eigen event loop. Draai hem in een thread (`asyncio.to_thread`)."""

    def lees(pad: Path) -> str | None:
        try:
            return asyncio.run(extract_bestand(pad, talen))
        except ExtractieFout as e:
            log.warning("tekst vooraf lezen mislukt voor %s: %s", pad.name, e)
            return None

    return lees


@dataclass
class Voorbereid:
    """Resultaat van `lees_vooraf`: de bestanden, de vooraf gelezen teksten en de bepaalde datum."""

    bestanden: list[tuple[str, bytes]]
    teksten: dict[int, str]  # index in `bestanden` -> gelezen tekst
    documentdatum: date
    datumbron: DatumBron  # "gebruiker" | "tekst" | "upload"

    @property
    def tekst(self) -> str:
        """Alle gelezen teksten in uploadvolgorde, gescheiden door een lege regel (voor `suggestie.stel_voor`)."""
        return "\n\n".join(self.teksten[i] for i in sorted(self.teksten))


def lees_vooraf(
    bestanden: list[tuple[str, bytes]],
    *,
    documentdatum: date | None,
    lees_tekst: LeesTekst | None,
    vandaag: date | None = None,
) -> Voorbereid:
    """Fase 1: tekst lezen en de documentdatum bepalen, nog zonder iets in het archief te schrijven.

    - `documentdatum` gegeven: niets lezen, bron `gebruiker`.
    - None en `lees_tekst` beschikbaar: extraheerbare bestanden lezen (tempbestand met de originele
      extensie); de eerste treffer van `vind_datum` bepaalt de datum (bron `tekst`), anders vandaag
      (bron `upload`).
    """
    vandaag = vandaag or date.today()
    if documentdatum is not None:
        return Voorbereid(bestanden, {}, documentdatum, "gebruiker")

    teksten: dict[int, str] = {}
    datum = vandaag
    bron: DatumBron = "upload"
    if lees_tekst is not None:
        with tempfile.TemporaryDirectory(prefix="ordner-") as tmp:
            for i, (naam, data) in enumerate(bestanden):
                if not is_extraheerbaar(naam):
                    continue
                pad = Path(tmp) / f"{i}_{Path(naam).name}"
                pad.write_bytes(data)
                tekst = lees_tekst(pad)
                if tekst is None:
                    continue
                teksten[i] = tekst
                if bron != "tekst":
                    treffer = vind_datum(tekst, vandaag)
                    if treffer is not None:
                        datum, bron = treffer.datum, "tekst"
                        log.info("datum uit tekst in %s: %s (%s: %r)", naam, datum, treffer.sleutelwoord, treffer.regel[:80])
        if bron != "tekst":
            log.info("geen datum in tekst van %s; documentdatum wordt vandaag", [naam for naam, _ in bestanden])
    return Voorbereid(bestanden, teksten, datum, bron)


def maak_document_uit_voorbereid(
    archief: Archief,
    titel: str,
    vb: Voorbereid,
    *,
    omschrijving: str = "",
    tags: list[str] | None = None,
    queue_fn: QueueFn,
    documentdatum: date | None = None,
) -> Path:
    """Fase 2: map aanmaken, bestanden en gelezen `.txt`'s schrijven, de rest queuen; geeft de documentmap terug.

    `documentdatum` None → `vb.documentdatum` met `vb.datumbron`; anders die datum met bron `gebruiker`
    (de gebruiker wijzigde het voorgevulde veld).
    """
    if documentdatum is None:
        datum, bron = vb.documentdatum, vb.datumbron
    else:
        datum, bron = documentdatum, "gebruiker"
    doc = archief.maak_document(titel, datum, omschrijving, tags, datumbron=bron)
    te_queuen: list[str] = []
    for i, (naam, data) in enumerate(vb.bestanden):
        opgeslagen = archief.voeg_bestand_toe(doc, naam, data)
        if i in vb.teksten:
            schrijf_txt(doc / opgeslagen, vb.teksten[i])
        elif is_extraheerbaar(opgeslagen):
            te_queuen.append(opgeslagen)
    if vb.teksten:
        meta = lees_meta(doc)
        meta.ocr = bepaal_ocr_status(doc, meta)
        schrijf_meta(doc, meta)
    # Pas queuen als alles op schijf staat: deze functie draait in een thread en de worker zou anders
    # gelijktijdig meta.md lezen/schrijven (lost update; op Windows PermissionError bij os.replace).
    for opgeslagen in te_queuen:
        queue_fn(doc, opgeslagen)
    return doc


def maak_document_uit_bestanden(
    archief: Archief,
    titel: str,
    bestanden: list[tuple[str, bytes]],
    *,
    documentdatum: date | None,
    omschrijving: str = "",
    tags: list[str] | None = None,
    lees_tekst: LeesTekst | None,
    queue_fn: QueueFn,
    vandaag: date | None = None,
) -> Path:
    """Beide fasen in één keer (`lees_vooraf` + `maak_document_uit_voorbereid`); geeft de documentmap terug.

    - `documentdatum` gegeven: bron `gebruiker`; extraheerbare bestanden gaan naar de OCR-queue.
    - `documentdatum` None en `lees_tekst` beschikbaar: tekst eerst lezen, datum zoeken (bron `tekst`),
      anders vandaag (bron `upload`). Gelezen tekst wordt direct als `.txt` weggeschreven; wat niet
      gelezen kon worden gaat alsnog naar de queue.
    """
    vb = lees_vooraf(bestanden, documentdatum=documentdatum, lees_tekst=lees_tekst, vandaag=vandaag)
    return maak_document_uit_voorbereid(archief, titel, vb, omschrijving=omschrijving, tags=tags, queue_fn=queue_fn)
