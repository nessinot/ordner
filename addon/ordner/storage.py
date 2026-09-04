"""Archief op schijf: mappen, bestanden, prullenbak (pakket 03)."""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path

from ordner.config import INBOX_DIR, META_NAAM, TRASH_DIR
from ordner.meta import Meta, bepaal_ocr_status, is_extraheerbaar, lees_meta, schrijf_meta
from ordner.slug import maak_slug

log = logging.getLogger(__name__)

_ONVEILIG = re.compile(r"[^A-Za-z0-9._ -]")
_JAAR = re.compile(r"[0-9]{4}")
_FALLBACK_NAAM = "bestand"
_TMP_PREFIX = ".tmp-"


class OngeldigPad(Exception):
    """Padcomponent is onveilig, ligt buiten het archief of bestaat niet."""


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
        )
        schrijf_meta(doc, meta)
        log.info("document aangemaakt: %s", self.relatief(doc))
        return doc

    def voeg_bestand_toe(self, doc: Path, naam: str, data: bytes) -> str:
        """Slaat data op onder een gesaneerde, unieke naam en werkt meta.md bij."""
        naam = _vrije_naam(doc, _saneer_naam(naam))
        tmp = doc / (_TMP_PREFIX + naam)
        tmp.write_bytes(data)
        os.replace(tmp, doc / naam)

        meta = lees_meta(doc)
        if naam not in meta.bestanden:
            meta.bestanden.append(naam)
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

    def documentmappen(self) -> list[Path]:
        """Alle root/JJJJ/*/ met meta.md, gesorteerd; '_'- en '.'-mappen overgeslagen."""
        return sorted(
            p.parent
            for p in self.root.glob(f"[0-9][0-9][0-9][0-9]/*/{META_NAAM}")
            if not p.parent.name.startswith(("_", "."))
        )

    # --- paden ------------------------------------------------------------

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
