"""Documentdatum uit de gelezen tekst halen (pakket 14, kolomlayout in 0.6.0).

Zoekt per sleutelwoord, in prioriteitsvolgorde, eerst naar een datum die direct achter dat
woord op dezelfde regel staat (alleen spaties en een optionele dubbele punt ertussen), en
daarna naar een datum in dezelfde kolom op de eerstvolgende niet-lege regel (label boven
waarde, zoals `pdftotext -layout` tabellen weergeeft). Pure functies, geen I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MIN_JAAR = 1990
_MAX_TUSSENRUIMTE = 60  # tekens tussen sleutelwoord en datum (pdftotext -layout kan brede kolommen geven)
_MAX_KOLOMAFSTAND = 20  # kolomlayout: max. afstand tussen het tekenbereik van het label en dat van de datum eronder

# (naam, patroon) in prioriteitsvolgorde; `\s?` staat een spatie toe ("factuur datum").
_SLEUTELWOORDEN: tuple[tuple[str, str], ...] = (
    ("factuurdatum", r"factuur\s?datum"),
    ("notadatum", r"nota\s?datum"),
    ("orderdatum", r"order\s?datum"),
    ("dagtekening", r"dagtekening"),
    ("datum", r"datum"),
)
# Letter-lookarounds i.p.v. \b: "Vervaldatum" en "Betaaldatum" mogen "datum" niet matchen.
_SLEUTEL_RE = [(naam, re.compile(rf"(?<![a-z])(?:{patroon})(?![a-z])", re.I)) for naam, patroon in _SLEUTELWOORDEN]

_MAANDEN: dict[str, int] = {
    "januari": 1, "january": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maart": 3, "march": 3, "mrt": 3, "maa": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "augustus": 8, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}  # fmt: skip
_MAAND_ALT = "|".join(sorted(_MAANDEN, key=len, reverse=True))

_TUSSEN = re.compile(rf"[ \t]{{0,{_MAX_TUSSENRUIMTE}}}:?[ \t]{{0,{_MAX_TUSSENRUIMTE}}}")
# Volgorde: ISO eerst (anders pakt het numerieke patroon "2024-03" als dag-maand).
_DATUM_RE = (
    re.compile(r"(?P<j>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})(?!\d)"),
    re.compile(r"(?P<d>\d{1,2})[-/.](?P<m>\d{1,2})[-/.](?P<j>\d{4}|\d{2})(?!\d)"),
    re.compile(rf"(?P<d>\d{{1,2}})\.?[ \t]+(?P<mn>{_MAAND_ALT})\.?,?[ \t]+(?P<j>\d{{4}}|\d{{2}})(?!\d)", re.I),
)


@dataclass(frozen=True)
class DatumTreffer:
    datum: date
    sleutelwoord: str  # naam uit _SLEUTELWOORDEN
    regel: str  # de regel waarin de datum stond (bij kolomlayout: de regel met de waarde), voor logging


def _jaar(tekst: str, vandaag: date) -> int:
    jaar = int(tekst)
    if len(tekst) == 2:
        jaar += 2000 if 2000 + jaar <= vandaag.year + 1 else 1900
    return jaar


def _parse(m: re.Match[str], vandaag: date) -> date | None:
    groepen = m.groupdict()
    try:
        jaar = _jaar(groepen["j"], vandaag)
        maand = _MAANDEN[groepen["mn"].lower()] if groepen.get("mn") else int(groepen["m"])
        datum = date(jaar, maand, int(groepen["d"]))
    except (KeyError, ValueError):
        return None
    if not MIN_JAAR <= datum.year <= vandaag.year + 1:
        return None
    return datum


def _datum_na(rest: str, vandaag: date) -> date | None:
    """Datum aan het begin van `rest`, na hoogstens spaties en een dubbele punt."""
    tussen = _TUSSEN.match(rest)
    start = tussen.end() if tussen else 0
    for patroon in _DATUM_RE:
        m = patroon.match(rest, start)
        if m:
            return _parse(m, vandaag)
    return None


def _afstand(a_start: int, a_eind: int, b_start: int, b_eind: int) -> int:
    """Afstand tussen twee tekenbereiken; 0 als ze overlappen."""
    return max(0, b_start - a_eind, a_start - b_eind)


def _datums_met_positie(regel: str, vandaag: date) -> list[tuple[int, int, date]]:
    """Alle geldige datums in `regel` als (start, eind, datum).

    Patronen in volgorde van `_DATUM_RE`; een match die overlapt met een eerder gevonden bereik
    telt niet (anders leest het dag-maand-patroon "24-03-12" binnen "2024-03-12").
    """
    gevonden: list[tuple[int, int, date]] = []
    for patroon in _DATUM_RE:
        for m in patroon.finditer(regel):
            if any(_afstand(m.start(), m.end(), start, eind) == 0 for start, eind, _ in gevonden):
                continue
            datum = _parse(m, vandaag)
            if datum is not None:
                gevonden.append((m.start(), m.end(), datum))
    return gevonden


def _datum_in_kolom(sleutel_start: int, sleutel_eind: int, waarderegel: str, vandaag: date) -> date | None:
    """Datum op `waarderegel` waarvan het tekenbereik het dichtst bij dat van het sleutelwoord ligt."""
    beste: tuple[int, date] | None = None
    for start, eind, datum in _datums_met_positie(waarderegel, vandaag):
        afstand = _afstand(sleutel_start, sleutel_eind, start, eind)
        if afstand <= _MAX_KOLOMAFSTAND and (beste is None or afstand < beste[0]):
            beste = (afstand, datum)
    return beste[1] if beste else None


def _volgende_niet_lege(regels: list[str], i: int) -> str | None:
    for regel in regels[i + 1 :]:
        if regel.strip():
            return regel
    return None


def vind_datum(tekst: str, vandaag: date | None = None) -> DatumTreffer | None:
    """Eerste bruikbare datum, gezocht per sleutelwoord in prioriteitsvolgorde over alle regels.

    Per sleutelwoord eerst alle regels met de datum achter het woord (sterkste bewijs), daarna de
    kolomlayout: label zonder datum op de eigen regel, datum in dezelfde kolom op de eerstvolgende
    niet-lege regel.
    """
    vandaag = vandaag or date.today()
    regels = [regel.expandtabs() for regel in tekst.splitlines()]
    for naam, sleutel in _SLEUTEL_RE:
        for regel in regels:
            for m in sleutel.finditer(regel):
                datum = _datum_na(regel[m.end() :], vandaag)
                if datum is not None:
                    return DatumTreffer(datum, naam, regel.strip())
        for i, regel in enumerate(regels):
            for m in sleutel.finditer(regel):
                waarderegel = _volgende_niet_lege(regels, i)
                if waarderegel is None:
                    continue
                datum = _datum_in_kolom(m.start(), m.end(), waarderegel, vandaag)
                if datum is not None:
                    return DatumTreffer(datum, naam, waarderegel.strip())
    return None
