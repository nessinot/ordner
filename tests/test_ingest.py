"""Tests voor ordner.ingest (pakket 14): documenten aanmaken met de datum uit de tekst."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ordner.ingest import maak_document_uit_bestanden, maak_tekstlezer
from ordner.meta import lees_meta
from ordner.storage import Archief
from tests.conftest import CmdMock

VANDAAG = date(2026, 9, 4)
_PDF = b"%PDF-1.4 x"


class _Queue:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def __call__(self, doc: Path, naam: str) -> None:
        # queuen mag pas als het bestand en de volledige meta.md op schijf staan (worker draait gelijktijdig)
        assert (doc / naam).exists()
        assert naam in lees_meta(doc).bestanden
        self.items.append((doc.name, naam))


def _lezer(teksten: dict[str, str | None]):  # type: ignore[no-untyped-def]
    """Nep-tekstlezer: kiest op bestandsnaam (zonder het tempprefix)."""
    gelezen: list[str] = []

    def lees(pad: Path) -> str | None:
        naam = pad.name.split("_", 1)[1]
        gelezen.append(naam)
        return teksten.get(naam)

    lees.gelezen = gelezen  # type: ignore[attr-defined]
    return lees


def test_met_datum_van_gebruiker_leest_niet_vooraf(archief: Archief) -> None:
    q = _Queue()
    lezer = _lezer({"a.pdf": "Factuurdatum: 01-01-2020"})
    doc = maak_document_uit_bestanden(
        archief, "Test", [("a.pdf", _PDF)], documentdatum=date(2026, 3, 1), lees_tekst=lezer, queue_fn=q, vandaag=VANDAAG
    )
    assert doc.name == "2026-03-01_test"
    meta = lees_meta(doc)
    assert meta.datumbron == "gebruiker"
    assert meta.ocr == "pending"
    assert lezer.gelezen == []  # type: ignore[attr-defined]
    assert q.items == [("2026-03-01_test", "a.pdf")]
    assert not (doc / "a.pdf.txt").exists()


def test_zonder_datum_haalt_datum_uit_tekst(archief: Archief) -> None:
    q = _Queue()
    lezer = _lezer({"factuur.pdf": "Bedrijf BV\nFactuurdatum: 12-03-2024\nVervaldatum: 12-04-2024"})
    doc = maak_document_uit_bestanden(
        archief, "Energie", [("factuur.pdf", _PDF)], documentdatum=None, lees_tekst=lezer, queue_fn=q, vandaag=VANDAAG
    )
    assert doc.parent.name == "2024"
    assert doc.name == "2024-03-12_energie"
    meta = lees_meta(doc)
    assert meta.documentdatum == date(2024, 3, 12)
    assert meta.datumbron == "tekst"
    assert meta.ocr == "done"
    assert meta.bestanden == ["factuur.pdf"]
    assert (doc / "factuur.pdf.txt").read_text(encoding="utf-8").startswith("Bedrijf BV")
    assert q.items == []  # tekst is al geschreven, niets te queuen


def test_zonder_datum_en_zonder_treffer_wordt_vandaag(archief: Archief) -> None:
    q = _Queue()
    lezer = _lezer({"scan.jpg": "onleesbare bon zonder datumregel"})
    doc = maak_document_uit_bestanden(
        archief, "Bon", [("scan.jpg", b"x")], documentdatum=None, lees_tekst=lezer, queue_fn=q, vandaag=VANDAAG
    )
    assert doc.name == "2026-09-04_bon"
    meta = lees_meta(doc)
    assert meta.datumbron == "upload"
    assert meta.ocr == "done"
    assert (doc / "scan.jpg.txt").exists()
    assert q.items == []


def test_eerste_bestand_met_datum_wint_en_alle_teksten_worden_geschreven(archief: Archief) -> None:
    q = _Queue()
    lezer = _lezer({"1.pdf": "geen datum hier", "2.pdf": "Datum: 05-05-2021", "3.pdf": "Factuurdatum: 06-06-2022"})
    doc = maak_document_uit_bestanden(
        archief,
        "Mix",
        [("1.pdf", _PDF), ("2.pdf", _PDF), ("3.pdf", _PDF), ("brief.docx", b"x")],
        documentdatum=None,
        lees_tekst=lezer,
        queue_fn=q,
        vandaag=VANDAAG,
    )
    assert doc.name == "2021-05-05_mix"  # het eerste bestand met een treffer, ongeacht prioriteit over bestanden heen
    assert lees_meta(doc).bestanden == ["1.pdf", "2.pdf", "3.pdf", "brief.docx"]
    for naam in ("1.pdf", "2.pdf", "3.pdf"):
        assert (doc / f"{naam}.txt").exists()
    assert not (doc / "brief.docx.txt").exists()
    assert lees_meta(doc).ocr == "done"


def test_mislukte_extractie_gaat_naar_queue(archief: Archief) -> None:
    q = _Queue()
    lezer = _lezer({"a.pdf": None, "b.pdf": "Datum: 01-02-2023"})
    doc = maak_document_uit_bestanden(
        archief, "Half", [("a.pdf", _PDF), ("b.pdf", _PDF)], documentdatum=None, lees_tekst=lezer, queue_fn=q, vandaag=VANDAAG
    )
    assert doc.name == "2023-02-01_half"
    meta = lees_meta(doc)
    assert meta.datumbron == "tekst"
    assert meta.ocr == "pending"  # a.pdf heeft nog geen .txt
    assert q.items == [("2023-02-01_half", "a.pdf")]
    assert (doc / "b.pdf.txt").exists()


def test_zonder_tekstlezer_gedraagt_zich_als_vroeger(archief: Archief) -> None:
    q = _Queue()
    doc = maak_document_uit_bestanden(
        archief, "Oud", [("a.pdf", _PDF)], documentdatum=None, lees_tekst=None, queue_fn=q, vandaag=VANDAAG
    )
    assert doc.name == "2026-09-04_oud"
    assert lees_meta(doc).datumbron == "upload"
    assert q.items == [("2026-09-04_oud", "a.pdf")]


def test_zonder_bestanden(archief: Archief) -> None:
    q = _Queue()
    lezer = _lezer({})
    doc = maak_document_uit_bestanden(
        archief, "Leeg", [], documentdatum=None, lees_tekst=lezer, queue_fn=q, vandaag=VANDAAG
    )
    assert doc.name == "2026-09-04_leeg"
    assert lees_meta(doc).ocr == "done"
    assert lezer.gelezen == []  # type: ignore[attr-defined]


def test_tempbestand_houdt_extensie(archief: Archief) -> None:
    """De extractie dispatcht op extensie; het tempbestand moet die dus behouden."""
    gezien: list[str] = []

    def lees(pad: Path) -> str | None:
        gezien.append(pad.suffix)
        assert pad.exists()
        return None

    maak_document_uit_bestanden(
        archief, "Ext", [("Foto.HEIC", b"x"), ("scan.PDF", b"x")], documentdatum=None, lees_tekst=lees, queue_fn=_Queue(), vandaag=VANDAAG
    )
    assert gezien == [".HEIC", ".PDF"]


def test_maak_tekstlezer_draait_extractie_synchroon(tmp_path: Path, mock_cmd: CmdMock) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"Factuurdatum: 01-01-2024" + b" x" * 30)
    pad = tmp_path / "f.pdf"
    pad.write_bytes(_PDF)
    lees = maak_tekstlezer("nld")
    tekst = lees(pad)
    assert tekst is not None and tekst.startswith("Factuurdatum: 01-01-2024")
    assert mock_cmd.calls[1][0] == "pdftotext"


def test_maak_tekstlezer_geeft_none_bij_fout(tmp_path: Path, mock_cmd: CmdMock) -> None:
    pad = tmp_path / "f.pdf"
    pad.write_bytes(_PDF)
    assert maak_tekstlezer("nld")(pad) is None  # pdfinfo/pdftotext niet geregistreerd -> ExtractieFout
    assert maak_tekstlezer("nld")(tmp_path / "brief.docx") is None


@pytest.mark.parametrize("naam", ["a.pdf", "b.PNG"])
def test_lezer_krijgt_alleen_extraheerbare_bestanden(archief: Archief, naam: str) -> None:
    lezer = _lezer({})
    maak_document_uit_bestanden(
        archief, "X", [(naam, b"x"), ("c.txt", b"x")], documentdatum=None, lees_tekst=lezer, queue_fn=_Queue(), vandaag=VANDAAG
    )
    assert lezer.gelezen == [naam]  # type: ignore[attr-defined]
