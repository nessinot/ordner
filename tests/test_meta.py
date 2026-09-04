from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from ordner.config import META_NAAM
from ordner.meta import (
    Meta,
    MetaFout,
    bepaal_ocr_status,
    is_extraheerbaar,
    lees_meta,
    parse_meta,
    render_meta,
    schrijf_meta,
    txt_pad,
)


def _volle_meta() -> Meta:
    return Meta(
        titel="WOZ-beschikking 2026 — Café Zürich",
        documentdatum=date(2026, 3, 1),
        uploaddatum=datetime(2026, 9, 3, 14, 12),
        omschrijving="Gemeente, waarde peildatum 1-1-2025",
        tags=["woz", "gemeente"],
        bestanden=["beschikking.pdf", "foto.heic"],
        ocr="pending",
        notities="Eerste regel.\n\nDerde regel met ünïcode.\n",
    )


def _minimale_meta() -> Meta:
    return Meta(
        titel="Bon",
        documentdatum=date(2026, 1, 15),
        uploaddatum=datetime(2026, 1, 15, 9, 0),
    )


# --- roundtrip ------------------------------------------------------------


def test_roundtrip_vol() -> None:
    m = _volle_meta()
    assert parse_meta(render_meta(m)) == m


def test_roundtrip_minimaal() -> None:
    m = _minimale_meta()
    tekst = render_meta(m)
    assert "tags: []" in tekst
    assert "bestanden: []" in tekst
    assert tekst.endswith("---\n")
    assert parse_meta(tekst) == m


# --- rendering ------------------------------------------------------------


def test_render_formaat_en_volgorde() -> None:
    tekst = render_meta(_volle_meta())
    assert tekst.startswith("---\ntitel:")
    regels = tekst.split("\n")
    keys = [r.split(":")[0] for r in regels[1:9]]
    assert keys == ["titel", "omschrijving", "documentdatum", "uploaddatum", "tags", "bestanden", "ocr", "datumbron"]
    assert regels[9] == "---"
    assert "documentdatum: 2026-03-01" in tekst
    assert "uploaddatum: '2026-09-03T14:12'" in tekst
    assert "tags: [woz, gemeente]" in tekst
    assert "bestanden: [beschikking.pdf, foto.heic]" in tekst
    assert "ocr: pending" in tekst
    assert tekst.endswith("---\nEerste regel.\n\nDerde regel met ünïcode.\n")


def test_render_voorbeeld_uit_contract() -> None:
    m = Meta(
        titel="WOZ-beschikking 2026",
        documentdatum=date(2026, 3, 1),
        uploaddatum=datetime(2026, 9, 3, 14, 12),
        tags=["woz", "gemeente"],
        bestanden=["beschikking.pdf"],
    )
    verwacht = (
        "---\n"
        "titel: WOZ-beschikking 2026\n"
        "omschrijving: ''\n"
        "documentdatum: 2026-03-01\n"
        "uploaddatum: '2026-09-03T14:12'\n"
        "tags: [woz, gemeente]\n"
        "bestanden: [beschikking.pdf]\n"
        "ocr: done\n"
        "datumbron: gebruiker\n"
        "---\n"
    )
    assert render_meta(m) == verwacht


def test_datumbron_parsen_en_default() -> None:
    m = _minimale_meta()
    assert m.datumbron == "gebruiker"
    m.datumbron = "tekst"
    assert parse_meta(render_meta(m)).datumbron == "tekst"
    # oude meta.md zonder veld en een onbekende waarde -> gebruiker
    zonder = render_meta(_minimale_meta()).replace("datumbron: gebruiker\n", "")
    assert "datumbron" not in zonder
    assert parse_meta(zonder).datumbron == "gebruiker"
    assert parse_meta(zonder.replace("ocr: done", "ocr: done\ndatumbron: raar")).datumbron == "gebruiker"


# --- parse_meta -----------------------------------------------------------


def test_parse_geen_frontmatter() -> None:
    with pytest.raises(MetaFout, match="frontmatter"):
        parse_meta("titel: x\ndocumentdatum: 2026-01-01\n")


def test_parse_frontmatter_niet_gesloten() -> None:
    with pytest.raises(MetaFout, match="frontmatter"):
        parse_meta("---\ntitel: x\ndocumentdatum: 2026-01-01\n")


def test_parse_geen_titel() -> None:
    with pytest.raises(MetaFout, match="titel"):
        parse_meta("---\ndocumentdatum: 2026-01-01\n---\n")
    with pytest.raises(MetaFout, match="titel"):
        parse_meta("---\ntitel: '   '\ndocumentdatum: 2026-01-01\n---\n")


def test_parse_geen_documentdatum() -> None:
    with pytest.raises(MetaFout, match="documentdatum"):
        parse_meta("---\ntitel: x\n---\n")


def test_parse_datum_als_string() -> None:
    m = parse_meta("---\ntitel: x\ndocumentdatum: '2026-03-01'\n---\n")
    assert m.documentdatum == date(2026, 3, 1)


def test_parse_ongeldige_datum() -> None:
    with pytest.raises(MetaFout, match="documentdatum"):
        parse_meta("---\ntitel: x\ndocumentdatum: gisteren\n---\n")


def test_parse_defaults() -> None:
    m = parse_meta("---\ntitel: x\ndocumentdatum: 2026-03-01\n---\n")
    assert m.ocr == "done"
    assert m.tags == []
    assert m.bestanden == []
    assert m.omschrijving == ""
    assert m.notities == ""
    assert m.uploaddatum == datetime(2026, 3, 1, 0, 0)


