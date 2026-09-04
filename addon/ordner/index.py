"""In-memory index en reconciler (pakket 05)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from ordner.config import META_NAAM
from ordner.meta import Meta, MetaFout, bepaal_ocr_status, is_extraheerbaar, lees_meta, schrijf_meta, txt_pad
from ordner.storage import Archief

log = logging.getLogger(__name__)

_DATUMPREFIX = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(.*)$")
_JAARMAP = "[0-9][0-9][0-9][0-9]"
_FALLBACK_TITEL = "document"

QueueFn = Callable[[Path, str], None]


# --- index ----------------------------------------------------------------


@dataclass
class DocEntry:
    rel: str
    map: Path
    meta: Meta
    teksten: dict[str, str]  # bestandsnaam -> inhoud van de .txt; alleen voor bestanden mét .txt


class Index:
    """In-memory overzicht van alle documenten; key is het relatieve pad."""

    def __init__(self) -> None:
        self.docs: dict[str, DocEntry] = {}

    def herlaad(self, archief: Archief, map: Path) -> DocEntry:
        """Leest meta.md en alle .txt's van de map opnieuw in."""
        meta = lees_meta(map)
        teksten: dict[str, str] = {}
        for naam in meta.bestanden:
            txt = txt_pad(map / naam)
            if txt.exists():
                teksten[naam] = txt.read_text(encoding="utf-8", errors="replace")
        entry = DocEntry(rel=archief.relatief(map), map=map, meta=meta, teksten=teksten)
        self.docs[entry.rel] = entry
        return entry

    def verwijder(self, rel: str) -> None:
        self.docs.pop(rel, None)

    def alle(self) -> list[DocEntry]:
        """Documentdatum desc, daarna rel desc."""
        return sorted(self.docs.values(), key=lambda d: (d.meta.documentdatum, d.rel), reverse=True)

    def tellingen(self) -> dict[str, int]:
        tel = {"totaal": len(self.docs), "pending": 0, "done": 0, "failed": 0}
        for entry in self.docs.values():
            tel[entry.meta.ocr] += 1
        return tel


def bouw_index(archief: Archief) -> Index:
    index = Index()
    for map in archief.documentmappen():
        try:
            index.herlaad(archief, map)
        except MetaFout as e:
            log.warning("document overgeslagen: %s", e)
    return index


# --- reconciler -----------------------------------------------------------


@dataclass
class ReconcileRapport:
    documenten: int = 0
    gesynchroniseerd: int = 0
    gequeued: int = 0
    meta_aangemaakt: int = 0
    inbox_verwerkt: int = 0


def _titel_en_datum_uit_mapnaam(naam: str) -> tuple[str, date]:
    """Mapnaam 'JJJJ-MM-DD_slug' -> ('slug met spaties', datum); zonder geldig prefix -> vandaag."""
    datum = date.today()
    rest = naam
    m = _DATUMPREFIX.match(naam)
    if m:
        try:
            datum = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            rest = m.group(4)
        except ValueError:
            log.warning("mapnaam %r heeft een ongeldige datum, gebruik vandaag", naam)
    titel = rest.replace("_", " ").replace("-", " ").strip()
    return titel or _FALLBACK_TITEL, datum


def _werkelijke_bestanden(map: Path, bekend: set[str]) -> list[str]:
    """Gewone bestanden in de map, zonder meta.md, verborgen bestanden en OCR-tekst; gesorteerd.

    Een .txt geldt als OCR-tekst tenzij hij al in meta.bestanden staat (bewust geüpload).
    """
    namen: list[str] = []
    for p in map.iterdir():
        if not p.is_file() or p.name == META_NAAM or p.name.startswith("."):
            continue
        if p.name.endswith(".txt") and p.name not in bekend:
            continue
        namen.append(p.name)
    return sorted(namen)


