"""In-memory index en reconciler (pakket 05; sha256-opzoektabel en dubbelen sinds pakket 16)."""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from ordner.config import INBOX_DUBBEL_DIR, META_NAAM
from ordner.dubbel import sha256_van_bestand
from ordner.ingest import LeesTekst, lees_vooraf, maak_document_uit_voorbereid
from ordner.meta import Meta, MetaFout, bepaal_ocr_status, is_extraheerbaar, lees_meta, schrijf_meta, txt_pad
from ordner.storage import Archief
from ordner.suggestie import stel_voor

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
        self._hashes: dict[str, tuple[str, str]] = {}  # sha256 -> (rel, bestandsnaam); pakket 16

    def herlaad(self, archief: Archief, map: Path) -> DocEntry:
        """Leest meta.md en alle .txt's van de map opnieuw in."""
        meta = lees_meta(map)
        teksten: dict[str, str] = {}
        for naam in meta.bestanden:
            txt = txt_pad(map / naam)
            if txt.exists():
                teksten[naam] = txt.read_text(encoding="utf-8", errors="replace")
        entry = DocEntry(rel=archief.relatief(map), map=map, meta=meta, teksten=teksten)
        self._vergeet_hashes(entry.rel)
        self.docs[entry.rel] = entry
        for naam, h in meta.sha256.items():
            self._hashes[h] = (entry.rel, naam)  # bij gelijke bestanden in twee documenten wint de laatst geladen
        return entry

    def verwijder(self, rel: str) -> None:
        self._vergeet_hashes(rel)
        self.docs.pop(rel, None)

    def zoek_hash(self, sha256: str) -> tuple[DocEntry, str] | None:
        """Het document en de bestandsnaam waar een bestand met deze hash al staat; None als onbekend."""
        treffer = self._hashes.get(sha256)
        if treffer is None:
            return None
        entry = self.docs.get(treffer[0])
        return None if entry is None else (entry, treffer[1])

    def _vergeet_hashes(self, rel: str) -> None:
        oud = self.docs.get(rel)
        if oud is None:
            return
        for h in oud.meta.sha256.values():
            if self._hashes.get(h, ("", ""))[0] == rel:
                del self._hashes[h]

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
    gehasht: int = 0  # bestanden waarvoor deze ronde een sha256 is berekend (pakket 16)


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

    def __init__(
        self, archief: Archief, index: Index, queue_fn: QueueFn, lees_tekst: LeesTekst | None = None
    ) -> None:
        self.archief = archief
        self.index = index
        self.queue_fn = queue_fn
        self.lees_tekst = lees_tekst  # voor de inbox: tekst vooraf lezen om de documentdatum te bepalen
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

        # sha256 (pakket 16): verweesde hashes weg, ontbrekende berekenen; zo vult een bestaand archief zichzelf
        for naam in [n for n in meta.sha256 if n not in meta.bestanden]:
            del meta.sha256[naam]
            gewijzigd = True
        for naam in meta.bestanden:
            if naam in meta.sha256:
                continue
            try:
                meta.sha256[naam] = sha256_van_bestand(map / naam)
            except OSError as e:
                log.warning("hash berekenen mislukt voor %s/%s: %s", self.archief.relatief(map), naam, e)
                continue
            gewijzigd = True
            rapport.gehasht += 1

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
        """Ingest inboxbestanden waarvan de grootte in twee opeenvolgende polls gelijk is.

        Een bestand dat al in het archief staat (zelfde sha256) gaat naar `_inbox/_dubbel/` (pakket 16).
        """
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
                if self._is_dubbel(pad):
                    continue
                aangemaakt.append(self._ingest(pad))
            except Exception:  # noqa: BLE001 - één kapot bestand mag de rest niet blokkeren
                log.exception("inbox-bestand overgeslagen: %s", pad.name)
            self._inbox_groottes.pop(pad, None)

        for pad in list(self._inbox_groottes):
            if not pad.exists():
                del self._inbox_groottes[pad]
        return aangemaakt

    def _is_dubbel(self, pad: Path) -> bool:
        """Staat dit inboxbestand al in het archief? Dan naar `_inbox/_dubbel/` en True."""
        treffer = self.index.zoek_hash(sha256_van_bestand(pad))
        if treffer is None:
            return False
        entry, bestand = treffer
        doelmap = self.archief.inbox_dir / INBOX_DUBBEL_DIR
        doelmap.mkdir(exist_ok=True)
        doel = doelmap / pad.name
        if doel.exists():
            doel = doelmap / f"{pad.name}_{datetime.now():%Y%m%d-%H%M%S}"
        shutil.move(str(pad), str(doel))
        log.warning(
            "inbox: %s staat al in het archief als %s/%s (%r); verplaatst naar %s/%s",
            pad.name, entry.rel, bestand, entry.meta.titel, INBOX_DUBBEL_DIR, doel.name,
        )
        return True

    def _ingest(self, pad: Path) -> Path:
        """Inboxbestand -> document: tekst vooraf lezen, titel en tags voorstellen (pakket 15a), daarna aanmaken."""
        vb = lees_vooraf([(pad.name, pad.read_bytes())], documentdatum=None, lees_tekst=self.lees_tekst)
        bekende_titels = {e.meta.titel for e in self.index.alle()}
        suggestie = stel_voor(vb.tekst, bekende_titels)
        titel = suggestie.titel or pad.stem.replace("_", " ").replace("-", " ").strip() or _FALLBACK_TITEL
        doc = maak_document_uit_voorbereid(self.archief, titel, vb, tags=suggestie.tags, queue_fn=self.queue_fn)
        pad.unlink()
        self.index.herlaad(self.archief, doc)
        log.info(
            "inbox verwerkt: %s -> %s (titel uit %s, tags %s)",
            pad.name,
            self.archief.relatief(doc),
            suggestie.titelbron if suggestie.titel else "bestandsnaam",
            suggestie.tags,
        )
        return doc
