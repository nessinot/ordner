"""Browser-laag (pakket 12): Playwright met mobiele viewport tegen een echte, lokaal gestarte uvicorn.

De tests bouwen op elkaar voort (één document dat wordt geüpload, bewerkt, aangevuld en verwijderd);
ze delen die staat via `staat` en draaien in bestandsvolgorde. Zonder OCR-tools op deze machine
wordt het `failed`-pad getest; met tools het `done`-pad.
"""

from __future__ import annotations

import re
import shutil
import time
from datetime import date
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from ordner.meta import lees_meta
from tests.e2e.conftest import FIXTURES, Server

pytestmark = pytest.mark.e2e

TITEL = "E2E factuur"
TITEL_BEWERKT = "E2E factuur bewerkt"
TAGS = ("e2e-tag", "energie 2026")  # tweede tag met spatie: wordt een AND-zoekopdracht
OCR_TIMEOUT_MS = 90_000

staat: dict[str, str] = {}  # "doc_url" en "doc_map" na de upload-test


def _doc_map(server: Server) -> Path:
    if "doc_map" not in staat:
        pytest.fail("upload-test is niet geslaagd; geen document om mee te werken")
    return server.archief / staat["doc_map"]


def _open_doc(page: Page, server: Server) -> None:
    page.goto(server.url + staat["doc_url"])


def _wacht_tot_ocr_klaar(page: Page) -> str:
    """Wacht via de status-polling in app.js tot de sectie niet meer `pending` is; geeft de eindstatus terug."""
    sectie = page.locator("section[data-ocr]")
    expect(sectie).not_to_have_attribute("data-ocr", "pending", timeout=OCR_TIMEOUT_MS)
    status = sectie.get_attribute("data-ocr")
    assert status in {"done", "failed"}, status
    return status


def test_upload_via_formulier(page: Page, server: Server) -> None:
    """Tweestaps upload (pakket 15b): scherm 1 alleen bestanden, scherm 2 de voorgevulde gegevens."""
    page.goto(server.url + "/upload")
    expect(page.locator("input[name=titel]")).to_have_count(0)  # scherm 1 heeft geen titelveld
    page.locator("input[name=bestanden]").set_input_files([str(FIXTURES / "tekst.pdf"), str(FIXTURES / "foto.jpg")])
    page.get_by_role("button", name="Verder").click()

    # scherm 2: bestandslijst en voorgevulde velden (zonder OCR-tools: titel leeg, datum vandaag)
    page.wait_for_url(re.compile(r"/upload/[A-Za-z0-9_-]{8,}$"), timeout=OCR_TIMEOUT_MS)
    expect(page.locator("ul.bestandslijst .bestand-naam")).to_have_text(["tekst.pdf", "foto.jpg"])
    expect(page.locator("input[name=documentdatum]")).not_to_have_value("")
    assert not (server.archief / date.today().strftime("%Y")).exists(), "scherm 1 mag niets in het archief schrijven"
    page.fill("input[name=titel]", TITEL)
    page.fill("input[name=documentdatum]", date.today().isoformat())
    page.fill("input[name=tags]", ", ".join(TAGS))
    page.get_by_role("button", name="Opslaan").click()

    page.wait_for_url(re.compile(r"/doc/"))
    expect(page.locator(".melding")).to_have_text("Opgeslagen")
    expect(page.locator("h2").first).to_contain_text(TITEL)

    pad = page.url.removeprefix(server.url).split("?")[0]  # /doc/<jaar>/<map>
    _, _, jaar, map = pad.split("/")
    staat["doc_url"] = pad
    staat["doc_map"] = f"{jaar}/{map}"

    doc = server.archief / jaar / map
    assert map == f"{date.today().isoformat()}_e2e-factuur"
    assert (doc / "meta.md").is_file()
    assert (doc / "tekst.pdf").is_file()
    assert (doc / "foto.jpg").is_file()
    assert lees_meta(doc).bestanden == ["tekst.pdf", "foto.jpg"]
    assert lees_meta(doc).tags == list(TAGS)


def test_status_polling(page: Page, server: Server, ocr_beschikbaar: bool) -> None:
    _open_doc(page, server)
    status = _wacht_tot_ocr_klaar(page)
    assert status == ("done" if ocr_beschikbaar else "failed")
    assert lees_meta(_doc_map(server)).ocr == status


