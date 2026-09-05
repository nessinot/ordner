"""Tests voor ordner.datum (pakket 14, kolomlayout in 0.6.0)."""

from __future__ import annotations

from datetime import date

import pytest

from ordner.datum import vind_datum

VANDAAG = date(2026, 9, 4)


def _datum(tekst: str) -> date | None:
    t = vind_datum(tekst, VANDAAG)
    return t.datum if t else None


@pytest.mark.parametrize(
    "tekst, verwacht",
    [
        ("Factuurdatum: 12-03-2024", date(2024, 3, 12)),
        ("Factuurdatum 12-03-2024", date(2024, 3, 12)),
        ("Factuur datum: 12/03/2024", date(2024, 3, 12)),
        ("FACTUURDATUM    12.03.2024", date(2024, 3, 12)),
        ("factuurdatum:12-03-24", date(2024, 3, 12)),
        ("Factuurdatum: 2024-03-12", date(2024, 3, 12)),
        ("Factuurdatum: 12 maart 2024", date(2024, 3, 12)),
        ("Factuurdatum: 12 mrt 2024", date(2024, 3, 12)),
        ("Factuurdatum: 12 mrt. 2024", date(2024, 3, 12)),
        ("Factuurdatum: 1 januari 2024", date(2024, 1, 1)),
        ("Factuurdatum: 5 sept 2023", date(2023, 9, 5)),
        ("Invoice date: 12 March 2024", None),  # Engelse sleutelwoorden vallen buiten de lijst
        ("Datum: 12 March 2024", date(2024, 3, 12)),  # Engelse maandnaam wel
        ("Notadatum: 3-1-2022", date(2022, 1, 3)),
        ("Orderdatum: 30-11-2021", date(2021, 11, 30)),
        ("Dagtekening: 14 februari 2020", date(2020, 2, 14)),
        ("Dagtekening 14-02-2020", date(2020, 2, 14)),
        ("Datum: 07-06-2019", date(2019, 6, 7)),
        ("datum 7-6-19", date(2019, 6, 7)),
    ],
)
def test_sleutelwoord_met_datum(tekst: str, verwacht: date | None) -> None:
    assert _datum(tekst) == verwacht


def test_prioriteit_factuurdatum_boven_datum() -> None:
    tekst = "Datum: 01-01-2024\nVervaldatum: 31-01-2024\nFactuurdatum: 15-01-2024\n"
    t = vind_datum(tekst, VANDAAG)
    assert t is not None
    assert t.datum == date(2024, 1, 15)
    assert t.sleutelwoord == "factuurdatum"
    assert t.regel == "Factuurdatum: 15-01-2024"


def test_prioriteit_volgorde_lijst() -> None:
    assert _datum("Datum: 01-01-2024\nDagtekening: 02-01-2024\nOrderdatum: 03-01-2024") == date(2024, 1, 3)
    assert _datum("Datum: 01-01-2024\nDagtekening: 02-01-2024") == date(2024, 1, 2)
    assert _datum("Notadatum: 04-01-2024\nOrderdatum: 03-01-2024") == date(2024, 1, 4)
    assert _datum("Afdrukdatum: 05-01-2024\nDatum: 01-01-2024") == date(2024, 1, 1)


def test_afdrukdatum_als_enige_sleutelwoord() -> None:
    t = vind_datum("Afdrukdatum: 05-01-2024", VANDAAG)
    assert t is not None
    assert t.datum == date(2024, 1, 5)
    assert t.sleutelwoord == "afdrukdatum"
    assert _datum("Afdruk datum 5 januari 2024") == date(2024, 1, 5)
    assert _datum("Afdrukdatum      Pagina\n05-01-2024       1 van 2") == date(2024, 1, 5)
    assert _datum("Vervaldatum: 31-01-2024\nAfdrukdatum: 05-01-2024") == date(2024, 1, 5)


def test_vervaldatum_en_betaaldatum_tellen_niet() -> None:
    assert _datum("Vervaldatum: 31-01-2024") is None
    assert _datum("Betaaldatum 31-01-2024\nGeboortedatum: 01-01-1980") is None
    assert _datum("Vervaldatum: 31-01-2024\nDatum: 15-01-2024") == date(2024, 1, 15)


def test_datum_moet_direct_achter_het_woord_staan() -> None:
    assert _datum("Factuurdatum en nummer: 12-03-2024") is None
    assert _datum("Factuurdatum: zie boven 12-03-2024") is None


def test_brede_kolom_uit_pdftotext_layout() -> None:
    assert _datum("Factuurdatum" + " " * 40 + "12-03-2024      Factuurnummer 2024001") == date(2024, 3, 12)


# --- kolomlayout: label op de ene regel, waarde in dezelfde kolom op de volgende ---

