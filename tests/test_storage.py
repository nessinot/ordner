from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from ordner.config import META_NAAM
from ordner.meta import lees_meta
from ordner.storage import Archief, OngeldigPad

DATUM = date(2026, 3, 1)
NU = datetime(2026, 9, 3, 14, 12, 33, 456)


def _doc(archief: Archief, titel: str = "WOZ-beschikking 2026") -> Path:
    return archief.maak_document(titel, DATUM, nu=NU)


# --- __init__ -------------------------------------------------------------


def test_init_maakt_mappen(tmp_path: Path) -> None:
    a = Archief(tmp_path / "nieuw" / "archief")
    assert a.root.is_dir()
    assert a.inbox_dir == a.root / "_inbox" and a.inbox_dir.is_dir()
    assert a.trash_dir == a.root / "_prullenbak" and a.trash_dir.is_dir()
    assert a.root.is_absolute()


# --- maak_document --------------------------------------------------------


def test_maak_document_mapnaam_en_collision(archief: Archief) -> None:
    d1 = _doc(archief)
    d2 = _doc(archief)
    d3 = _doc(archief)
    assert archief.relatief(d1) == "2026/2026-03-01_woz-beschikking-2026"
    assert archief.relatief(d2) == "2026/2026-03-01_woz-beschikking-2026_2"
    assert archief.relatief(d3) == "2026/2026-03-01_woz-beschikking-2026_3"
    assert d1.is_absolute()


def test_maak_document_meta(archief: Archief) -> None:
    doc = archief.maak_document("  Bon ", DATUM, omschrijving="AH", tags=["bon", "ah"], nu=NU)
    meta = lees_meta(doc)
    assert meta.titel == "Bon"
    assert meta.documentdatum == DATUM
    assert meta.omschrijving == "AH"
    assert meta.tags == ["bon", "ah"]
    assert meta.bestanden == []
    assert meta.ocr == "done"
    assert meta.uploaddatum == datetime(2026, 9, 3, 14, 12)
    assert "uploaddatum: '2026-09-03T14:12'" in (doc / META_NAAM).read_text(encoding="utf-8")


def test_maak_document_datumbron(archief: Archief) -> None:
    assert lees_meta(archief.maak_document("A", date(2026, 3, 1))).datumbron == "gebruiker"
    assert lees_meta(archief.maak_document("B", date(2026, 3, 1), datumbron="tekst")).datumbron == "tekst"


def test_maak_document_zonder_nu(archief: Archief) -> None:
    voor = datetime.now().replace(second=0, microsecond=0)
    meta = lees_meta(archief.maak_document("x", DATUM))
    assert meta.uploaddatum.second == 0 and meta.uploaddatum.microsecond == 0
    assert meta.uploaddatum >= voor


# --- voeg_bestand_toe -----------------------------------------------------


@pytest.mark.parametrize(
    ("invoer", "verwacht"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\bas\\factuur.pdf", "factuur.pdf"),
        ("foto (1).JPG", "foto _1_.JPG"),
        (".env", "_env"),
        ("", "bestand"),
        ("meta.md", "meta_1.md"),
        ("META.MD", "meta_1.md"),
        ("Café ü.pdf", "Caf_ _.pdf"),
    ],
)
def test_voeg_bestand_toe_saneert(archief: Archief, invoer: str, verwacht: str) -> None:
    doc = _doc(archief)
    assert archief.voeg_bestand_toe(doc, invoer, b"x") == verwacht
    assert (doc / verwacht).read_bytes() == b"x"
    assert lees_meta(doc).bestanden == [verwacht]
    assert not any(p.name.startswith(".tmp-") for p in doc.iterdir())


def test_voeg_bestand_toe_conflict(archief: Archief) -> None:
    doc = _doc(archief)
    assert archief.voeg_bestand_toe(doc, "a.pdf", b"1") == "a.pdf"
    assert archief.voeg_bestand_toe(doc, "a.pdf", b"2") == "a_2.pdf"
    assert archief.voeg_bestand_toe(doc, "a.pdf", b"3") == "a_3.pdf"
    assert (doc / "a.pdf").read_bytes() == b"1"
    assert (doc / "a_2.pdf").read_bytes() == b"2"
    assert lees_meta(doc).bestanden == ["a.pdf", "a_2.pdf", "a_3.pdf"]


def test_voeg_bestand_toe_txt_botsing(archief: Archief) -> None:
    doc = _doc(archief)
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF")
    assert archief.voeg_bestand_toe(doc, "a.pdf.txt", b"tekst") == "a.pdf_2.txt"
    assert not (doc / "a.pdf.txt").exists()


def test_voeg_bestand_toe_ocr_pending_bij_pdf(archief: Archief) -> None:
    doc = _doc(archief)
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF")
    assert lees_meta(doc).ocr == "pending"