class Reconciler:
    """Brengt schijf, meta.md en index met elkaar in overeenstemming en ingest de inbox."""

    def __init__(self, archief: Archief, index: Index, queue_fn: QueueFn) -> None:
        self.archief = archief
        self.index = index
        self.queue_fn = queue_fn
        self._inbox_groottes: dict[Path, int] = {}

    def run(self) -> ReconcileRapport:
        """Synchroon; de app roept aan via asyncio.to_thread."""
        rapport = ReconcileRapport()
        rapport.meta_aangemaakt = self._maak_ontbrekende_meta()
        mappen = self.archief.documentmappen()
        for map in mappen:
            self._sync_map(map, rapport)
        bestaand = {self.archief.relatief(map) for map in mappen}
        for rel in list(self.index.docs):
            if rel not in bestaand:
                self.index.verwijder(rel)
                log.info("uit index verwijderd: %s", rel)
        rapport.inbox_verwerkt = len(self.verwerk_inbox())
        log.info("reconcile: %s", rapport)
        return rapport

    # --- stap A ---

    def _maak_ontbrekende_meta(self) -> int:
        aantal = 0
        for map in sorted(self.archief.root.glob(f"{_JAARMAP}/*/")):
            if not map.is_dir() or map.name.startswith(("_", ".")) or (map / META_NAAM).exists():
                continue
            if not any(p.is_file() and not p.name.startswith(".") for p in map.iterdir()):
                continue
            titel, datum = _titel_en_datum_uit_mapnaam(map.name)
            uploaddatum = datetime.fromtimestamp(map.stat().st_mtime).replace(second=0, microsecond=0)
            meta = Meta(titel=titel, documentdatum=datum, uploaddatum=uploaddatum, bestanden=[], ocr="done")
            try:
                schrijf_meta(map, meta)
            except OSError as e:
                log.warning("meta.md aanmaken mislukt voor %s: %s", map, e)
                continue
            log.info("meta.md aangemaakt: %s", self.archief.relatief(map))
            aantal += 1
        return aantal

    # --- stap B ---

    def _sync_map(self, map: Path, rapport: ReconcileRapport) -> None:
        try:
            meta = lees_meta(map)
        except MetaFout as e:
            log.warning("document overgeslagen: %s", e)
            return
        gewijzigd = False

        werkelijk = _werkelijke_bestanden(map, set(meta.bestanden))
        if set(meta.bestanden) != set(werkelijk):
            meta.bestanden = [n for n in meta.bestanden if n in werkelijk] + [
                n for n in werkelijk if n not in meta.bestanden
            ]
            gewijzigd = True
            rapport.gesynchroniseerd += 1

        nieuw = bepaal_ocr_status(map, meta)
        if nieuw != meta.ocr:
            meta.ocr = nieuw
            gewijzigd = True

        if gewijzigd:
            schrijf_meta(map, meta)
            log.info("meta.md bijgewerkt: %s", self.archief.relatief(map))

        if meta.ocr == "pending":
            for naam in meta.bestanden:
                if is_extraheerbaar(naam) and not txt_pad(map / naam).exists():
                    self.queue_fn(map, naam)
                    rapport.gequeued += 1

        self.index.herlaad(self.archief, map)
        rapport.documenten += 1

    # --- stap D ---

    def verwerk_inbox(self) -> list[Path]:
        """Ingest inboxbestanden waarvan de grootte in twee opeenvolgende polls gelijk is."""
        aangemaakt: list[Path] = []
        kandidaten = sorted(
            p for p in self.archief.inbox_dir.iterdir() if p.is_file() and not p.name.startswith(".")
        )
        for pad in kandidaten:
            try:
                grootte = pad.stat().st_size
                if self._inbox_groottes.get(pad) != grootte:
                    self._inbox_groottes[pad] = grootte
                    continue
                aangemaakt.append(self._ingest(pad))
            except Exception:  # noqa: BLE001 - één kapot bestand mag de rest niet blokkeren
                log.exception("inbox-bestand overgeslagen: %s", pad.name)
            self._inbox_groottes.pop(pad, None)

        for pad in list(self._inbox_groottes):
            if not pad.exists():
                del self._inbox_groottes[pad]
        return aangemaakt

    def _ingest(self, pad: Path) -> Path:
        titel = pad.stem.replace("_", " ").replace("-", " ").strip() or _FALLBACK_TITEL
        doc = self.archief.maak_document(titel, date.today())
        naam = self.archief.voeg_bestand_toe(doc, pad.name, pad.read_bytes())
        pad.unlink()
        if is_extraheerbaar(naam):
            self.queue_fn(doc, naam)
        self.index.herlaad(self.archief, doc)
        log.info("inbox verwerkt: %s -> %s", pad.name, self.archief.relatief(doc))
        return doc
