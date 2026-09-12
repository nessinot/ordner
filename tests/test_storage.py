from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from ordner.config import META_NAAM
from ordner.meta import lees_meta
from ordner.storage import Archief, OngeldigPad, PrullenbakItem

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
    doc = archief.maak_document("  Bon ", DATUM, omschrijving="Super", tags=["bon", "super"], nu=NU)
    meta = lees_meta(doc)
    assert meta.titel == "Bon"
    assert meta.documentdatum == DATUM
    assert meta.omschrijving == "Super"
    assert meta.tags == ["bon", "super"]
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
        ("C:\\Users\\gebruiker\\factuur.pdf", "factuur.pdf"),
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


def test_inbox_pad_geldig(archief: Archief) -> None:
    assert archief.inbox_pad("scan 0001.pdf") == archief.inbox_dir / "scan 0001.pdf"
    assert archief.inbox_pad("brief.docx") == archief.inbox_dir / "brief.docx"  # hoeft niet te bestaan


@pytest.mark.parametrize("naam", ["", ".", "..", ".tekst", ".verborgen.pdf", "a/b.pdf", "a\\b.pdf", "../meta.md", "_dubbel/x.pdf"])
def test_inbox_pad_ongeldig(archief: Archief, naam: str) -> None:
    with pytest.raises(OngeldigPad):
        archief.inbox_pad(naam)


def test_voeg_bestand_toe_registreert_sha256(archief: Archief) -> None:
    import hashlib

    doc = archief.maak_document("Bon", DATUM)
    assert lees_meta(doc).sha256 == {}
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF a")
    naam = archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF b")  # conflict -> a_2.pdf, eigen hash; nooit geweigerd
    meta = lees_meta(doc)
    assert naam == "a_2.pdf"
    assert meta.sha256 == {"a.pdf": hashlib.sha256(b"%PDF a").hexdigest(), "a_2.pdf": hashlib.sha256(b"%PDF b").hexdigest()}


# --- prullenbak: kijken en legen (pakket 19) --------------------------------------


def _vul_prullenbak(archief: Archief) -> tuple[Path, Path, Path]:
    """Twee weggegooide documenten (de tweede met conflict-suffix), een los bestand en een '.'-bestand."""
    doc1 = _doc(archief)
    archief.voeg_bestand_toe(doc1, "a.pdf", b"%PDF 1234")
    archief.voeg_bestand_toe(doc1, "b.jpg", b"jpg")
    (doc1 / "a.pdf.txt").write_text("tekst", encoding="utf-8")
    eerste = archief.naar_prullenbak(doc1)
    tweede = archief.naar_prullenbak(_doc(archief))
    los = archief.trash_dir / "los.pdf"
    los.write_bytes(b"%PDF los")
    (archief.trash_dir / ".DS_Store").write_bytes(b"x")
    return eerste, tweede, los


def test_prullenbak_inhoud_leeg(archief: Archief) -> None:
    assert archief.prullenbak_inhoud() == []
    assert archief.prullenbak_inhoud(met_grootte=False) == []


def test_prullenbak_inhoud(archief: Archief) -> None:
    eerste, tweede, los = _vul_prullenbak(archief)
    items = archief.prullenbak_inhoud()
    assert [i.naam for i in items] == sorted([eerste.name, tweede.name, "los.pdf"], reverse=True)
    assert ".DS_Store" not in [i.naam for i in items]
    per_naam = {i.naam: i for i in items}
    a = per_naam[eerste.name]
    assert a.is_map and a.titel == "WOZ-beschikking 2026" and a.documentdatum == DATUM and a.bestanden == 2
    assert a.grootte == sum(p.stat().st_size for p in eerste.iterdir())  # meta.md + a.pdf + b.jpg + a.pdf.txt
    assert per_naam[tweede.name].bestanden == 0
    l = per_naam["los.pdf"]
    assert l == PrullenbakItem("los.pdf", False, "los.pdf", None, 1, len(b"%PDF los"))
    assert all(i.grootte == 0 for i in archief.prullenbak_inhoud(met_grootte=False))


