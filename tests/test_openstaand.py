"""Tests voor de openstaande uploads tussen scherm 1 en 2 (pakket 15b)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from ordner.ingest import Voorbereid
from ordner.suggestie import Suggestie
from ordner.web.openstaand import OpenstaandeUpload, OpenstaandeUploads


class _Klok:
    def __init__(self) -> None:
        self.nu = datetime(2026, 9, 4, 12, 0)

    def __call__(self) -> datetime:
        return self.nu

    def verder(self, minuten: int) -> None:
        self.nu += timedelta(minutes=minuten)


def _vb(naam: str = "a.pdf") -> Voorbereid:
    return Voorbereid([(naam, b"%PDF")], {0: "tekst"}, date(2024, 3, 12), "tekst")


def _sug() -> Suggestie:
    return Suggestie("Eneco B.V.", "rechtsvorm", ["factuur"])


def test_maak_en_haal() -> None:
    store = OpenstaandeUploads()
    upload = store.maak(_vb(), _sug())
    assert isinstance(upload, OpenstaandeUpload)
    assert re.fullmatch(r"[A-Za-z0-9_-]{8,64}", upload.token)
    assert store.haal(upload.token) is upload
    assert upload.voorbereid.bestanden == [("a.pdf", b"%PDF")]
    assert upload.suggestie.titel == "Eneco B.V."
    assert len(store) == 1


def test_onbekend_token_geeft_none() -> None:
    store = OpenstaandeUploads()
    assert store.haal("bestaatniet") is None
    store.maak(_vb(), _sug())
    assert store.haal("bestaatniet") is None


def test_tokens_uniek() -> None:
    store = OpenstaandeUploads(maximum=100)
    tokens = {store.maak(_vb(), _sug()).token for _ in range(50)}
    assert len(tokens) == 50


def test_verwijder_is_idempotent() -> None:
    store = OpenstaandeUploads()
    upload = store.maak(_vb(), _sug())
    store.verwijder(upload.token)
    assert store.haal(upload.token) is None
    assert len(store) == 0
    store.verwijder(upload.token)  # tweede keer: geen fout
    store.verwijder("nooit-bestaan")


def test_verloopt_na_ttl() -> None:
    klok = _Klok()
    store = OpenstaandeUploads(ttl=timedelta(minutes=60), nu=klok)
    upload = store.maak(_vb(), _sug())
    assert upload.aangemaakt == klok.nu
    klok.verder(59)
    assert store.haal(upload.token) is upload
    klok.verder(1)
    assert store.haal(upload.token) is None
    assert len(store) == 0  # verlopen upload is bij het ophalen opgeruimd


def test_maak_ruimt_verlopen_op() -> None:
    klok = _Klok()
    store = OpenstaandeUploads(ttl=timedelta(minutes=60), nu=klok)
    oud = store.maak(_vb(), _sug())
    klok.verder(61)
    nieuw = store.maak(_vb("b.pdf"), _sug())
    assert len(store) == 1
    assert store.haal(nieuw.token) is nieuw
    assert store.haal(oud.token) is None


def test_maximum_gooit_oudste_weg() -> None:
    klok = _Klok()
    store = OpenstaandeUploads(maximum=3, nu=klok)
    uploads = []
    for i in range(3):
        uploads.append(store.maak(_vb(f"{i}.pdf"), _sug()))
        klok.verder(1)
    assert len(store) == 3
    vierde = store.maak(_vb("3.pdf"), _sug())
    assert len(store) == 3
    assert store.haal(uploads[0].token) is None  # oudste weg
    assert store.haal(uploads[1].token) is uploads[1]
    assert store.haal(uploads[2].token) is uploads[2]
    assert store.haal(vierde.token) is vierde
