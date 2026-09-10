"""Archief op schijf: mappen, bestanden, prullenbak (pakket 03; pakket 19: prullenbak kijken en legen; pakket 20: terugzetten)."""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ordner.config import INBOX_DIR, META_NAAM, TRASH_DIR
from ordner.dubbel import sha256_van
from ordner.meta import DatumBron, Meta, MetaFout, bepaal_ocr_status, is_extraheerbaar, lees_meta, schrijf_meta
from ordner.slug import maak_slug

log = logging.getLogger(__name__)

_ONVEILIG = re.compile(r"[^A-Za-z0-9._ -]")
_JAAR = re.compile(r"[0-9]{4}")
_FALLBACK_NAAM = "bestand"
_TMP_PREFIX = ".tmp-"
_PRULLENBAK_SUFFIX = re.compile(r"_[0-9]{8}-[0-9]{6}$")  # conflict-tijdstempel van naar_prullenbak
_JAARPREFIX = re.compile(r"^[0-9]{4}-")


class OngeldigPad(Exception):
    """Padcomponent is onveilig, ligt buiten het archief of bestaat niet."""


@dataclass(frozen=True)
class PrullenbakItem:
    """Eén map of los bestand direct in `_prullenbak/` (pakket 19)."""

    naam: str  # naam van de map of het losse bestand in _prullenbak/
    is_map: bool
    titel: str  # meta.titel; zonder leesbare meta.md de naam zelf
    documentdatum: date | None  # meta.documentdatum; None zonder leesbare meta.md of bij een los bestand
    bestanden: int  # len(meta.bestanden), anders gewone bestanden in de map (geen meta.md, "."-namen, .txt); los bestand -> 1
    grootte: int  # bytes, recursief; 0 bij met_grootte=False


@dataclass(frozen=True)
class PrullenbakDocument:
    """Eén weggegooide documentmap, voor de kijkpagina en Terugzetten (pakket 20)."""

    naam: str
    map: Path
    meta: Meta | None  # None zonder leesbare meta.md
    bestanden: list[str]  # meta.bestanden, anders gewone bestanden in de map
    jaar: str | None  # jaarmap waar Terugzetten hem neerzet; None -> niet terugzetbaar


def _map_grootte(map: Path) -> int:
    """Som van de bestandsgroottes onder `map`, recursief; symlinks niet gevolgd, OSError per bestand overgeslagen."""
    totaal = 0
    for dirpath, _dirnames, filenames in os.walk(map):
        for naam in filenames:
            try:
                totaal += os.lstat(os.path.join(dirpath, naam)).st_size
            except OSError:
                continue
    return totaal


def _gewone_bestanden(map: Path) -> list[str]:
    """Bestandsnamen direct in `map` zonder meta.md, "."-namen en .txt, gesorteerd (fallback zonder leesbare meta.md)."""
    namen: list[str] = []
    try:
        for p in map.iterdir():
            try:
                if p.is_file() and not p.name.startswith(".") and p.name != META_NAAM and p.suffix.lower() != ".txt":
                    namen.append(p.name)
            except OSError:
                continue
    except OSError:
        pass
    return sorted(namen)


def _tel_gewone_bestanden(map: Path) -> int:
    """Aantal gewone bestanden in `map` (zie `_gewone_bestanden`)."""
    return len(_gewone_bestanden(map))


def _saneer_naam(naam: str) -> str:
    """Basisnaam zonder mapdelen, alleen veilige tekens, nooit leeg of verborgen."""
    naam = naam.replace("\\", "/").rsplit("/", 1)[-1]
    naam = _ONVEILIG.sub("_", naam).strip()
    if naam.startswith("."):
        naam = "_" + naam[1:]
    if not naam:
        naam = _FALLBACK_NAAM
    if naam.lower() == META_NAAM:
        naam = "meta_1.md"
    return naam


def _botst(doc: Path, naam: str) -> bool:
    """Bestaat de naam al, of zou hij een OCR-tekstbestand van een ander bestand overschrijven?"""
    if (doc / naam).exists():
        return True
    return naam.endswith(".txt") and (doc / naam[:-4]).is_file()


