from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ordner import extract
from ordner.extract import (
    ExtractieFout,
    _normaliseer,
    extract_afbeelding,
    extract_bestand,
    extract_pdf,
    run_cmd,
)

if TYPE_CHECKING:
    from tests.conftest import CmdMock

TALEN = "nld+eng"


def _programmas(mock: CmdMock) -> list[str]:
    return [call[0] for call in mock.calls]


def _sidecar_handler(tekst: str):
    def handler(args: list[str]) -> tuple[int, bytes, bytes]:
        sidecar = Path(args[args.index("--sidecar") + 1])
        sidecar.write_bytes(tekst.encode("utf-8"))  # bytes, anders vertaalt Windows \n naar \r\n
        return 0, b"", b""

    return handler


# --- extract_pdf ----------------------------------------------------------


async def test_pdf_met_tekstlaag_geen_ocr(mock_cmd: CmdMock, tmp_path: Path) -> None:
    tekst = "a" * 200
    mock_cmd.register("pdfinfo", stdout=b"Title: x\nPages:          2\n")
    mock_cmd.register("pdftotext", stdout=tekst.encode())
    pdf = tmp_path / "factuur.pdf"
    pdf.write_bytes(b"%PDF")

    assert await extract_pdf(pdf, TALEN) == tekst
    assert "ocrmypdf" not in _programmas(mock_cmd)
    assert mock_cmd.calls[1] == ["pdftotext", "-layout", str(pdf), "-"]


async def test_pdf_te_weinig_tekst_valt_terug_op_ocrmypdf(mock_cmd: CmdMock, tmp_path: Path) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 3\n")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    mock_cmd.register("ocrmypdf", handler=_sidecar_handler("Gescande tekst\r\nregel 2"))
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF")

    resultaat = await extract_pdf(pdf, TALEN)

    assert resultaat == "Gescande tekst\nregel 2"
    ocr = next(call for call in mock_cmd.calls if call[0] == "ocrmypdf")
    assert "--force-ocr" in ocr
    assert ocr[ocr.index("-l") + 1] == TALEN
    assert "--sidecar" in ocr
    assert ocr[-2] == str(pdf)
    assert ocr[-1].endswith("uit.pdf")


async def test_pdf_zonder_pages_regel_drempel_50(mock_cmd: CmdMock, tmp_path: Path) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Title: geen paginatelling\n")
    mock_cmd.register("pdftotext", stdout=b"y" * 60)
    pdf = tmp_path / "kort.pdf"
    pdf.write_bytes(b"%PDF")

    assert await extract_pdf(pdf, TALEN) == "y" * 60
    assert "ocrmypdf" not in _programmas(mock_cmd)


async def test_pdf_ocrmypdf_faalt(mock_cmd: CmdMock, tmp_path: Path) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1\n")
    mock_cmd.register("pdftotext", stdout=b"")
    mock_cmd.register("ocrmypdf", rc=1, stderr=b"InputFileError: bestand is versleuteld")
    pdf = tmp_path / "kapot.pdf"
    pdf.write_bytes(b"%PDF")

    with pytest.raises(ExtractieFout) as excinfo:
        await extract_pdf(pdf, TALEN)
    assert "versleuteld" in str(excinfo.value)
    assert "(1)" in str(excinfo.value)


async def test_pdf_pdftotext_faalt_probeert_ocr(mock_cmd: CmdMock, tmp_path: Path) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1\n")
    mock_cmd.register("pdftotext", rc=1, stdout=b"z" * 500, stderr=b"Syntax Error")
    mock_cmd.register("ocrmypdf", handler=_sidecar_handler("via ocr"))
    pdf = tmp_path / "raar.pdf"
    pdf.write_bytes(b"%PDF")

    assert await extract_pdf(pdf, TALEN) == "via ocr"
    assert "ocrmypdf" in _programmas(mock_cmd)


async def test_pdf_ocrmypdf_zonder_sidecar(mock_cmd: CmdMock, tmp_path: Path) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1\n")
    mock_cmd.register("pdftotext", stdout=b"")
    mock_cmd.register("ocrmypdf", rc=0)
    pdf = tmp_path / "leeg.pdf"
    pdf.write_bytes(b"%PDF")

    with pytest.raises(ExtractieFout, match="sidecar"):
        await extract_pdf(pdf, TALEN)


