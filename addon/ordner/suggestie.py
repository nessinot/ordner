"""Titel- en tagsuggestie uit de gelezen tekst (pakket 15a).

Stelt uit de tekst van een document een titel (alleen de bedrijfs- of instantienaam) en
tags (het documenttype) voor. Pure functies zonder I/O, met dezelfde opzet als `datum.py`.
Een verkeerde naam is erger dan geen naam: bij twijfel is de titelsuggestie leeg.

Heuristiek voor de titel, op prioriteit (de eerste stap met resultaat wint):
1. een bekende titel uit het archief die als heel woord in de tekst voorkomt;
2. de naam achter "t.n.v." of "ten name van";
3. de naam die hoort bij het domein van een e-mailadres of website in de tekst
   (`info@voorbeeld-installaties.nl` -> de cel "Voorbeeld Installaties", ook als die cel een rechtsvorm heeft);
4. de eerste kolomcel met een rechtsvorm (B.V., N.V., …) of instantiewoord (Gemeente, Belastingdienst, …);
   het rechtsvorm-achtervoegsel zelf blijft weg uit de titel ("Voorbeeldshop B.V." -> "Voorbeeldshop"), ook achter "t.n.v.";
5. anders leeg.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Literal

from ordner.slug import maak_slug

TitelBron = Literal["archief", "tnv", "domein", "rechtsvorm", "geen"]

_MAX_TITEL = 60  # tekens; afkappen op woordgrens
_MIN_BEKENDE_TITEL = 3  # kortere archieftitels worden niet gezocht
_FALLBACK_TITEL = "document"  # fallback van maak_slug/inbox; nooit als bekende titel gebruiken

# Documenttypewoord -> tag. Telt alleen als kopregel (cel gelijk aan het woord, of het woord
# gevolgd door een niet-letter): "Factuur", "FACTUUR", "Factuur nr. 123"; niet "Factuurdatum".
_DOCUMENTTYPEN: dict[str, str] = {
    "factuur": "factuur",
    "creditnota": "creditnota",
    "offerte": "offerte",
    "polis": "polis",
    "beschikking": "beschikking",
    "nota": "nota",
    "bon": "bon",
    "kassabon": "bon",
    "herinnering": "herinnering",
    "betalingsherinnering": "herinnering",
    "aanmaning": "aanmaning",
    "contract": "contract",
    "overeenkomst": "overeenkomst",
    "aanslag": "aanslag",
    "jaaroverzicht": "jaaroverzicht",
    "jaarafrekening": "jaarafrekening",
    "garantiebewijs": "garantie",
}
_DOCUMENTTYPE_WOORDEN = set(_DOCUMENTTYPEN) | set(_DOCUMENTTYPEN.values())

# Rechtsvormen als achtervoegsel: herkennen de cel; de titel is het deel ervoor.
# Bewust hoofdlettergevoelig: "b.v." is in lopende tekst "bijvoorbeeld".
_ACHTERVOEGSELS: tuple[str, ...] = ("B.V.", "BV", "N.V.", "NV", "V.O.F.", "VOF", "U.A.")
# Instantiewoorden als voorvoegsel: vanaf het woord tot het eind van de cel ("Gemeente Voorbeeldstad").
_VOORVOEGSELS: tuple[str, ...] = (
    "gemeente", "stichting", "vereniging", "waterschap", "provincie", "coöperatie", "cooperatie", "ministerie",
)  # fmt: skip
# Losse instantiewoorden: de hele cel. Niet "bank" of "verzekeraar": die staan op vrijwel elke
# factuur als bankgegevens of in lopende tekst; echte banken hebben een rechtsvorm.
_LOSSE_WOORDEN: tuple[str, ...] = (
    "belastingdienst", "zorgverzekeraar", "ziekenhuis", "universiteit", "hogeschool",
)  # fmt: skip
# Domeinlabels van e-mailproviders: zeggen niets over de afzender.
_PROVIDERS: frozenset[str] = frozenset(
    {"gmail", "googlemail", "hotmail", "outlook", "live", "icloud", "yahoo", "protonmail", "kpnmail"}
)

# Woordgrenzen via lookarounds op alnum: `\b` faalt aan de rand van "B.V." (eindigt op een leesteken).
_GRENS_VOOR = r"(?<![^\W_])"
_GRENS_NA = r"(?![^\W_])"
_LETTER = r"[^\W\d_]"


def _alternatie(woorden: Iterable[str]) -> str:
    return "|".join(re.escape(w) for w in sorted(woorden, key=len, reverse=True))


_KOPREGEL_RE = re.compile(rf"^(?P<woord>{_alternatie(_DOCUMENTTYPEN)})(?!{_LETTER})", re.I)
_TNV_RE = re.compile(rf"{_GRENS_VOOR}(?:t\.n\.v\.?|ten name van){_GRENS_NA}\s*:?\s*(?P<naam>.*)$", re.I)
_ACHTERVOEGSEL_RE = re.compile(rf"^\S.*?(?P<rest>\s+(?:{_alternatie(_ACHTERVOEGSELS)}){_GRENS_NA}.*)$")
_VOORVOEGSEL_RE = re.compile(rf"{_GRENS_VOOR}(?:{_alternatie(_VOORVOEGSELS)}){_GRENS_NA}\s+\S", re.I)
_LOS_WOORD_RE = re.compile(rf"{_GRENS_VOOR}(?:{_alternatie(_LOSSE_WOORDEN)}){_GRENS_NA}", re.I)
# Host achter "@", "http(s)://" of "www."; minstens twee labels.
_DOMEIN_RE = re.compile(r"(?:@|https?://|www\.)(?P<host>[a-z0-9-]+(?:\.[a-z0-9-]+)+)", re.I)

_LETTERS_RE = re.compile(_LETTER)


@dataclass(frozen=True)
class Suggestie:
    titel: str  # "" als er geen betrouwbare naam is
    titelbron: TitelBron  # voor logging en tests
    tags: list[str]  # documenttype(n), lowercase, in volgorde van voorkomen


# --- hulpfuncties ----------------------------------------------------------


def cellen(regel: str) -> list[str]:
    """Splitst een regel op twee of meer spaties (tabs geëxpandeerd) in niet-lege, gestripte cellen.

    `pdftotext -layout` zet adresblokken en tabelkolommen naast elkaar; per cel kijken voorkomt
    dat "Voltaria B.V.        Factuurnummer 123" in zijn geheel een titel wordt.
    """
    return [cel.strip() for cel in re.split(r" {2,}", regel.expandtabs()) if cel.strip()]


def _schoon(tekst: str) -> str:
    """Whitespace samenvoegen, leestekens aan de randen weg, max 60 tekens op woordgrens."""
    s = " ".join(tekst.split()).strip(",;:.- ")
    if len(s) > _MAX_TITEL:
        kop = s[:_MAX_TITEL]
        s = kop.rsplit(" ", 1)[0] if " " in kop else kop
        s = s.rstrip(",;:.- ")
    return s


def _zonder_rechtsvorm(tekst: str) -> str:
    """Alles vanaf een rechtsvorm-achtervoegsel weg: "Voorbeeldshop B.V. Postbus 1" -> "Voorbeeldshop"; anders ongewijzigd."""
    m = _ACHTERVOEGSEL_RE.match(tekst)
    return tekst[: m.start("rest")] if m else tekst


def _is_documenttypewoord(tekst: str) -> bool:
    return tekst.strip().lower() in _DOCUMENTTYPE_WOORDEN


def _bekende_titel_re(titel: str) -> re.Pattern[str]:
    woorden = [re.escape(w) for w in titel.split()]
    return re.compile(_GRENS_VOOR + r"\s+".join(woorden) + _GRENS_NA, re.I)


# --- titel -----------------------------------------------------------------


def _uit_archief(tekst: str, bekende_titels: Iterable[str]) -> str:
    """Langste bekende titel die als heel woord in de tekst staat; bij gelijke lengte de vroegste treffer."""
    beste: tuple[int, int, str] | None = None
    for ruw in bekende_titels:
        titel = " ".join(ruw.split())
        if len(titel) < _MIN_BEKENDE_TITEL or titel.lower() == _FALLBACK_TITEL or _is_documenttypewoord(titel):
            continue
        m = _bekende_titel_re(titel).search(tekst)
        if m is None:
            continue
        sleutel = (-len(titel), m.start(), titel)
        if beste is None or sleutel < beste:
            beste = sleutel
    return beste[2] if beste else ""


def _uit_tnv(regels: list[list[str]]) -> str:
    for cellen_ in regels:
        for cel in cellen_:
            m = _TNV_RE.search(cel)
            if m is None:
                continue
            naam = _schoon(_zonder_rechtsvorm(m.group("naam")[:_MAX_TITEL]))
            if naam:
                return naam
    return ""


def _domeinlabels(tekst: str) -> list[str]:
    """Voorlaatste hostonderdeel van elk domein in de tekst ("winkel.voorbeeldshop.nl" -> "voorbeeldshop"), zonder
    e-mailproviders; uniek, op aantal voorkomens aflopend en dan op eerste voorkomen.

    De afzender staat er meestal twee keer (e-mail én website), de klant hooguit één keer.
    """
    labels = [m.group("host").lower().split(".")[-2] for m in _DOMEIN_RE.finditer(tekst)]
    telling = Counter(labels)
    volgorde = list(dict.fromkeys(labels))
    return [lab for lab in sorted(volgorde, key=lambda lab: (-telling[lab], volgorde.index(lab))) if lab not in _PROVIDERS]


def _uit_domein(tekst: str, regels: list[list[str]]) -> str:
    """Eerste cel waarvan de slug gelijk is aan een domeinlabel (ook zonder koppeltekens); de hoofdletters uit de tekst.

    Een rechtsvorm-achtervoegsel telt niet mee: "Voorbeeldshop B.V." matcht `voorbeeldshop` en geeft "Voorbeeldshop".
    """
    for label in _domeinlabels(tekst):
        kaal = label.replace("-", "")
        for cellen_ in regels:
            for cel in cellen_:
                if len(_LETTERS_RE.findall(cel)) < 3:
                    continue
                kern = _zonder_rechtsvorm(cel)
                slug = maak_slug(kern)
                if slug == label or slug.replace("-", "") == kaal:
                    naam = _schoon(kern)
                    if naam:
                        return naam
    return ""


def _uit_rechtsvorm(regels: list[list[str]]) -> str:
    for cellen_ in regels:
        for cel in cellen_:
            if _ACHTERVOEGSEL_RE.match(cel):
                naam = _schoon(_zonder_rechtsvorm(cel))
            else:
                m = _VOORVOEGSEL_RE.search(cel)
                if m is not None:
                    naam = _schoon(cel[m.start() :])
                elif _LOS_WOORD_RE.search(cel):
                    naam = _schoon(cel)
                else:
                    continue
            if naam:
                return naam
    return ""


def _regels(tekst: str) -> list[list[str]]:
    """Niet-lege regels, elk als lijst cellen."""
    return [c for c in (cellen(regel) for regel in tekst.splitlines()) if c]


def stel_titel_voor(tekst: str, bekende_titels: Iterable[str] = ()) -> tuple[str, TitelBron]:
    """Titelsuggestie (alleen de afzender) en de bron ervan; ("", "geen") als niets betrouwbaar is."""
    if not tekst.strip():
        return "", "geen"
    titel = _uit_archief(tekst, bekende_titels)
    if titel:
        return titel, "archief"
    regels = _regels(tekst)
    stappen: tuple[tuple[TitelBron, str], ...] = (
        ("tnv", _uit_tnv(regels)),
        ("domein", _uit_domein(tekst, regels)),
        ("rechtsvorm", _uit_rechtsvorm(regels)),
    )
    for bron, titel in stappen:
        if titel:
            return titel, bron
    return "", "geen"


# --- tags ------------------------------------------------------------------


def stel_tags_voor(tekst: str) -> list[str]:
    """Documenttypen uit kopregels, lowercase, in volgorde van eerste voorkomen, zonder dubbelen."""
    tags: list[str] = []
    for cellen_ in _regels(tekst):
        for cel in cellen_:
            m = _KOPREGEL_RE.match(cel)
            if m is None:
                continue
            tag = _DOCUMENTTYPEN[m.group("woord").lower()]
            if tag not in tags:
                tags.append(tag)
    return tags


def stel_voor(tekst: str, bekende_titels: Iterable[str] = ()) -> Suggestie:
    """Titel- en tagsuggestie voor één document; pure functie."""
    titel, bron = stel_titel_voor(tekst, bekende_titels)
    return Suggestie(titel=titel, titelbron=bron, tags=stel_tags_voor(tekst))