def _vrije_naam(doc: Path, naam: str) -> str:
    if not _botst(doc, naam):
        return naam
    stam, ext = Path(naam).stem, Path(naam).suffix
    n = 2
    while _botst(doc, f"{stam}_{n}{ext}"):
        n += 1
    return f"{stam}_{n}{ext}"


def _controleer_component(waarde: str) -> None:
    if not waarde or waarde in (".", "..") or "/" in waarde or "\\" in waarde:
        raise OngeldigPad(f"ongeldige padcomponent: {waarde!r}")


class Archief:
    """Toegang tot de archiefmap op schijf."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.inbox_dir = self.root / INBOX_DIR
        self.trash_dir = self.root / TRASH_DIR
        for map in (self.root, self.inbox_dir, self.trash_dir):
            map.mkdir(parents=True, exist_ok=True)

    # --- documenten -------------------------------------------------------

    def maak_document(
        self,
        titel: str,
        documentdatum: date,
        omschrijving: str = "",
        tags: list[str] | None = None,
        nu: datetime | None = None,
        datumbron: DatumBron = "gebruiker",
    ) -> Path:
        """Maakt JJJJ/JJJJ-MM-DD_slug[_N] met meta.md aan en geeft de absolute map terug."""
        jaarmap = self.root / str(documentdatum.year)
        basis = f"{documentdatum:%Y-%m-%d}_{maak_slug(titel)}"
        doc = jaarmap / basis
        n = 2
        while doc.exists():
            doc = jaarmap / f"{basis}_{n}"
            n += 1
        doc.mkdir(parents=True)
        meta = Meta(
            titel=titel.strip(),
            documentdatum=documentdatum,
            uploaddatum=(nu or datetime.now()).replace(second=0, microsecond=0),
            omschrijving=omschrijving,
            tags=list(tags or []),
            bestanden=[],
            ocr="done",
            datumbron=datumbron,
        )
        schrijf_meta(doc, meta)
        log.info("document aangemaakt: %s", self.relatief(doc))
        return doc

    def voeg_bestand_toe(self, doc: Path, naam: str, data: bytes) -> str:
        """Slaat data op onder een gesaneerde, unieke naam en werkt meta.md bij (bestanden, sha256, ocr).

        Weigert nooit een dubbel bestand; dat is beleid van de upload en de inbox (pakket 16).
        """
        naam = _vrije_naam(doc, _saneer_naam(naam))
        tmp = doc / (_TMP_PREFIX + naam)
        tmp.write_bytes(data)
        os.replace(tmp, doc / naam)

        meta = lees_meta(doc)
        if naam not in meta.bestanden:
            meta.bestanden.append(naam)
        meta.sha256[naam] = sha256_van(data)
        if meta.ocr == "failed" and is_extraheerbaar(naam):
            meta.ocr = "done"  # nieuw bestand verdient een poging
        meta.ocr = bepaal_ocr_status(doc, meta)
        schrijf_meta(doc, meta)
        return naam

    def naar_prullenbak(self, doc: Path) -> Path:
        """Verplaatst de documentmap naar _prullenbak; lege jaarmap blijft staan."""
        doel = self.trash_dir / doc.name
        if doel.exists():
            doel = self.trash_dir / f"{doc.name}_{datetime.now():%Y%m%d-%H%M%S}"
        shutil.move(str(doc), str(doel))
        log.info("naar prullenbak: %s -> %s", doc.name, doel.name)
        return doel

    # --- prullenbak (pakket 19) -------------------------------------------

    def prullenbak_pad(self, naam: str) -> Path:
        """`_prullenbak/<naam>` voor een naam uit een formulier; de enige verdediging vóór `rmtree`.

        Raises OngeldigPad bij een lege naam, `.`/`..`, een pad-scheider, een naam die met `.` begint,
        een resolved pad dat niet direct onder `trash_dir` ligt, of een item dat niet bestaat. Een symlink
        wordt niet gevolgd: het pad is de link zelf (die ligt per definitie in de prullenbak) en
        `verwijder_definitief` haalt alleen de link weg.
        """
        _controleer_component(naam)
        if naam.startswith(".") or Path(naam).name != naam:
            raise OngeldigPad(f"ongeldige prullenbaknaam: {naam!r}")
        pad = self.trash_dir / naam
        if pad.is_symlink():
            return pad
        echt = pad.resolve()
        if echt.parent != self.trash_dir or echt.name != naam:
            raise OngeldigPad(f"pad ligt niet direct in de prullenbak: {echt}")
        if not echt.exists():
            raise OngeldigPad(f"pad bestaat niet: {echt}")
        return echt

    def prullenbak_inhoud(self, met_grootte: bool = True) -> list[PrullenbakItem]:
        """Mappen en losse bestanden direct in `_prullenbak/` zonder "."-prefix, op naam aflopend.

        Titel, datum en bestandsaantal uit `meta.md` (MetaFout/OSError -> naam als titel, geen datum, bestanden
        geteld). `met_grootte=False` slaat de recursieve walk over (grootte 0): goedkoop genoeg voor de teller
        op de event loop. Een item dat onder ons verdwijnt (OSError) wordt overgeslagen; nooit een fout.
        """
        try:
            paden = sorted(self.trash_dir.iterdir(), key=lambda p: p.name, reverse=True)
        except OSError:
            return []
        items: list[PrullenbakItem] = []
        for p in paden:
            if p.name.startswith("."):
                continue
            try:
                if p.is_symlink() or not p.is_dir():
                    # los bestand of symlink (nooit gevolgd, ook niet voor de grootte)
                    grootte = p.lstat().st_size if met_grootte else 0
                    items.append(PrullenbakItem(p.name, False, p.name, None, 1, grootte))
                    continue
                try:
                    meta = lees_meta(p)
                    titel, datum, bestanden = meta.titel, meta.documentdatum, len(meta.bestanden)
                except (MetaFout, OSError):
                    titel, datum, bestanden = p.name, None, _tel_gewone_bestanden(p)
                grootte = _map_grootte(p) if met_grootte else 0
                items.append(PrullenbakItem(p.name, True, titel, datum, bestanden, grootte))
            except OSError:
                continue
        return items

    def verwijder_definitief(self, naam: str) -> None:
        """Haalt één item onomkeerbaar uit de prullenbak: symlink of bestand -> unlink, map -> rmtree.

        Alleen via `prullenbak_pad`; een `OSError` (bv. alleen-lezen bestand op Windows) gaat door naar de aanroeper.
        """
        pad = self.prullenbak_pad(naam)
        if pad.is_symlink() or pad.is_file():
            pad.unlink()
        else:
            shutil.rmtree(pad)
        log.info("definitief verwijderd uit de prullenbak: %s", naam)

    def leeg_prullenbak(self) -> tuple[int, int]:
        """Verwijdert alle items uit `prullenbak_inhoud()` één voor één; geeft (verwijderd, mislukt) terug.

        Een `OSError` op één item wordt gelogd en de rest gaat door. `trash_dir` zelf blijft bestaan;
        een item dat intussen al weg is (OngeldigPad) telt niet mee.
        """
        verwijderd = mislukt = 0
        for item in self.prullenbak_inhoud(met_grootte=False):
            try:
                self.verwijder_definitief(item.naam)
            except OngeldigPad:
                continue
            except OSError as e:
                log.warning("prullenbak legen: %s kon niet worden verwijderd: %s", item.naam, e)
                mislukt += 1
            else:
                verwijderd += 1
        log.info("prullenbak geleegd: %d verwijderd, %d mislukt", verwijderd, mislukt)
        return verwijderd, mislukt

    # --- prullenbak: kijken in een document en terugzetten (pakket 20) -----

    def prullenbak_document(self, naam: str) -> PrullenbakDocument:
        """Een weggegooide documentmap voor de kijkpagina; via `prullenbak_pad`.

        Raises OngeldigPad als het item geen map is (los bestand of symlink). Zonder leesbare `meta.md`
        is `meta` None en komen de bestanden uit de map zelf.
        """
        pad = self.prullenbak_pad(naam)
        if pad.is_symlink() or not pad.is_dir():
            raise OngeldigPad(f"geen documentmap in de prullenbak: {naam!r}")
        meta: Meta | None
        try:
            meta = lees_meta(pad)
        except (MetaFout, OSError):
            meta = None
        bestanden = list(meta.bestanden) if meta is not None else _gewone_bestanden(pad)
        return PrullenbakDocument(naam, pad, meta, bestanden, self._terugzet_jaar(naam, meta))

    def prullenbak_bestand(self, naam: str, bestand: str) -> Path:
        """Een bestaand bestand direct in `_prullenbak/<naam>/`; raises OngeldigPad bij alles wat daarbuiten wijst."""
        map = self.prullenbak_document(naam).map
        _controleer_component(bestand)
        if bestand.startswith(".") or Path(bestand).name != bestand:
            raise OngeldigPad(f"ongeldige bestandsnaam: {bestand!r}")
        pad = (map / bestand).resolve()
        if pad.parent != map or pad.name != bestand or not pad.is_file():
            raise OngeldigPad(f"bestand niet in de prullenbakmap: {bestand!r}")
        return pad

    def herstel_uit_prullenbak(self, naam: str) -> Path:
        """Verplaatst `_prullenbak/<naam>` terug naar de jaarmap en geeft de nieuwe absolute map terug.

        Het jaar komt uit de mapnaam (`JJJJ-...`), anders uit `meta.documentdatum`; zonder beide OngeldigPad.
        De conflict-tijdstempel `_JJJJMMDD-HHMMSS` van `naar_prullenbak` wordt gestript; bestaat de naam in
        de jaarmap al, dan `_2`, `_3`, ... zoals bij aanmaken. Dubbelen controleert de aanroeper (pakket 16).
        """
        item = self.prullenbak_document(naam)
        if item.jaar is None:
            raise OngeldigPad(f"geen jaar te bepalen voor {naam!r}")
        jaarmap = self.root / item.jaar
        basis = _PRULLENBAK_SUFFIX.sub("", naam) or naam
        doel = jaarmap / basis
        n = 2
        while doel.exists():
            doel = jaarmap / f"{basis}_{n}"
            n += 1
        jaarmap.mkdir(exist_ok=True)
        shutil.move(str(item.map), str(doel))
        log.info("teruggezet uit de prullenbak: %s -> %s", naam, self.relatief(doel))
        return doel

    @staticmethod
    def _terugzet_jaar(naam: str, meta: Meta | None) -> str | None:
        """Jaarmap voor Terugzetten: de eerste vier tekens van `JJJJ-...`, anders het jaar van de documentdatum."""
        if _JAARPREFIX.match(naam):
            return naam[:4]
        if meta is not None:
            return f"{meta.documentdatum.year:04d}"
        return None

    def documentmappen(self) -> list[Path]:
        """Alle root/JJJJ/*/ met meta.md, gesorteerd; '_'- en '.'-mappen overgeslagen."""
        return sorted(
            p.parent
            for p in self.root.glob(f"[0-9][0-9][0-9][0-9]/*/{META_NAAM}")
            if not p.parent.name.startswith(("_", "."))
        )

    # --- paden ------------------------------------------------------------

    def inbox_pad(self, naam: str) -> Path:
        """`_inbox/<naam>` voor een kale bestandsnaam uit een formulier (pakket 17).

        Raises OngeldigPad bij een lege naam, een pad-scheider, `.`/`..` of een naam die met `.`
        begint (verborgen bestanden en de map `.tekst/` horen niet bij de inbox). Het bestand hoeft
        niet te bestaan; dat controleert de aanroeper.
        """
        _controleer_component(naam)
        if naam.startswith(".") or Path(naam).name != naam:
            raise OngeldigPad(f"ongeldige inboxnaam: {naam!r}")
        return self.inbox_dir / naam

    def relatief(self, doc: Path) -> str:
        return doc.relative_to(self.root).as_posix()

    def veilig_pad(self, jaar: str, map: str, naam: str | None = None) -> Path:
        """Bestaand pad binnen root; raises OngeldigPad bij onveilige of onbestaande componenten."""
        for component in (jaar, map) if naam is None else (jaar, map, naam):
            _controleer_component(component)
        if not _JAAR.fullmatch(jaar):
            raise OngeldigPad(f"ongeldig jaar: {jaar!r}")
        pad = self.root / jaar / map
        if naam is not None:
            pad = pad / naam
        pad = pad.resolve()
        if not pad.is_relative_to(self.root):
            raise OngeldigPad(f"pad ligt buiten het archief: {pad}")
        if not pad.exists():
            raise OngeldigPad(f"pad bestaat niet: {pad}")
        return pad
