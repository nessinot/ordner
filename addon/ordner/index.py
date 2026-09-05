"""In-memory index en reconciler (pakket 05; sha256-opzoektabel en dubbelen sinds pakket 16; inbox wacht op een titel sinds pakket 17)."""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from ordner.config import INBOX_DUBBEL_DIR, INBOX_RESERVERING, INBOX_TEKST_DIR, META_NAAM
from ordner.dubbel import sha256_van_bestand
from ordner.ingest import LeesTekst, Voorbereid, maak_document_uit_voorbereid, voorbereid_uit_teksten
from ordner.meta import (
    Meta,
    MetaFout,
    bepaal_ocr_status,
    is_extraheerbaar,
    lees_meta,
    schrijf_meta,
    schrijf_txt,
    txt_pad,
)
from ordner.storage import Archief
from ordner.suggestie import Suggestie, stel_voor

log = logging.getLogger(__name__)

_DATUMPREFIX = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(.*)$")
_JAARMAP = "[0-9][0-9][0-9][0-9]"
_FALLBACK_TITEL = "document"  # alleen nog voor meta.md uit een mapnaam zonder slug (stap A)

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
    inbox_wachtend: int = 0  # inboxbestanden die na deze ronde op een titel wachten (pakket 17)


@dataclass(frozen=True)
class Wachtend:
    """Een inboxbestand zonder herkende afzender dat op een titel van de gebruiker wacht (pakket 17)."""

    naam: str
    grootte: int
    sinds: datetime  # mtime van het bestand


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
        # pakket 17: per wachtend bestand de archieftitels waartegen het voor het laatst is beoordeeld
        # (gelijke verzameling -> niet opnieuw beoordelen), en de reserveringen van de inboxpagina
        # (naam -> verloopt op). Beide alleen in het geheugen; de gelezen tekst staat in `_inbox/.tekst/`.
        self._beoordeeld: dict[str, frozenset[str]] = {}
        self._reserveringen: dict[str, datetime] = {}

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
        rapport.inbox_wachtend = len(self.wachtend())
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

    # --- stap D: inbox ---

    def verwerk_inbox(self) -> list[Path]:
        """Ingest inboxbestanden waarvan de grootte in twee opeenvolgende polls gelijk is.

        Een bestand dat al in het archief staat (zelfde sha256) gaat naar `_inbox/_dubbel/` (pakket 16).
        Levert de tekst geen afzender op, dan blijft het bestand wachten (pakket 17): de gelezen tekst
        staat in `_inbox/.tekst/<naam>.txt` zodat er maar één keer OCR draait, en het bestand wordt pas
        opnieuw beoordeeld als de verzameling archieftitels veranderd is. Gereserveerde bestanden
        (iemand geeft er via de inboxpagina een titel aan) worden overgeslagen.
        """
        aangemaakt: list[Path] = []
        kandidaten = sorted(
            p for p in self.archief.inbox_dir.iterdir() if p.is_file() and not p.name.startswith(".")
        )
        titels = self._titels()
        for pad in kandidaten:
            naam = pad.name
            if self._is_gereserveerd(naam):
                continue
            try:
                grootte = pad.stat().st_size
                if self._inbox_groottes.get(pad) != grootte:
                    self._inbox_groottes[pad] = grootte
                    self._beoordeeld.pop(naam, None)  # nieuwe of gewijzigde inhoud: opnieuw beoordelen
                    continue
                if self._beoordeeld.get(naam) == titels:
                    continue  # wacht al, en er is geen titel bijgekomen: niets te doen (goedkoop)
                if self._is_dubbel(pad):
                    self._vergeet(pad)
                    continue
                tekst = self._tekst_van(pad)
                suggestie = stel_voor(tekst, titels)
                if not suggestie.titel:
                    if naam not in self._beoordeeld:
                        log.info("inbox: %s wacht op een titel (geen afzender in de tekst)", naam)
                    self._beoordeeld[naam] = titels
                    continue
                aangemaakt.append(self._ingest(pad, tekst, suggestie))
                self._vergeet(pad)
                titels = self._titels()  # de nieuwe titel telt direct mee voor de volgende bestanden
            except Exception:  # noqa: BLE001 - één kapot bestand mag de rest niet blokkeren
                log.exception("inbox-bestand overgeslagen: %s", naam)
                self._vergeet(pad)

        for pad in list(self._inbox_groottes):
            if not pad.exists():
                self._vergeet(pad)
        self._ruim_sidecars_op()
        return aangemaakt

    def wachtend(self) -> list[Wachtend]:
        """Beoordeelde inboxbestanden zonder titel die niet gereserveerd zijn; op naam gesorteerd."""
        lijst: list[Wachtend] = []
        for naam in sorted(list(self._beoordeeld)):  # kopie: de poll-thread wijzigt het dict
            if self._is_gereserveerd(naam):
                continue
            try:
                st = (self.archief.inbox_dir / naam).stat()
            except OSError:
                continue
            lijst.append(Wachtend(naam, st.st_size, datetime.fromtimestamp(st.st_mtime).replace(microsecond=0)))
        return lijst

    def bereid_inbox_voor(self, naam: str) -> tuple[Voorbereid, Suggestie]:
        """Bestand en sidecar -> `Voorbereid` en `Suggestie` voor scherm 2 van de upload (leest zo nodig de tekst).

        Raises FileNotFoundError als het bestand niet (meer) in de inbox ligt.
        """
        pad = self.archief.inbox_pad(naam)
        if not pad.is_file():
            raise FileNotFoundError(str(pad))
        tekst = self._tekst_van(pad)
        vb = voorbereid_uit_teksten([(naam, pad.read_bytes())], {0: tekst} if tekst else {})
        return vb, stel_voor(tekst, self._titels())

    def reserveer(self, naam: str) -> None:
        """Houdt het bestand buiten de poll tot `geef_vrij`, `verwijder_uit_inbox` of het verlopen van de reservering."""
        self._reserveringen[naam] = datetime.now() + INBOX_RESERVERING

    def geef_vrij(self, naam: str) -> None:
        self._reserveringen.pop(naam, None)

    def verwijder_uit_inbox(self, naam: str) -> None:
        """Bestand en sidecar weg (missing_ok) en de reservering vrijgeven; na opname via de inboxpagina."""
        pad = self.archief.inbox_pad(naam)
        pad.unlink(missing_ok=True)
        self._sidecar(pad).unlink(missing_ok=True)
        self._vergeet(pad)

    def _titels(self) -> frozenset[str]:
        return frozenset(e.meta.titel for e in self.index.alle())

    def _is_gereserveerd(self, naam: str) -> bool:
        verloopt = self._reserveringen.get(naam)
        if verloopt is None:
            return False
        if verloopt <= datetime.now():
            self._reserveringen.pop(naam, None)
            return False
        return True

    def _vergeet(self, pad: Path) -> None:
        """Alle geheugenstaat van een inboxbestand weg (opgenomen, verplaatst, verdwenen)."""
        self._inbox_groottes.pop(pad, None)
        self._beoordeeld.pop(pad.name, None)
        self._reserveringen.pop(pad.name, None)

    def _sidecar(self, pad: Path) -> Path:
        return self.archief.inbox_dir / INBOX_TEKST_DIR / (pad.name + ".txt")

    def _tekst_van(self, pad: Path) -> str:
        """De tekst van een inboxbestand: uit de sidecar als die actueel is, anders lezen en de sidecar schrijven.

        Lege tekst betekent: niet extraheerbaar, geen tekstlezer, of extractie mislukt. Ook dan wordt
        de sidecar geschreven, zodat er niet elke poll opnieuw ge-OCR'd wordt; bij opname gaat zo'n
        bestand naar de OCR-queue.
        """
        sidecar = self._sidecar(pad)
        try:
            if sidecar.stat().st_mtime >= pad.stat().st_mtime:
                return sidecar.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        tekst = ""
        if self.lees_tekst is not None and is_extraheerbaar(pad.name):
            tekst = self.lees_tekst(pad) or ""
        sidecar.parent.mkdir(exist_ok=True)
        schrijf_txt(sidecar.parent / pad.name, tekst)
        return tekst

    def _ruim_sidecars_op(self) -> None:
        """Sidecars zonder inboxbestand weg (bestand opgenomen, verplaatst of door de gebruiker verwijderd)."""
        map = self.archief.inbox_dir / INBOX_TEKST_DIR
        if not map.is_dir():
            return
        for sidecar in map.glob("*.txt"):
            if not (self.archief.inbox_dir / sidecar.name[:-4]).is_file():
                sidecar.unlink(missing_ok=True)

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

    def _ingest(self, pad: Path, tekst: str, suggestie: Suggestie) -> Path:
        """Inboxbestand met herkende titel -> document; bestand en sidecar weg, index bijgewerkt."""
        vb = voorbereid_uit_teksten([(pad.name, pad.read_bytes())], {0: tekst} if tekst else {})
        doc = maak_document_uit_voorbereid(self.archief, suggestie.titel, vb, tags=suggestie.tags, queue_fn=self.queue_fn)
        pad.unlink()
        self._sidecar(pad).unlink(missing_ok=True)
        self.index.herlaad(self.archief, doc)
        log.info(
            "inbox verwerkt: %s -> %s (titel uit %s, tags %s)",
            pad.name, self.archief.relatief(doc), suggestie.titelbron, suggestie.tags,
        )
        return doc