def test_prullenbak_inhoud_zonder_meta(archief: Archief) -> None:
    map = archief.trash_dir / "2025-01-01_samba"
    map.mkdir()
    (map / "scan.pdf").write_bytes(b"%PDF")
    (map / "scan.pdf.txt").write_text("t", encoding="utf-8")
    (map / "foto.jpg").write_bytes(b"jpg")
    (map / ".verborgen").write_bytes(b"x")
    (map / "sub").mkdir()
    (archief.trash_dir / "2025-02-02_kapot").mkdir()
    (archief.trash_dir / "2025-02-02_kapot" / META_NAAM).write_text("geen frontmatter", encoding="utf-8")
    items = {i.naam: i for i in archief.prullenbak_inhoud()}
    assert items["2025-01-01_samba"] == PrullenbakItem("2025-01-01_samba", True, "2025-01-01_samba", None, 2, 4 + 1 + 3 + 1)
    kapot = items["2025-02-02_kapot"]
    assert kapot.titel == "2025-02-02_kapot" and kapot.documentdatum is None and kapot.bestanden == 0


def test_prullenbak_pad_geldig(archief: Archief) -> None:
    eerste, _tweede, los = _vul_prullenbak(archief)
    assert archief.prullenbak_pad(eerste.name) == eerste
    assert archief.prullenbak_pad("los.pdf") == los


@pytest.mark.parametrize("naam", ["", ".", "..", "a/b", "a\\b", ".tekst", ".DS_Store", "bestaat-niet", "../_inbox", "..\\_inbox"])
def test_prullenbak_pad_ongeldig(archief: Archief, naam: str) -> None:
    _vul_prullenbak(archief)
    with pytest.raises(OngeldigPad):
        archief.prullenbak_pad(naam)


def test_prullenbak_pad_nooit_buiten_de_prullenbak(archief: Archief) -> None:
    """Een naam die naar buiten wijst (jaarmap, inbox, root) is nooit geldig, ook niet als het doel bestaat."""
    _doc(archief)
    for naam in ("../2026", "../2026/2026-03-01_woz-beschikking-2026", "../_inbox", "..", "../"):
        with pytest.raises(OngeldigPad):
            archief.prullenbak_pad(naam)
    assert (archief.root / "2026" / "2026-03-01_woz-beschikking-2026" / META_NAAM).exists()