def test_zoeken(page: Page, server: Server, ocr_beschikbaar: bool) -> None:
    page.goto(server.url + "/?q=e2e")
    expect(page.locator(".kaart .titel")).to_contain_text([TITEL])

    if ocr_beschikbaar:
        page.goto(server.url + "/?q=factuurnummer")
        kaart = page.locator(".kaart").first
        expect(kaart.locator(".titel")).to_have_text(TITEL)
        expect(kaart.locator(".snippet")).to_contain_text("tekst.pdf")


def test_tag_label_zoekt(page: Page, server: Server) -> None:
    """Klik op een tag-label (pakket 15c): in de resultatenlijst en op de documentpagina."""
    page.goto(server.url + "/?q=e2e")
    kaart = page.locator(".kaart").first
    expect(kaart.locator(".tags a.badge-tag")).to_have_text(list(TAGS))
    kaart.locator(".tags a.badge-tag", has_text=TAGS[1]).click()

    page.wait_for_url(re.compile(r"\?q=energie(%20|\+)2026"))
    expect(page.locator("input[name=q]")).to_have_value(TAGS[1])
    expect(page.locator(".kaart .titel")).to_contain_text([TITEL])

    # vanaf de documentpagina; de terugknop wijst daarna naar de tag-zoekopdracht
    kaart = page.locator(".kaart").first
    kaart.locator("a.titel").click()
    page.wait_for_url(re.compile(r"/doc/"))
    page.locator(".badges a.badge-tag", has_text=TAGS[0]).click()
    page.wait_for_url(re.compile(r"\?q=e2e-tag$"))
    expect(page.locator("input[name=q]")).to_have_value(TAGS[0])
    expect(page.locator(".kaart .titel")).to_contain_text([TITEL])

    # klik naast het label (op de datum) opent het document: de titel-link dekt de hele kaart, dus
    # via muiscoördinaten, anders weigert Playwright omdat de link "in de weg" ligt
    vak = page.locator(".kaart .datum").first.bounding_box()
    assert vak is not None
    page.mouse.click(vak["x"] + vak["width"] / 2, vak["y"] + vak["height"] / 2)
    page.wait_for_url(re.compile(r"/doc/.*\?q=e2e-tag"))
    expect(page.locator(".terug a")).to_contain_text("e2e-tag")


def test_open_toont_kijkpagina_met_terugknop(page: Page, server: Server) -> None:
    """"Open" bij een bestand toont het op een eigen pagina met de app-kop en een terugknop (0.9.2)."""
    _open_doc(page, server)
    page.locator(".bestand", has_text="tekst.pdf").get_by_role("link", name="Open").click()
    page.wait_for_url(re.compile(r"/bekijk/tekst\.pdf$"))
    expect(page.locator("header.top")).to_be_visible()
    expect(page.locator("h2")).to_have_text("tekst.pdf")
    expect(page.locator("iframe.bekijk-vlak")).to_have_attribute("src", re.compile(r"/bestand/tekst\.pdf$"))
    page.locator(".terug a").click()
    page.wait_for_url(re.compile(r"/doc/[^/]+/[^/]+$"))
    expect(page.locator("h2").first).to_have_text(TITEL)


def test_bewerken_zonder_hernoemen(page: Page, server: Server) -> None:
    doc = _doc_map(server)
    _open_doc(page, server)
    page.fill("input[name=titel]", TITEL_BEWERKT)
    page.get_by_role("button", name="Opslaan").click()

    page.wait_for_url(re.compile(r"m=Opgeslagen"))
    expect(page.locator("h2").first).to_have_text(TITEL_BEWERKT)
    assert doc.is_dir(), "de documentmap is hernoemd of verdwenen"
    assert lees_meta(doc).titel == TITEL_BEWERKT


def test_bestand_toevoegen(page: Page, server: Server) -> None:
    doc = _doc_map(server)
    _open_doc(page, server)
    page.locator("form.bestand-toevoegen input[name=bestanden]").set_input_files(str(FIXTURES / "foto.png"))
    page.get_by_role("button", name="Toevoegen", exact=True).click()

    page.wait_for_url(re.compile(r"m=Toegevoegd"))
    expect(page.locator(".bestand-naam")).to_contain_text(["tekst.pdf", "foto.jpg", "foto.png"])
    assert "foto.png" in lees_meta(doc).bestanden
    assert (doc / "foto.png").is_file()


