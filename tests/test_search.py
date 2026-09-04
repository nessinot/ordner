from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ordner.index import Index
from ordner.meta import lees_meta, schrijf_meta
from ordner.search import zoek
from ordner.storage import Archief


def _doc(
    archief: Archief,
    index: Index,
    titel: str,
    datum: date,
    *,
    omschrijving: str = "",
    tags: list[str] | None = None,
    notities: str = "",
    teksten: dict[str, str] | None = None,
) -> Path:
    doc = archief.maak_document(titel, datum, omschrijving=omschrijving, tags=tags)
    for naam, tekst in (teksten or {}).items():
        archief.voeg_bestand_toe(doc, naam, b"x")
        (doc / f"{naam}.txt").write_text(tekst, encoding="utf-8")
    if notities:
        meta = lees_meta(doc)
        meta.notities = notities
        schrijf_meta(doc, meta)
    index.herlaad(archief, doc)
    return doc


@pytest.fixture
def index(archief: Archief) -> Index:
    index = Index()
    _doc(
        archief,
        index,
        "WOZ-beschikking 2026",
        date(2026, 3, 1),
        omschrijving="Aanslag onroerende zaken",
        tags=["woz", "belasting"],
        notities="Bezwaar ingediend in april.",
        teksten={"beschikking.pdf": "Gemeente Utrecht stelt de waarde vast op 400.000 euro."},
    )
    _doc(
        archief,
        index,
        "Factuur loodgieter",
        date(2025, 11, 15),
        teksten={"factuur.pdf": "Reparatie lekkage badkamer, totaal 250 euro."},
    )
    _doc(archief, index, "café", date(2024, 1, 1))
    _doc(archief, index, "CAFÉ", date(2023, 1, 1))
    return index


def test_woord_in_titel(index: Index) -> None:
    treffers = zoek(index, "loodgieter")
    assert len(treffers) == 1
    assert treffers[0].titel == "Factuur loodgieter"
    assert treffers[0].bron == "titel"
    assert "loodgieter" in treffers[0].snippet


def test_woord_alleen_in_txt(index: Index) -> None:
    treffers = zoek(index, "lekkage")
    assert len(treffers) == 1
    assert treffers[0].titel == "Factuur loodgieter"
    assert treffers[0].bron == "factuur.pdf"
    assert "lekkage" in treffers[0].snippet


def test_and_over_velden(index: Index) -> None:
    treffers = zoek(index, "woz gemeente")
    assert [t.titel for t in treffers] == ["WOZ-beschikking 2026"]
    assert treffers[0].bron == "titel"
    assert zoek(index, "woz nietbestaand") == []


def test_hoofdletterongevoelig(index: Index) -> None:
    assert {t.titel for t in zoek(index, "CAFÉ")} == {"café", "CAFÉ"}
    assert {t.titel for t in zoek(index, "café")} == {"café", "CAFÉ"}


def test_datum(index: Index) -> None:
    treffers = zoek(index, "2026-03")
    assert [t.titel for t in treffers] == ["WOZ-beschikking 2026"]
    assert treffers[0].bron == "documentdatum"
    assert treffers[0].documentdatum == date(2026, 3, 1)


def test_tags_en_notities(index: Index) -> None:
    belasting = zoek(index, "belasting")
    assert [t.titel for t in belasting] == ["WOZ-beschikking 2026"]
    assert belasting[0].bron == "tags"

    bezwaar = zoek(index, "bezwaar")
    assert [t.titel for t in bezwaar] == ["WOZ-beschikking 2026"]
    assert bezwaar[0].bron == "notities"


def test_omschrijving(index: Index) -> None:
    treffers = zoek(index, "onroerende")
    assert treffers[0].bron == "omschrijving"
    assert treffers[0].omschrijving == "Aanslag onroerende zaken"


def test_snippet_midden_in_lange_tekst(archief: Archief) -> None:
    index = Index()
    tekst = "lorem " * 50 + "naald\nin   de\thooiberg " + "ipsum " * 50
    _doc(archief, index, "Lang", date(2026, 1, 1), teksten={"lang.pdf": tekst})

    treffers = zoek(index, "naald")
    assert len(treffers) == 1
    snippet = treffers[0].snippet
    assert snippet.startswith("…")
    assert snippet.endswith("…")
    assert "naald in de hooiberg" in snippet
    assert len(snippet) <= 2 + 5 + 2 * 80


def test_snippet_zonder_afkappen(index: Index) -> None:
    snippet = zoek(index, "loodgieter")[0].snippet
    assert snippet == "Factuur loodgieter"


def test_lege_query(index: Index) -> None:
    assert zoek(index, "") == []
    assert zoek(index, "   \t\n") == []


def test_geen_limiet_in_zoek(index: Index) -> None:
    treffers = zoek(index, "café")
    assert [t.titel for t in treffers] == ["café", "CAFÉ"]  # 2024 is nieuwer dan 2023; niets afgekapt


def test_volgorde_nieuwste_eerst(index: Index) -> None:
    treffers = zoek(index, "euro")
    assert [t.documentdatum for t in treffers] == [date(2026, 3, 1), date(2025, 11, 15)]


def test_rel_verwijst_naar_document(archief: Archief, index: Index) -> None:
    treffer = zoek(index, "loodgieter")[0]
    assert treffer.rel in index.docs
    assert index.docs[treffer.rel].map.is_dir()
