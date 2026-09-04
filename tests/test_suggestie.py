"""Tests voor ordner.suggestie (pakket 15a): titel- en tagsuggestie uit de tekst. Pure functies, geen fixtures."""

from __future__ import annotations

import pytest

from ordner.suggestie import Suggestie, cellen, stel_tags_voor, stel_titel_voor, stel_voor

# Lange "brief" (>= 25 niet-lege regels) zodat de bon-stap niet meedoet.
_LANG = "regel tekst\n" * 30


# --- cellen ------------------------------------------------------------------


def test_cellen_splitst_op_twee_of_meer_spaties_en_tabs() -> None:
    assert cellen("Eneco B.V.        Factuurnummer 123") == ["Eneco B.V.", "Factuurnummer 123"]
    assert cellen("Gemeente Amsterdam\tPostbus 1") == ["Gemeente Amsterdam", "Postbus 1"]
    assert cellen("een enkele spatie blijft één cel") == ["een enkele spatie blijft één cel"]
    assert cellen("   ") == []
    assert cellen("  aan de randen  ") == ["aan de randen"]


# --- stap 1: bekende titel uit het archief -----------------------------------


def test_bekende_titel_als_heel_woord() -> None:
    tekst = "Aan: J. Jansen\nAfzender ENECO Services\n" + _LANG
    assert stel_titel_voor(tekst, ["Eneco", "Vattenfall"]) == ("Eneco", "archief")


def test_bekende_titel_matcht_niet_binnen_een_woord() -> None:
    assert stel_titel_voor("Wij verkopen rozenecobloemen\n" + _LANG, ["Eneco"]) == ("", "geen")
    assert stel_titel_voor("Zie Eneco2024 voor details\n" + _LANG, ["Eneco"]) == ("", "geen")


def test_bekende_titel_wint_van_rechtsvorm() -> None:
    tekst = "Vattenfall N.V.\nUw leverancier: Eneco\n" + _LANG
    assert stel_titel_voor(tekst, ["Eneco"]) == ("Eneco", "archief")
    assert stel_titel_voor(tekst) == ("Vattenfall N.V.", "rechtsvorm")


def test_langste_bekende_titel_wint_dan_vroegste_treffer() -> None:
    tekst = "Gemeente Amsterdam, afdeling Belastingen\n" + _LANG
    assert stel_titel_voor(tekst, ["Amsterdam", "Gemeente Amsterdam"]) == ("Gemeente Amsterdam", "archief")
    assert stel_titel_voor("Ziggo en Odido\n" + _LANG, ["Odido", "Ziggo"]) == ("Ziggo", "archief")


def test_bekende_titel_met_leesteken_aan_de_rand() -> None:
    tekst = "Klantnummer 1\nEneco B.V.\n" + _LANG
    assert stel_titel_voor(tekst, ["Eneco B.V."]) == ("Eneco B.V.", "archief")
    assert stel_titel_voor("Gemeente    Utrecht\n" + _LANG, ["Gemeente Utrecht"]) == ("Gemeente Utrecht", "archief")


def test_bekende_titel_document_en_documenttypewoord_worden_genegeerd() -> None:
    tekst = "Factuur\nDit document is een kopie\nAH\n" + _LANG
    assert stel_titel_voor(tekst, ["document", "Factuur", "AH", "Document"]) == ("", "geen")


# --- stap 2: t.n.v. ----------------------------------------------------------


@pytest.mark.parametrize(
    "regel",
    ["IBAN NL12ABCD0123456789 t.n.v. Eneco Services B.V.", "Ten name van: Eneco Services B.V.", "T.N.V Eneco Services B.V."],
)
def test_tnv_geeft_de_naam_erachter(regel: str) -> None:
    assert stel_titel_voor(regel + "\n" + _LANG) == ("Eneco Services B.V.", "tnv")


def test_tnv_stopt_bij_de_kolomcel() -> None:
    tekst = "t.n.v. Eneco Services B.V.        Vervaldatum 01-01-2025\n" + _LANG
    assert stel_titel_voor(tekst) == ("Eneco Services B.V.", "tnv")


def test_tnv_zonder_naam_of_binnen_woord_telt_niet() -> None:
    assert stel_titel_voor("t.n.v.\n" + _LANG) == ("", "geen")
    assert stel_titel_voor("Antnv. Jansen\n" + _LANG) == ("", "geen")


# --- stap 3: rechtsvorm / instantiewoord --------------------------------------


@pytest.mark.parametrize(
    ("cel", "verwacht"),
    [
        ("Eneco Services B.V.", "Eneco Services B.V."),
        ("Eneco Services B.V. Postbus 1234", "Eneco Services B.V."),
        ("Bakkerij Jansen VOF", "Bakkerij Jansen VOF"),
        ("Coöperatie DELA U.A.", "Coöperatie DELA U.A."),
        ("Vattenfall N.V.,", "Vattenfall N.V."),
    ],
)
def test_achtervoegsel_geeft_de_cel_tot_en_met_het_achtervoegsel(cel: str, verwacht: str) -> None:
    assert stel_titel_voor("Geachte heer,\n" + cel + "\n" + _LANG) == (verwacht, "rechtsvorm")


def test_achtervoegsel_is_hoofdlettergevoelig_en_heel_woord() -> None:
    assert stel_titel_voor("Neem b.v. contact op met ons\n" + _LANG) == ("", "geen")  # "bijvoorbeeld"
    assert stel_titel_voor("Levering ABVAKABO\n" + _LANG) == ("", "geen")
    assert stel_titel_voor("B.V.\n" + _LANG) == ("", "geen")  # niets vóór het achtervoegsel