def _symlink(bron: Path, doel: Path) -> None:
    import os

    try:
        os.symlink(doel, bron, target_is_directory=doel.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("geen symlink-rechten op dit platform")


def test_prullenbak_pad_symlink_wordt_niet_gevolgd(archief: Archief) -> None:
    doc = _doc(archief)
    link = archief.trash_dir / "link"
    _symlink(link, doc)
    pad = archief.prullenbak_pad("link")
    assert pad == link and pad.is_symlink()  # de link zelf, nooit het doel
    item = next(i for i in archief.prullenbak_inhoud() if i.naam == "link")
    assert not item.is_map and item.bestanden == 1  # geen walk door het doel


def test_verwijder_definitief_map_en_bestand(archief: Archief) -> None:
    eerste, tweede, los = _vul_prullenbak(archief)
    archief.verwijder_definitief(eerste.name)
    assert not eerste.exists() and tweede.exists() and los.exists()
    archief.verwijder_definitief("los.pdf")
    assert not los.exists()
    assert archief.trash_dir.is_dir()
    with pytest.raises(OngeldigPad):
        archief.verwijder_definitief(eerste.name)  # al weg


def test_verwijder_definitief_symlink_laat_doel_intact(archief: Archief) -> None:
    doc = _doc(archief)
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF")
    link = archief.trash_dir / "link"
    _symlink(link, doc)
    archief.verwijder_definitief("link")
    assert not link.exists() and not link.is_symlink()
    assert (doc / "a.pdf").exists() and (doc / META_NAAM).exists()
    assert archief.trash_dir.is_dir()


def test_leeg_prullenbak(archief: Archief) -> None:
    eerste, tweede, los = _vul_prullenbak(archief)
    assert archief.leeg_prullenbak() == (3, 0)
    assert not eerste.exists() and not tweede.exists() and not los.exists()
    assert (archief.trash_dir / ".DS_Store").exists()
    assert archief.trash_dir.is_dir()
    assert archief.prullenbak_inhoud() == []
    assert archief.leeg_prullenbak() == (0, 0)


def test_leeg_prullenbak_gaat_door_na_fout(archief: Archief, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    eerste, tweede, los = _vul_prullenbak(archief)
    echte_rmtree = shutil.rmtree

    def kapot(pad, *args, **kwargs):  # type: ignore[no-untyped-def]
        if Path(pad).name == eerste.name:
            raise OSError("alleen-lezen")
        return echte_rmtree(pad, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", kapot)
    assert archief.leeg_prullenbak() == (2, 1)
    assert eerste.exists() and not tweede.exists() and not los.exists()
    assert archief.trash_dir.is_dir()


# --- prullenbak: kijken in een document en terugzetten (pakket 20) ----------------


def test_prullenbak_document(archief: Archief) -> None:
    eerste, tweede, _los = _vul_prullenbak(archief)
    item = archief.prullenbak_document(eerste.name)
    assert item.naam == eerste.name and item.map == eerste
    assert item.meta is not None and item.meta.titel == "WOZ-beschikking 2026"
    assert item.bestanden == ["a.pdf", "b.jpg"]
    assert item.jaar == "2026"
    assert archief.prullenbak_document(tweede.name).jaar == "2026"  # ook met conflict-tijdstempel


def test_prullenbak_document_zonder_meta(archief: Archief) -> None:
    map = archief.trash_dir / "2024-05-05_kaal"
    map.mkdir()
    (map / "scan.pdf").write_bytes(b"pdf")
    (map / "scan.pdf.txt").write_text("x", encoding="utf-8")
    (map / ".stil").write_bytes(b"x")
    item = archief.prullenbak_document("2024-05-05_kaal")
    assert item.meta is None
    assert item.bestanden == ["scan.pdf"]
    assert item.jaar == "2024"


def test_prullenbak_document_jaar_uit_meta_of_geen(archief: Archief) -> None:
    doc = _doc(archief)
    doel = archief.trash_dir / "hernoemd-via-samba"
    doc.rename(doel)
    assert archief.prullenbak_document("hernoemd-via-samba").jaar == "2026"  # meta.documentdatum
    (archief.trash_dir / "leeg").mkdir()
    assert archief.prullenbak_document("leeg").jaar is None
    with pytest.raises(OngeldigPad):
        archief.herstel_uit_prullenbak("leeg")


@pytest.mark.parametrize("naam", ["los.pdf", "bestaat-niet", "", "..", ".DS_Store", "a/b"])
def test_prullenbak_document_ongeldig(archief: Archief, naam: str) -> None:
    _vul_prullenbak(archief)
    with pytest.raises(OngeldigPad):
        archief.prullenbak_document(naam)


def test_prullenbak_bestand(archief: Archief) -> None:
    eerste, _tweede, _los = _vul_prullenbak(archief)
    assert archief.prullenbak_bestand(eerste.name, "a.pdf") == eerste / "a.pdf"
    assert archief.prullenbak_bestand(eerste.name, "a.pdf.txt") == eerste / "a.pdf.txt"
    (archief.root / "buiten.pdf").write_bytes(b"x")
    for bestand in ("", ".", "..", "meta.md" + "/", "nietbestaand.pdf", "../los.pdf", "..\\..\\buiten.pdf", ".tmp-x", "sub/a.pdf"):
        with pytest.raises(OngeldigPad):
            archief.prullenbak_bestand(eerste.name, bestand)
    with pytest.raises(OngeldigPad):
        archief.prullenbak_bestand("los.pdf", "x")
    # een submap is geen bestand
    (eerste / "sub").mkdir()
    with pytest.raises(OngeldigPad):
        archief.prullenbak_bestand(eerste.name, "sub")


def test_herstel_uit_prullenbak(archief: Archief) -> None:
    eerste, tweede, _los = _vul_prullenbak(archief)
    doc = archief.herstel_uit_prullenbak(eerste.name)
    assert doc == archief.root / "2026" / "2026-03-01_woz-beschikking-2026"
    assert (doc / "a.pdf").read_bytes() == b"%PDF 1234" and (doc / "a.pdf.txt").exists() and (doc / META_NAAM).exists()
    assert not eerste.exists() and archief.trash_dir.is_dir()
    assert archief.relatief(doc) in {archief.relatief(m) for m in archief.documentmappen()}
    # de tweede (met tijdstempel): gestript, naam bezet -> _2
    doc2 = archief.herstel_uit_prullenbak(tweede.name)
    assert doc2 == archief.root / "2026" / "2026-03-01_woz-beschikking-2026_2"
    assert not tweede.exists()


def test_herstel_uit_prullenbak_maakt_jaarmap(archief: Archief) -> None:
    doc = archief.maak_document("Oud", date(2019, 1, 2))
    weg = archief.naar_prullenbak(doc)
    (archief.root / "2019").rmdir()
    assert archief.herstel_uit_prullenbak(weg.name) == archief.root / "2019" / "2019-01-02_oud"


def test_herstel_uit_prullenbak_ongeldig(archief: Archief) -> None:
    _vul_prullenbak(archief)
    for naam in ("los.pdf", "bestaat-niet", "..", ""):
        with pytest.raises(OngeldigPad):
            archief.herstel_uit_prullenbak(naam)
