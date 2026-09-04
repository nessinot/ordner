"""Container-laag (pakket 12): het echte add-on-image met echte pdftotext/ocrmypdf/tesseract, getest via HTTP.

Skipt in zijn geheel als `docker` ontbreekt (zie fixture `container` in conftest.py).
"""

from __future__ import annotations

import re
import shutil
import time
from datetime import date
from pathlib import Path
from typing import Callable

import httpx
import pytest

from ordner.meta import lees_meta
from tests.e2e.conftest import CONTAINER_NAAM, FIXTURES, Container, _docker, wacht_op_http

pytestmark = pytest.mark.container


def _wacht(conditie: Callable[[], bool], timeout: float, wat: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if conditie():
            return
        time.sleep(1)
    pytest.fail(f"{wat} niet binnen {timeout:.0f} s")


def _upload(container: Container, titel: str, bestand: Path) -> Path:
    """Upload één bestand; geeft de documentmap op de gedeelde schijf terug."""
    with open(bestand, "rb") as f:
        r = httpx.post(
            container.url + "/upload",
            data={"titel": titel, "documentdatum": date.today().isoformat()},
            files={"bestanden": (bestand.name, f, "application/octet-stream")},
            follow_redirects=False,
            timeout=60,
        )
    assert r.status_code == 303, r.text
    pad = r.headers["location"].split("?")[0]  # /doc/<jaar>/<map>
    _, _, jaar, map = pad.split("/")
    doc = container.share / jaar / map
    assert doc.is_dir(), doc
    return doc


def _txt_bevat(doc: Path, naam: str, woord: str) -> Callable[[], bool]:
    txt = doc / f"{naam}.txt"
    return lambda: txt.is_file() and woord in txt.read_text(encoding="utf-8", errors="replace")


def test_start(container: Container) -> None:
    assert httpx.get(container.url + "/").status_code == 200


def test_pending_bij_start(container: Container) -> None:
    doc = container.share / "2025" / "2025-01-01_pending-test"
    _wacht(_txt_bevat(doc, "foto.png", "SCANTEST"), 60, "pending document opgepakt")
    _wacht(lambda: lees_meta(doc).ocr == "done", 10, "meta.md op done")


def test_digitale_pdf(container: Container) -> None:
    doc = _upload(container, "Container digitale pdf", FIXTURES / "tekst.pdf")
    start = time.monotonic()
    _wacht(_txt_bevat(doc, "tekst.pdf", "FACTUURNUMMER"), 60, "tekstlaag via pdftotext")
    tekst = (doc / "tekst.pdf.txt").read_text(encoding="utf-8")
    # pdftotext-pad: exacte tekst en snel klaar (ocrmypdf zou tientallen seconden kosten)
    assert "Ordner testdocument FACTUURNUMMER 20260903" in tekst
    assert time.monotonic() - start < 30


def test_gescande_pdf(container: Container) -> None:
    doc = _upload(container, "Container gescande pdf", FIXTURES / "scan.pdf")
    _wacht(_txt_bevat(doc, "scan.pdf", "SCANTEST"), 120, "OCR via ocrmypdf")


def test_heic(container: Container) -> None:
    doc = _upload(container, "Container heic bon", FIXTURES / "foto.heic")
    _wacht(_txt_bevat(doc, "foto.heic", "BONNETJE"), 60, "OCR via heic→jpg→tesseract")
    assert lees_meta(doc).ocr == "done"


def test_zoeken_op_ocr_tekst(container: Container) -> None:
    r = httpx.get(container.url + "/", params={"q": "bonnetje"})
    assert r.status_code == 200
    assert "Container heic bon" in r.text


def test_ingress_header(container: Container) -> None:
    prefix = "/api/hassio_ingress/abc"
    r = httpx.get(container.url + "/", headers={"X-Ingress-Path": prefix})
    assert r.status_code == 200
    verwijzingen = re.findall(r'(?:href|action|data-status-url)="([^"]*)"', r.text)
    assert verwijzingen
    fout = [v for v in verwijzingen if not v.startswith(prefix + "/")]
    assert not fout, fout


def test_inbox_via_volume(container: Container) -> None:
    inbox = container.share / "_inbox"
    inbox.mkdir(exist_ok=True)
    shutil.copy(FIXTURES / "foto.jpg", inbox / "foto.jpg")
    vandaag = container.share / str(date.today().year)

    def opgenomen() -> bool:
        if (inbox / "foto.jpg").exists():
            return False
        return any(
            m.name.startswith(date.today().isoformat()) and (m / "foto.jpg").is_file()
            for m in vandaag.iterdir()
        ) if vandaag.is_dir() else False

    _wacht(opgenomen, 30, "inbox-bestand opgenomen")


def test_herstart(container: Container) -> None:
    voor = httpx.get(container.url + "/").text
    titels = [t for t in ("Container digitale pdf", "Container gescande pdf", "Container heic bon") if t in voor]
    assert titels, "geen eerder gemaakte documenten zichtbaar vóór herstart"

    herstart = _docker("restart", CONTAINER_NAAM, timeout=120)
    assert herstart.returncode == 0, herstart.stderr
    wacht_op_http(container.url + "/", timeout=90)

    na = httpx.get(container.url + "/").text
    for titel in titels:
        assert titel in na