def test_parse_null_waarden() -> None:
    m = parse_meta(
        "---\ntitel: x\ndocumentdatum: 2026-03-01\nomschrijving:\ntags:\nbestanden:\nocr:\n---\n"
    )
    assert m.omschrijving == ""
    assert m.tags == []
    assert m.bestanden == []
    assert m.ocr == "done"


def test_parse_ongeldige_ocr_wordt_done() -> None:
    m = parse_meta("---\ntitel: x\ndocumentdatum: 2026-03-01\nocr: onzin\n---\n")
    assert m.ocr == "done"


def test_parse_uploaddatum_met_seconden() -> None:
    m = parse_meta("---\ntitel: x\ndocumentdatum: 2026-03-01\nuploaddatum: '2026-09-03T14:12:33'\n---\n")
    assert m.uploaddatum == datetime(2026, 9, 3, 14, 12)


def test_parse_uploaddatum_ongequote() -> None:
    # PyYAML parseert een ongequote ISO-timestamp zelf als datetime.
    m = parse_meta("---\ntitel: x\ndocumentdatum: 2026-03-01\nuploaddatum: 2026-09-03 14:12:00\n---\n")
    assert m.uploaddatum == datetime(2026, 9, 3, 14, 12)


def test_parse_notities_en_crlf() -> None:
    m = parse_meta("---\r\ntitel: x\r\ndocumentdatum: 2026-03-01\r\n---\r\nregel 1\r\n\r\nregel 2\r\n")
    assert m.notities == "regel 1\n\nregel 2\n"


def test_parse_notities_met_streepjes_in_body() -> None:
    tekst = "---\ntitel: x\ndocumentdatum: 2026-03-01\n---\nnotitie\n---\nnog meer\n"
    m = parse_meta(tekst)
    assert m.notities == "notitie\n---\nnog meer\n"


def test_parse_elementen_naar_str() -> None:
    m = parse_meta("---\ntitel: x\ndocumentdatum: 2026-03-01\ntags: [2026, woz]\n---\n")
    assert m.tags == ["2026", "woz"]


# --- lees_meta / schrijf_meta ---------------------------------------------


def test_schrijf_en_lees(tmp_path: Path) -> None:
    m = _volle_meta()
    schrijf_meta(tmp_path, m)
    assert (tmp_path / META_NAAM).exists()
    assert not (tmp_path / ".meta.md.tmp").exists()
    assert lees_meta(tmp_path) == m
    # geen \r\n op schijf, ook op Windows
    assert b"\r\n" not in (tmp_path / META_NAAM).read_bytes()


def test_schrijf_overschrijft(tmp_path: Path) -> None:
    schrijf_meta(tmp_path, _minimale_meta())
    m = _volle_meta()
    schrijf_meta(tmp_path, m)
    assert lees_meta(tmp_path) == m


def test_lees_ontbrekend(tmp_path: Path) -> None:
    with pytest.raises(MetaFout):
        lees_meta(tmp_path)


def test_lees_ongeldig(tmp_path: Path) -> None:
    (tmp_path / META_NAAM).write_text("geen frontmatter", encoding="utf-8")
    with pytest.raises(MetaFout, match="frontmatter"):
        lees_meta(tmp_path)


# --- hulpfuncties ---------------------------------------------------------


def test_txt_pad() -> None:
    assert txt_pad(Path("map") / "factuur.pdf") == Path("map") / "factuur.pdf.txt"
    assert txt_pad(Path("map") / "foto.HEIC") == Path("map") / "foto.HEIC.txt"


@pytest.mark.parametrize(
    ("naam", "verwacht"),
    [
        ("a.pdf", True),
        ("a.PDF", True),
        ("a.jpg", True),
        ("a.jpeg", True),
        ("a.png", True),
        ("a.HEIC", True),
        ("a.docx", False),
        ("a.txt", False),
        ("a", False),
        ("a.pdf.txt", False),
    ],
)
def test_is_extraheerbaar(naam: str, verwacht: bool) -> None:
    assert is_extraheerbaar(naam) is verwacht


def test_bepaal_ocr_status_failed_blijft_failed(tmp_path: Path) -> None:
    m = _minimale_meta()
    m.ocr = "failed"
    assert bepaal_ocr_status(tmp_path, m) == "failed"


def test_bepaal_ocr_status_pending(tmp_path: Path) -> None:
    m = _minimale_meta()
    m.bestanden = ["a.pdf"]
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    assert bepaal_ocr_status(tmp_path, m) == "pending"


def test_bepaal_ocr_status_done_met_txt(tmp_path: Path) -> None:
    m = _minimale_meta()
    m.bestanden = ["a.pdf"]
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "a.pdf.txt").write_text("tekst", encoding="utf-8")
    assert bepaal_ocr_status(tmp_path, m) == "done"


def test_bepaal_ocr_status_alleen_niet_extraheerbaar(tmp_path: Path) -> None:
    m = _minimale_meta()
    m.bestanden = ["a.docx"]
    (tmp_path / "a.docx").write_bytes(b"x")
    assert bepaal_ocr_status(tmp_path, m) == "done"


def test_bepaal_ocr_status_geen_bestanden(tmp_path: Path) -> None:
    assert bepaal_ocr_status(tmp_path, _minimale_meta()) == "done"


def test_bepaal_ocr_status_pending_reset_vanuit_pending(tmp_path: Path) -> None:
    m = _minimale_meta()
    m.ocr = "pending"
    m.bestanden = ["a.jpg"]
    (tmp_path / "a.jpg.txt").write_text("tekst", encoding="utf-8")
    assert bepaal_ocr_status(tmp_path, m) == "done"