@pytest.mark.parametrize(
    ("cel", "verwacht"),
    [
        ("Gemeente Amsterdam", "Gemeente Amsterdam"),
        ("Aan de Gemeente Amsterdam, afdeling Belastingen", "Gemeente Amsterdam, afdeling Belastingen"),
        ("STICHTING PENSIOENFONDS ABP", "STICHTING PENSIOENFONDS ABP"),
        ("Ministerie van Financiën", "Ministerie van Financiën"),
    ],
)
def test_voorvoegsel_geeft_vanaf_het_woord_tot_het_eind_van_de_cel(cel: str, verwacht: str) -> None:
    assert stel_titel_voor("Kenmerk 1\n" + cel + "\n" + _LANG) == (verwacht, "rechtsvorm")


def test_voorvoegsel_zonder_naam_erachter_telt_niet() -> None:
    assert stel_titel_voor("Gemeente\nGemeentelijke heffingen\n" + _LANG) == ("", "geen")


def test_los_instantiewoord_geeft_de_hele_cel() -> None:
    assert stel_titel_voor("Kenmerk 1\nBelastingdienst\n" + _LANG) == ("Belastingdienst", "rechtsvorm")
    assert stel_titel_voor("Kenmerk 1\nUniversiteit Utrecht        Kamer 1\n" + _LANG) == ("Universiteit Utrecht", "rechtsvorm")
    assert stel_titel_voor("Rabobank\n" + _LANG) == ("", "geen")  # "bank" niet als heel woord


def test_eerste_regel_met_rechtsvorm_wint_en_kolommen_blijven_gescheiden() -> None:
    tekst = "Klant B.V.        Eneco B.V.\nVattenfall N.V.\n" + _LANG
    assert stel_titel_voor(tekst) == ("Klant B.V.", "rechtsvorm")


# --- stap 4: korte tekst (bon) ------------------------------------------------


def test_bon_eerste_bruikbare_regel() -> None:
    assert stel_titel_voor("ALBERT HEIJN 1234\nKassabon\nMelk 1,09\nDatum 01-02-2024") == ("ALBERT HEIJN 1234", "eerste-regel")


def test_bon_slaat_documenttypewoord_datum_en_korte_regels_over() -> None:
    tekst = "Bon\n12\nVervaldatum: 12-04-2024\nFactuurdatum\n01-02-2024\nBakkerij Jansen\n"
    assert stel_titel_voor(tekst) == ("Bakkerij Jansen", "eerste-regel")
    assert stel_titel_voor("Factuur nr. 123\n01-02-2024\n") == ("", "geen")


def test_lange_tekst_neemt_nooit_blind_de_eerste_regel() -> None:
    assert stel_titel_voor("J. Jansen\nDorpsstraat 1\n" + _LANG) == ("", "geen")


# --- opschonen ----------------------------------------------------------------


def test_opschonen_leestekens_en_whitespace() -> None:
    assert stel_titel_voor("Kenmerk\n- Gemeente Utrecht :\n" + _LANG) == ("Gemeente Utrecht", "rechtsvorm")
    assert stel_titel_voor("Kenmerk\nt.n.v.: Eneco Services B.V.,\n" + _LANG) == ("Eneco Services B.V.", "tnv")


def test_afkappen_op_60_tekens_op_woordgrens() -> None:
    naam = "Stichting " + " ".join(["Woord"] * 20)
    titel, bron = stel_titel_voor("Kenmerk\n" + naam + "\n" + _LANG)
    assert bron == "rechtsvorm"
    assert len(titel) <= 60
    assert titel == "Stichting Woord Woord Woord Woord Woord Woord Woord Woord"
    assert not titel.endswith(" ")


def test_hoofdletters_blijven_zoals_in_de_tekst() -> None:
    assert stel_titel_voor("Kenmerk\nENECO SERVICES B.V.\n" + _LANG)[0] == "ENECO SERVICES B.V."


# --- tags ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tekst", "tags"),
    [
        ("Factuur", ["factuur"]),
        ("FACTUUR", ["factuur"]),
        ("Factuur nr. 123", ["factuur"]),
        ("Eneco B.V.        Factuur", ["factuur"]),
        ("Kassabon", ["bon"]),
        ("Betalingsherinnering", ["herinnering"]),
        ("Garantiebewijs", ["garantie"]),
        ("Factuurdatum: 01-01-2024", []),
        ("Wij sturen u deze factuur toe", []),
        ("Polisnummer 123", []),
        ("", []),
    ],
)
def test_tag_alleen_als_kopregel(tekst: str, tags: list[str]) -> None:
    assert stel_tags_voor(tekst) == tags


def test_tags_in_volgorde_zonder_dubbelen() -> None:
    tekst = "Offerte\nFactuur\nfactuur 2\nHerinnering        Aanmaning\n"
    assert stel_tags_voor(tekst) == ["offerte", "factuur", "herinnering", "aanmaning"]


# --- stel_voor -----------------------------------------------------------------


def test_stel_voor_combineert() -> None:
    tekst = "Eneco Services B.V.        Factuur\nFactuurdatum 01-02-2024\n" + _LANG
    assert stel_voor(tekst) == Suggestie(titel="Eneco Services B.V.", titelbron="rechtsvorm", tags=["factuur"])
    assert stel_voor(tekst, ["Eneco"]) == Suggestie(titel="Eneco", titelbron="archief", tags=["factuur"])


def test_lege_tekst_geeft_lege_suggestie() -> None:
    assert stel_voor("") == Suggestie(titel="", titelbron="geen", tags=[])
    assert stel_voor("  \n\t\n", ["Eneco"]) == Suggestie(titel="", titelbron="geen", tags=[])