def test_ocr_opnieuw(page: Page, server: Server, ocr_beschikbaar: bool) -> None:
    _open_doc(page, server)
    page.get_by_role("button", name="OCR opnieuw").click()

    page.wait_for_url(re.compile(r"m=OCR"))
    expect(page.locator(".melding")).to_have_text("OCR gestart")
    # De worker kan al klaar zijn vóór de redirect rendert; de eindstatus is wat telt.
    status = _wacht_tot_ocr_klaar(page)
    assert status == ("done" if ocr_beschikbaar else "failed")


def test_verwijderen_met_confirm(page: Page, server: Server) -> None:
    doc = _doc_map(server)
    _open_doc(page, server)
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Verwijderen").click()

    page.wait_for_url(re.compile(r"m=Verplaatst"))
    expect(page.locator(".melding")).to_contain_text("prullenbak")
    assert not doc.exists()
    assert (server.archief / "_prullenbak" / doc.name).is_dir()


def test_inbox(page: Page, server: Server) -> None:
    """Pakket 17: zonder herkende afzender wacht het bestand op de inboxpagina; met tesseract (bon-titel) wordt het zelf opgenomen."""
    inbox = server.archief / "_inbox" / "foto.jpg"
    shutil.copy(FIXTURES / "foto.jpg", inbox)

    deadline = time.monotonic() + 30
    page.goto(server.url + "/inbox")
    while inbox.exists() and page.locator("ul.inbox li").count() == 0 and time.monotonic() < deadline:
        time.sleep(1)
        page.reload()
    if inbox.exists():
        expect(page.locator("ul.inbox .bestand-naam").first).to_have_text("foto.jpg")
        page.get_by_role("button", name="Opnemen").click()
        page.wait_for_url(re.compile(r"/upload/[A-Za-z0-9_-]{8,}$"))
        expect(page.locator("p.herkomst")).to_contain_text("foto.jpg")
        expect(page.get_by_role("button", name="Terug naar inbox")).to_be_visible()
        page.fill("input[name=titel]", "E2E inbox")
        page.get_by_role("button", name="Opslaan").click()
        page.wait_for_url(re.compile(r"/doc/"))
        expect(page.locator(".melding")).to_have_text("Opgeslagen")
        expect(page.locator("h2").first).to_contain_text("E2E inbox")
    assert not inbox.exists()
    assert not (server.archief / "_inbox" / ".tekst" / "foto.jpg.txt").exists()


def test_beheer(page: Page, server: Server) -> None:
    page.goto(server.url + "/beheer")
    expect(page.locator('[data-tel="totaal"]')).to_have_text(re.compile(r"^\d+$"))
    page.get_by_role("button", name=re.compile("Cache verversen")).click()

    page.wait_for_url(re.compile(r"/beheer\?m="))
    deadline = time.monotonic() + 10
    while page.locator(".beheer table").count() < 2 and time.monotonic() < deadline:
        time.sleep(1)
        page.reload()
    assert page.locator(".beheer table").count() == 2, "geen rapport van de laatste verversing"
    expect(page.locator(".beheer")).to_contain_text("Inbox verwerkt")


def test_ingress_prefix(browser: Browser, server: Server) -> None:
    prefix = "/api/hassio_ingress/abc"
    context = browser.new_context(extra_http_headers={"X-Ingress-Path": prefix})
    try:
        page = context.new_page()
        page.goto(server.url + "/")
        waarden = {
            **{f"a[{i}]": v for i, v in enumerate(page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"))},
            **{f"form[{i}]": v for i, v in enumerate(page.eval_on_selector_all("form[action]", "els => els.map(e => e.getAttribute('action'))"))},
            **{f"css[{i}]": v for i, v in enumerate(page.eval_on_selector_all("link[rel=stylesheet]", "els => els.map(e => e.getAttribute('href'))"))},
            "status": page.get_attribute("body", "data-status-url"),
        }
        assert waarden, "geen links gevonden"
        fout = {k: v for k, v in waarden.items() if not (v or "").startswith(prefix + "/")}
        assert not fout, fout
    finally:
        context.close()