# --- extract_afbeelding ---------------------------------------------------


async def test_jpg_via_tesseract(mock_cmd: CmdMock, tmp_path: Path) -> None:
    mock_cmd.register("tesseract", stdout=b"Bonnetje\ntotaal 12,50  \n")
    jpg = tmp_path / "bon.jpg"
    jpg.write_bytes(b"\xff\xd8")

    assert await extract_afbeelding(jpg, TALEN) == "Bonnetje\ntotaal 12,50\n"
    assert mock_cmd.calls == [["tesseract", str(jpg), "-", "-l", TALEN]]


async def test_heic_wordt_eerst_jpg(
    mock_cmd: CmdMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def nep_heic_naar_jpg(pad: Path, tmpdir: Path) -> Path:
        doel = tmpdir / (pad.stem + ".jpg")
        doel.write_bytes(b"")
        return doel

    monkeypatch.setattr("ordner.extract._heic_naar_jpg", nep_heic_naar_jpg)
    mock_cmd.register("tesseract", stdout=b"foto")
    heic = tmp_path / "Foto.HEIC"
    heic.write_bytes(b"")

    assert await extract_afbeelding(heic, TALEN) == "foto"
    bron = Path(mock_cmd.calls[0][1])
    assert bron.suffix == ".jpg"
    assert bron.stem == "Foto"
    assert bron.parent != tmp_path


async def test_kapotte_heic_geeft_extractiefout(mock_cmd: CmdMock, tmp_path: Path) -> None:
    """Onleesbare heic-data (PIL: UnidentifiedImageError) wordt een ExtractieFout, geen crash (15b: stap 1 leest altijd)."""
    mock_cmd.register("tesseract", stdout=b"foto")
    heic = tmp_path / "kapot.heic"
    heic.write_bytes(b"dit is geen heic")

    with pytest.raises(ExtractieFout, match="heic niet leesbaar"):
        await extract_afbeelding(heic, TALEN)
    assert mock_cmd.calls == []  # tesseract is niet aangeroepen


async def test_tesseract_faalt(mock_cmd: CmdMock, tmp_path: Path) -> None:
    mock_cmd.register("tesseract", rc=1, stderr=b"Error opening data file")
    png = tmp_path / "x.png"
    png.write_bytes(b"")

    with pytest.raises(ExtractieFout, match="data file"):
        await extract_afbeelding(png, TALEN)


# --- extract_bestand ------------------------------------------------------


async def test_extract_bestand_dispatch(mock_cmd: CmdMock, tmp_path: Path) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1\n")
    mock_cmd.register("pdftotext", stdout=b"p" * 80)
    mock_cmd.register("tesseract", stdout=b"beeld")
    pdf = tmp_path / "A.PDF"
    png = tmp_path / "b.PNG"
    pdf.write_bytes(b"")
    png.write_bytes(b"")

    assert await extract_bestand(pdf, TALEN) == "p" * 80
    assert await extract_bestand(png, TALEN) == "beeld"


async def test_extract_bestand_onbekende_extensie(mock_cmd: CmdMock, tmp_path: Path) -> None:
    with pytest.raises(ExtractieFout, match="niet extraheerbaar: brief.docx"):
        await extract_bestand(tmp_path / "brief.docx", TALEN)
    assert mock_cmd.calls == []


# --- _normaliseer ---------------------------------------------------------


def test_normaliseer_regeleinden_en_paginas() -> None:
    assert _normaliseer("a\r\nb\fc") == "a\nb\nc"


def test_normaliseer_trailing_whitespace_en_lege_regels() -> None:
    assert _normaliseer("a  \t\n\n\n\n\n\nb ") == "a\n\n\nb"
    assert _normaliseer("a\n\n\nb") == "a\n\n\nb"


# --- run_cmd (echt, zonder mock) ------------------------------------------


async def test_run_cmd_programma_niet_gevonden() -> None:
    assert extract.run_cmd is run_cmd
    with pytest.raises(ExtractieFout, match="niet gevonden"):
        await run_cmd(["ordner-bestaat-niet-xyz"])