def test_voeg_bestand_toe_ocr_done_bij_docx(archief: Archief) -> None:
    doc = _doc(archief)
    archief.voeg_bestand_toe(doc, "a.docx", b"x")
    assert lees_meta(doc).ocr == "done"


def test_voeg_bestand_toe_failed_wordt_pending(archief: Archief) -> None:
    doc = _doc(archief)
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF")
    from ordner.meta import schrijf_meta

    meta = lees_meta(doc)
    meta.ocr = "failed"
    schrijf_meta(doc, meta)
    archief.voeg_bestand_toe(doc, "b.pdf", b"%PDF")
    assert lees_meta(doc).ocr == "pending"


def test_voeg_bestand_toe_failed_blijft_failed_bij_docx(archief: Archief) -> None:
    doc = _doc(archief)
    from ordner.meta import schrijf_meta

    meta = lees_meta(doc)
    meta.ocr = "failed"
    schrijf_meta(doc, meta)
    archief.voeg_bestand_toe(doc, "a.docx", b"x")
    assert lees_meta(doc).ocr == "failed"


# --- naar_prullenbak ------------------------------------------------------


def test_naar_prullenbak(archief: Archief) -> None:
    doc = _doc(archief)
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF")
    naam = doc.name
    doel = archief.naar_prullenbak(doc)
    assert doel == archief.trash_dir / naam
    assert (doel / "a.pdf").exists() and (doel / META_NAAM).exists()
    assert not doc.exists()
    assert (archief.root / "2026").is_dir()  # lege jaarmap blijft staan


def test_naar_prullenbak_conflict(archief: Archief) -> None:
    eerste = archief.naar_prullenbak(_doc(archief))
    tweede = archief.naar_prullenbak(_doc(archief))
    assert eerste.name == "2026-03-01_woz-beschikking-2026"
    assert tweede.name.startswith("2026-03-01_woz-beschikking-2026_")
    assert len(tweede.name) == len(eerste.name) + 1 + 15  # _JJJJMMDD-HHMMSS
    assert eerste.is_dir() and tweede.is_dir()
    assert archief.documentmappen() == []


# --- documentmappen / relatief --------------------------------------------


def test_documentmappen(archief: Archief) -> None:
    d2 = archief.maak_document("Later", date(2026, 5, 1))
    d1 = archief.maak_document("Eerder", date(2025, 12, 31))
    (archief.inbox_dir / "los.pdf").write_bytes(b"x")
    for extra in ("_prullenbak/2026-01-01_weg", ".hidden", "abc/2026-01-01_x", "2026/_intern", "2026/.stil"):
        (archief.root / extra).mkdir(parents=True, exist_ok=True)
        (archief.root / extra / META_NAAM).write_text("---\ntitel: x\ndocumentdatum: 2026-01-01\n---\n", encoding="utf-8")
    (archief.root / "2026" / "2026-02-02_zonder-meta").mkdir()
    assert archief.documentmappen() == [d1, d2]


def test_relatief(archief: Archief) -> None:
    doc = _doc(archief)
    assert archief.relatief(doc) == "2026/2026-03-01_woz-beschikking-2026"
    assert "\\" not in archief.relatief(doc)


# --- veilig_pad -----------------------------------------------------------


def test_veilig_pad_geldig(archief: Archief) -> None:
    doc = _doc(archief)
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF")
    assert archief.veilig_pad("2026", doc.name) == doc
    assert archief.veilig_pad("2026", doc.name, "a.pdf") == doc / "a.pdf"


@pytest.mark.parametrize(
    ("jaar", "map", "naam"),
    [
        ("2026", "..", None),
        ("..", "2026-03-01_woz-beschikking-2026", None),
        ("2026", "2026-03-01_woz-beschikking-2026", ".."),
        ("2026", "a/b", None),
        ("2026", "a\\b", None),
        ("2026", "2026-03-01_woz-beschikking-2026", "../meta.md"),
        ("2026", "2026-03-01_woz-beschikking-2026", "..\\meta.md"),
        ("", "2026-03-01_woz-beschikking-2026", None),
        ("2026", "", None),
        ("2026", "2026-03-01_woz-beschikking-2026", ""),
        ("2026", ".", None),
        ("20x6", "2026-03-01_woz-beschikking-2026", None),
        ("12026", "2026-03-01_woz-beschikking-2026", None),
        ("2026", "2026-03-01_woz-beschikking-2026", "bestaat-niet.pdf"),
        ("2026", "bestaat-niet", None),
        ("2025", "2026-03-01_woz-beschikking-2026", None),
    ],
)
def test_veilig_pad_ongeldig(archief: Archief, jaar: str, map: str, naam: str | None) -> None:
    _doc(archief)
    with pytest.raises(OngeldigPad):
        archief.veilig_pad(jaar, map, naam)
