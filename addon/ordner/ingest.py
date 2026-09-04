"""Documenten aanmaken uit uploads en inbox, met de documentdatum uit de tekst (pakket 14).

Eén codepad voor het uploadformulier en de inbox. Zonder opgegeven datum wordt de tekst
van de extraheerbare bestanden *vóór* het aanmaken van de map gelezen, zodat de map de
gevonden datum in zijn naam krijgt en nooit hernoemd hoeft te worden.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
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
    """Maakt een document aan en slaat de bestanden op; geeft de documentmap terug.

    - `documentdatum` gegeven: bron `gebruiker`; extraheerbare bestanden gaan naar de OCR-queue.
    - `documentdatum` None en `lees_tekst` beschikbaar: tekst eerst lezen, datum zoeken (bron `tekst`),
      anders vandaag (bron `upload`). Gelezen tekst wordt direct als `.txt` weggeschreven; wat niet
      gelezen kon worden gaat alsnog naar de queue.
    """
    vandaag = vandaag or date.today()
    teksten: dict[int, str] = {}  # index in `bestanden` -> tekst
    bron: DatumBron = "gebruiker"
    datum = documentdatum

    if datum is None:
        bron = "upload"
        datum = vandaag
        if lees_tekst is not None:
            treffer_gevonden = False
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
                    if not treffer_gevonden:
                        treffer = vind_datum(tekst, vandaag)
                        if treffer is not None:
                            treffer_gevonden = True
                            datum, bron = treffer.datum, "tekst"
                            log.info("datum uit tekst voor %r: %s (%s: %r)", titel, datum, treffer.sleutelwoord, treffer.regel[:80])
            if not treffer_gevonden:
                log.info("geen datum in tekst voor %r; documentdatum wordt vandaag", titel)

    doc = archief.maak_document(titel, datum, omschrijving, tags, datumbron=bron)
    te_queuen: list[str] = []
    for i, (naam, data) in enumerate(bestanden):
        opgeslagen = archief.voeg_bestand_toe(doc, naam, data)
        if i in teksten:
            schrijf_txt(doc / opgeslagen, teksten[i])
        elif is_extraheerbaar(opgeslagen):
            te_queuen.append(opgeslagen)
    if teksten:
        meta = lees_meta(doc)
        meta.ocr = bepaal_ocr_status(doc, meta)
        schrijf_meta(doc, meta)
    # Pas queuen als alles op schijf staat: deze functie draait in een thread en de worker zou anders
    # gelijktijdig meta.md lezen/schrijven (lost update; op Windows PermissionError bij os.replace).
    for opgeslagen in te_queuen:
        queue_fn(doc, opgeslagen)
    return doc