KOLOM = "Factuurnummer        Factuurdatum        Vervaldatum\n2024001              12-03-2024          12-04-2024\n"


def test_kolomlayout_label_boven_waarde() -> None:
    t = vind_datum(KOLOM, VANDAAG)
    assert t is not None
    assert t.datum == date(2024, 3, 12)
    assert t.sleutelwoord == "factuurdatum"
    assert t.regel == "2024001              12-03-2024          12-04-2024"


def test_kolomlayout_enkel_label_en_waarde() -> None:
    assert _datum("Factuurdatum\n12-03-2024") == date(2024, 3, 12)
    assert _datum("Datum\n\n\n12 maart 2024") == date(2024, 3, 12)  # lege regels ertussen mogen


def test_kolomlayout_dichtstbijzijnde_kolom_wint() -> None:
    assert _datum("Vervaldatum          Factuurdatum\n12-04-2024           12-03-2024\n") == date(2024, 3, 12)
    assert _datum("Factuurdatum         Vervaldatum\n12-03-2024           12-04-2024\n") == date(2024, 3, 12)


def test_kolomlayout_rechts_uitgelijnd() -> None:
    tekst = "        Factuurnummer        Factuurdatum\n              2024001          12-03-2024\n"
    assert _datum(tekst) == date(2024, 3, 12)


def test_kolomlayout_iso_en_tabs() -> None:
    assert _datum("Factuurnummer\tFactuurdatum\n2024001\t\t2024-03-12") == date(2024, 3, 12)
    assert _datum("Factuurdatum\n2024-03-12") == date(2024, 3, 12)  # niet "24-03-12" binnen de ISO-datum


def test_kolomlayout_te_ver_weg_of_geen_datum() -> None:
    assert _datum("Factuurdatum\n" + " " * 33 + "12-03-2024") is None  # afstand 21 > _MAX_KOLOMAFSTAND
    assert _datum("Factuurdatum\n" + " " * 32 + "12-03-2024") == date(2024, 3, 12)  # afstand 20 mag nog
    assert _datum("Factuurdatum\nFactuurnummer 2024001\n12-03-2024") is None  # alleen de eerstvolgende regel
    assert _datum("Factuurdatum\nzonder datum") is None
    assert _datum("Factuurdatum\n31-02-2024") is None  # ongeldige datum in de kolom


def test_kolomlayout_regeltreffer_gaat_voor() -> None:
    tekst = "Factuurdatum\n12-03-2024\nFactuurdatum: 15-03-2024\n"
    t = vind_datum(tekst, VANDAAG)
    assert t is not None
    assert t.datum == date(2024, 3, 15)
    assert t.regel == "Factuurdatum: 15-03-2024"


def test_kolomlayout_sleutelwoordprioriteit_boven_regeltreffer() -> None:
    t = vind_datum("Datum: 01-01-2024\n" + KOLOM, VANDAAG)
    assert t is not None
    assert t.datum == date(2024, 3, 12)
    assert t.sleutelwoord == "factuurdatum"


def test_kolomlayout_vervaldatum_telt_niet() -> None:
    assert _datum("Vervaldatum\n12-04-2024") is None


# --- plausibiliteit en randgevallen ---


def test_onmogelijke_en_onwaarschijnlijke_datums() -> None:
    assert _datum("Factuurdatum: 31-02-2024") is None
    assert _datum("Factuurdatum: 12-13-2024") is None
    assert _datum("Factuurdatum: 12-03-1980") is None  # vóór MIN_JAAR
    assert _datum("Factuurdatum: 12-03-2035") is None  # ver in de toekomst
    assert _datum("Factuurdatum: 12-03-2027") == date(2027, 3, 12)  # volgend jaar mag
    assert _datum("Factuurdatum: 12-03-20245") is None  # vijfcijferig jaar
    assert _datum("Factuurdatum: 123-03-2024") is None


def test_tweecijferig_jaar() -> None:
    assert _datum("Datum: 01-02-99") == date(1999, 2, 1)
    assert _datum("Datum: 01-02-26") == date(2026, 2, 1)
    assert _datum("Datum: 01-02-27") == date(2027, 2, 1)
    assert _datum("Datum: 01-02-28") is None  # 2028 ligt te ver vooruit, 1928 vóór MIN_JAAR


def test_eerste_treffer_bij_meerdere_regels() -> None:
    tekst = "Kopregel\nDatum: onbekend\nDatum: 05-05-2022\nDatum: 06-06-2022"
    assert _datum(tekst) == date(2022, 5, 5)


def test_geen_tekst_of_geen_datum() -> None:
    assert _datum("") is None
    assert _datum("Factuur zonder datum") is None
    assert _datum("12-03-2024 zonder sleutelwoord") is None


def test_vandaag_default_is_vandaag() -> None:
    assert vind_datum(f"Datum: {date.today():%d-%m-%Y}") is not None
