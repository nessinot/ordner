"""Documentdatum uit de gelezen tekst halen (pakket 14).

Zoekt per sleutelwoord, in prioriteitsvolgorde, naar een datum die direct achter dat
woord op dezelfde regel staat (alleen spaties en een optionele dubbele punt ertussen).
Pure functies, geen I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

MIN_JAAR = 1990
_MAX_TUSSENRUIMTE = 60  # tekens tussen sleutelwoord en datum (pdftotext -layout kan brede kolommen geven)

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
    regel: str  # de regel waarin de datum stond, voor logging


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


def vind_datum(tekst: str, vandaag: date | None = None) -> DatumTreffer | None:
    """Eerste bruikbare datum, gezocht per sleutelwoord in prioriteitsvolgorde over alle regels."""
    vandaag = vandaag or date.today()
    regels = tekst.splitlines()
    for naam, sleutel in _SLEUTEL_RE:
        for regel in regels:
            for m in sleutel.finditer(regel):
                datum = _datum_na(regel[m.end() :], vandaag)
                if datum is not None:
                    return DatumTreffer(datum, naam, regel.strip())
    return None
