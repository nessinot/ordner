"""Lezen en schrijven van meta.md (pakket 02)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Literal, get_args

import yaml

from ordner.config import EXTRAHEERBAAR, META_NAAM

log = logging.getLogger(__name__)

OcrStatus = Literal["pending", "done", "failed"]
_OCR_STATUSSEN: tuple[str, ...] = get_args(OcrStatus)

_SCHEIDER = "---"
_TMP_NAAM = ".meta.md.tmp"
_UPLOADDATUM_FORMAAT = "%Y-%m-%dT%H:%M"


class MetaFout(Exception):
    """Ongeldige of ontbrekende meta.md."""


class _Gequoteerd(str):
    """String die altijd met enkele quotes wordt gerenderd (voor uploaddatum)."""


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(
    _Gequoteerd,
    lambda dumper, data: dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="'"),
)


@dataclass
class Meta:
    titel: str
    documentdatum: date
    uploaddatum: datetime  # minuut-precisie, naïef (lokale tijd)
    omschrijving: str = ""
    tags: list[str] = field(default_factory=list)
    bestanden: list[str] = field(default_factory=list)
    ocr: OcrStatus = "done"
    notities: str = ""  # body onder de frontmatter


# --- parsen ---------------------------------------------------------------


def _splits_frontmatter(tekst: str) -> tuple[str, str]:
    """Geeft (frontmatter, notities) terug. Raises MetaFout zonder frontmatter."""
    regels = tekst.replace("\r\n", "\n").split("\n")
    if not regels or regels[0] != _SCHEIDER:
        raise MetaFout("geen frontmatter")
    for i in range(1, len(regels)):
        if regels[i] == _SCHEIDER:
            frontmatter = "\n".join(regels[1:i])
            notities = "\n".join(regels[i + 1 :])
            return frontmatter, notities
    raise MetaFout("geen frontmatter")


def _parse_datum(waarde: Any) -> date:
    if isinstance(waarde, datetime):
        return waarde.date()
    if isinstance(waarde, date):
        return waarde
    if isinstance(waarde, str):
        try:
            return date.fromisoformat(waarde.strip())
        except ValueError as e:
            raise MetaFout(f"ongeldige documentdatum: {waarde!r}") from e
    raise MetaFout(f"ongeldige documentdatum: {waarde!r}")


def _parse_uploaddatum(waarde: Any, documentdatum: date) -> datetime:
    if waarde is None:
        return datetime.combine(documentdatum, time())
    if isinstance(waarde, datetime):
        return waarde.replace(second=0, microsecond=0, tzinfo=None)
    if isinstance(waarde, date):
        return datetime.combine(waarde, time())
    if isinstance(waarde, str):
        try:
            dt = datetime.fromisoformat(waarde.strip())
        except ValueError as e:
            raise MetaFout(f"ongeldige uploaddatum: {waarde!r}") from e
        return dt.replace(second=0, microsecond=0, tzinfo=None)
    raise MetaFout(f"ongeldige uploaddatum: {waarde!r}")


def _parse_lijst(waarde: Any, veld: str) -> list[str]:
    if waarde is None:
        return []
    if isinstance(waarde, str):
        return [waarde]
    if isinstance(waarde, (list, tuple)):
        return [str(x) for x in waarde]
    raise MetaFout(f"{veld} moet een lijst zijn, kreeg {type(waarde).__name__}")


def parse_meta(tekst: str) -> Meta:
    """Parseert de tekst van een meta.md. Raises MetaFout bij ontbrekende frontmatter/titel/datum."""
    frontmatter, notities = _splits_frontmatter(tekst)
    try:
        data = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        raise MetaFout(f"ongeldige YAML in frontmatter: {e}") from e
    if not isinstance(data, dict):
        raise MetaFout("frontmatter is geen mapping")

    titel = data.get("titel")
    if not isinstance(titel, str) or not titel.strip():
        raise MetaFout("titel ontbreekt")
    titel = titel.strip()

    if data.get("documentdatum") is None:
        raise MetaFout("documentdatum ontbreekt")
    documentdatum = _parse_datum(data["documentdatum"])
    uploaddatum = _parse_uploaddatum(data.get("uploaddatum"), documentdatum)

    omschrijving = data.get("omschrijving")
    omschrijving = "" if omschrijving is None else str(omschrijving)

    ocr = data.get("ocr")
    if ocr not in _OCR_STATUSSEN:
        if ocr is not None:
            log.warning("onbekende ocr-status %r, gebruik 'done'", ocr)
        ocr = "done"

    if notities.startswith("\n"):
        notities = notities[1:]

    return Meta(
        titel=titel,
        documentdatum=documentdatum,
        uploaddatum=uploaddatum,
        omschrijving=omschrijving,
        tags=_parse_lijst(data.get("tags"), "tags"),
        bestanden=_parse_lijst(data.get("bestanden"), "bestanden"),
        ocr=ocr,  # type: ignore[arg-type]
        notities=notities,
    )


# --- renderen -------------------------------------------------------------


def render_meta(meta: Meta) -> str:
    """Rendert een Meta naar de tekst van meta.md (frontmatter + notities)."""
    data: dict[str, Any] = {
        "titel": meta.titel,
        "omschrijving": meta.omschrijving,
        "documentdatum": meta.documentdatum,
        "uploaddatum": _Gequoteerd(meta.uploaddatum.strftime(_UPLOADDATUM_FORMAAT)),
        "tags": list(meta.tags),
        "bestanden": list(meta.bestanden),
        "ocr": meta.ocr,
    }
    yaml_tekst = yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=None,
        width=1000,
    )
    return f"{_SCHEIDER}\n{yaml_tekst}{_SCHEIDER}\n{meta.notities}"


# --- bestanden ------------------------------------------------------------


def lees_meta(map: Path) -> Meta:
    """Leest map/meta.md. Raises MetaFout als het bestand ontbreekt of ongeldig is."""
    pad = map / META_NAAM
    try:
        tekst = pad.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise MetaFout(f"{pad} bestaat niet") from e
    except OSError as e:
        raise MetaFout(f"{pad} kan niet gelezen worden: {e}") from e
    try:
        return parse_meta(tekst)
    except MetaFout as e:
        raise MetaFout(f"{pad}: {e}") from e


def schrijf_meta(map: Path, meta: Meta) -> None:
    """Schrijft map/meta.md atomic via een tempbestand in dezelfde map."""
    tmp = map / _TMP_NAAM
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_meta(meta))
    os.replace(tmp, map / META_NAAM)


# --- hulpfuncties ---------------------------------------------------------


def txt_pad(bestand: Path) -> Path:
    """Pad van de OCR-tekst naast een bronbestand: factuur.pdf -> factuur.pdf.txt."""
    return bestand.with_name(bestand.name + ".txt")


def is_extraheerbaar(naam: str) -> bool:
    return Path(naam).suffix.lower() in EXTRAHEERBAAR


def bepaal_ocr_status(map: Path, meta: Meta) -> OcrStatus:
    """'failed' blijft 'failed'; anders 'pending' als een extraheerbaar bestand geen .txt heeft, anders 'done'."""
    if meta.ocr == "failed":
        return "failed"
    for naam in meta.bestanden:
        if is_extraheerbaar(naam) and not txt_pad(map / naam).exists():
            return "pending"
    return "done"
