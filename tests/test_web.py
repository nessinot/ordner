from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient

from ordner.meta import lees_meta

_PREFIX = "/api/hassio_ingress/abc"
_PDF = b"%PDF-1.4 testinhoud"


Bestand = tuple[str, bytes, str]  # (naam, inhoud, content-type)
_A_PDF: Bestand = ("a.pdf", _PDF, "application/pdf")


def _stap1(client: TestClient, bestanden: list[Bestand] | None = None, headers: dict[str, str] | None = None):
    """Scherm 1: bestanden insturen; geeft de (303-)response met het token in `Location`."""
    files = [("bestanden", b) for b in (bestanden if bestanden is not None else [_A_PDF])]
    return client.post("/upload", files=files, headers=headers, follow_redirects=False)


def _token(r) -> str:  # type: ignore[no-untyped-def]
    assert r.status_code == 303, r.status_code
    m = re.search(r"/upload/([A-Za-z0-9_-]+)$", r.headers["location"])
    assert m, r.headers["location"]
    return m.group(1)


def _upload(
    client: TestClient,
    titel: str = "Test",
    datum: str = "2026-03-01",
    bestanden: list[Bestand] | None = None,
    **velden: str,
):
    """Beide stappen: POST /upload met de bestanden, dan POST /upload/{token} met de velden (pakket 15b)."""
    token = _token(_stap1(client, bestanden))
    return client.post(f"/upload/{token}", data={"titel": titel, "documentdatum": datum, **velden}, follow_redirects=False)


def _wacht_op(pad: Path, seconden: float = 2.0) -> bool:
    einde = time.monotonic() + seconden
    while time.monotonic() < einde:
        if pad.exists():
            return True
        time.sleep(0.02)
    return pad.exists()


def _root(client: TestClient) -> Path:
    return client.app.state.archief.root  # type: ignore[attr-defined]


# --- zoeken ---------------------------------------------------------------


def test_zoekpagina(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "Ordner" in r.text
    assert "Recent" in r.text
    assert 'type="search"' in r.text


def test_zoeken_toont_titel_na_upload(client: TestClient) -> None:
    _upload(client, titel="WOZ beschikking", tags="woz, gemeente")
    r = client.get("/?q=woz")
    assert r.status_code == 200
    assert "WOZ beschikking" in r.text
    assert "/doc/2026/2026-03-01_woz-beschikking" in r.text
    assert "Niets gevonden" not in r.text

    r = client.get("/?q=bestaatniet")
    assert "Niets gevonden" in r.text


def _vul_index(client: TestClient, aantal: int, titel: str) -> None:
    """Maakt `aantal` documenten direct op schijf en in de index (zonder upload/OCR)."""
    from datetime import date, timedelta

    archief = client.app.state.archief  # type: ignore[attr-defined]
    index = client.app.state.index  # type: ignore[attr-defined]
    for i in range(aantal):
        doc = archief.maak_document(f"{titel} {i:03d}", date(2026, 1, 1) + timedelta(days=i))
        index.herlaad(archief, doc)


def test_recent_kapt_af_op_20_met_voetnoot(client: TestClient) -> None:
    _vul_index(client, 25, "Bon")
    r = client.get("/")
    assert r.text.count('class="kaart"') == 20
    assert "De 20 nieuwste van 25 documenten" in r.text
    assert "Bon 024" in r.text  # nieuwste datum
    assert "Bon 000" not in r.text  # oudste valt buiten de 20


def test_recent_zonder_voetnoot_als_alles_past(client: TestClient) -> None:
    _vul_index(client, 3, "Bon")
    r = client.get("/")
    assert r.text.count('class="kaart"') == 3
    assert "nieuwste van" not in r.text


def test_zoeken_kapt_af_op_50_en_toon_alles(client: TestClient) -> None:
    _vul_index(client, 55, "Factuur")
    r = client.get("/?q=factuur")
    assert r.text.count('class="kaart"') == 50
    assert "55 resultaten" in r.text
    assert "de 50 nieuwste getoond" in r.text
    assert "De 50 nieuwste van 55 resultaten" in r.text
    assert "?q=factuur&amp;alles=1" in r.text

    r = client.get("/?q=factuur&alles=1")
    assert r.text.count('class="kaart"') == 55
    assert "nieuwste" not in r.text


def test_zoeken_zonder_afkapping_geen_voetnoot(client: TestClient) -> None:
    _vul_index(client, 5, "Factuur")
    r = client.get("/?q=factuur")
    assert "5 resultaten" in r.text
    assert "nieuwste" not in r.text


# --- tags als labels (pakket 15c) -------------------------------------------


class _LinkParser(HTMLParser):
    """Telt geneste <a>-elementen; ongeldige HTML zodra een <a> binnen een <a> opent."""

    def __init__(self) -> None:
        super().__init__()
        self.diepte = 0
        self.genest = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            if self.diepte:
                self.genest += 1
            self.diepte += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.diepte:
            self.diepte -= 1


def _geneste_links(html: str) -> int:
    parser = _LinkParser()
    parser.feed(html)
    return parser.genest


def test_tags_als_labels_in_resultatenlijst(client: TestClient) -> None:
    _upload(client, titel="WOZ beschikking", tags="woz, gemeente amsterdam")
    for pad in ("/", "/?q=woz"):
        r = client.get(pad)
        assert r.status_code == 200, pad
        assert '<span class="tags">' in r.text, pad
        assert '<a class="badge badge-tag" href="/?q=woz">woz</a>' in r.text, pad
        assert '<a class="badge badge-tag" href="/?q=gemeente%20amsterdam">gemeente amsterdam</a>' in r.text, pad
        # titel blijft een link naar het document; de kaartrij zelf is geen link meer
        assert '<a class="titel" href="/doc/2026/2026-03-01_woz-beschikking' in r.text, pad
        assert '<a class="rij"' not in r.text, pad
        assert _geneste_links(r.text) == 0, pad
    # volgorde zoals in meta.md
    r = client.get("/")
    assert r.text.index("?q=woz") < r.text.index("?q=gemeente%20amsterdam")


def test_tags_labels_met_ingress_prefix(client: TestClient) -> None:
    _upload(client, titel="WOZ beschikking", tags="woz")
    for pad in ("/?q=woz", "/doc/2026/2026-03-01_woz-beschikking"):
        r = client.get(pad, headers={"X-Ingress-Path": _PREFIX})
        assert f'<a class="badge badge-tag" href="{_PREFIX}/?q=woz">woz</a>' in r.text, pad


def test_kaart_zonder_tags_heeft_geen_tags_span(client: TestClient) -> None:
    _upload(client, titel="Zonder tags")
    r = client.get("/?q=zonder")
    assert 'class="kaart"' in r.text
    assert 'class="tags"' not in r.text
    assert "badge-tag" not in r.text


def test_tag_label_op_documentpagina(client: TestClient) -> None:
    _upload(client, tags="woz, gemeente amsterdam")
    r = client.get(_DOC)
    assert '<a class="badge badge-tag" href="/?q=woz">woz</a>' in r.text
    assert '<a class="badge badge-tag" href="/?q=gemeente%20amsterdam">gemeente amsterdam</a>' in r.text
    assert _geneste_links(r.text) == 0
    # de tag-zoekopdracht vindt het document
    r = client.get("/?q=gemeente amsterdam")
    assert "1 resultaat" in r.text
    assert f'href="{_DOC}?q=gemeente%20amsterdam"' in r.text


# --- upload (tweestaps sinds pakket 15b) ------------------------------------

_ENECO = b"Factuur                     Factuurnummer 2024-0031\nEneco Services B.V.\nFactuurdatum 12-03-2024\nVervaldatum 12-04-2024\n" + b" x" * 30


def test_upload_formulier_scherm1_alleen_bestanden(client: TestClient) -> None:
    r = client.get("/upload")
    assert r.status_code == 200
    assert "data-upload" in r.text
    assert 'enctype="multipart/form-data"' in r.text
    assert 'name="bestanden"' in r.text
    assert "capture" not in r.text
    assert "Verder" in r.text
    for veld in ("titel", "omschrijving", "documentdatum", "tags"):
        assert f'name="{veld}"' not in r.text, veld
    assert "Bestanden ontvangen, tekst lezen" in r.text


def test_stap1_zonder_bestanden_400(client: TestClient) -> None:
    r = client.post("/upload", follow_redirects=False)
    assert r.status_code == 400
    assert "Kies minstens één bestand." in r.text
    assert "data-upload" in r.text
    # oude velden worden genegeerd: nog steeds geen document
    r = client.post("/upload", data={"titel": "Leeg", "documentdatum": "2026-03-01"}, follow_redirects=False)
    assert r.status_code == 400
    assert client.app.state.archief.documentmappen() == []  # type: ignore[attr-defined]


def test_stap1_schrijft_niets_en_stuurt_door(client: TestClient) -> None:
    archief = client.app.state.archief  # type: ignore[attr-defined]
    voor = archief.documentmappen()
    r = _stap1(client)
    assert r.status_code == 303
    token = _token(r)
    assert r.headers["location"] == f"/upload/{token}"
    assert archief.documentmappen() == voor == []
    assert list((_root(client) / "_inbox").iterdir()) == []
    assert not any(_root(client).glob("*/*"))  # geen jaarmap, geen documentmap
    assert len(client.app.state.openstaand) == 1  # type: ignore[attr-defined]


def test_scherm2_voorgevuld_uit_tekst(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    mock_cmd.register("pdftotext", stdout=_ENECO)
    token = _token(_stap1(client, [("factuur.pdf", _PDF, "application/pdf")]))
    r = client.get(f"/upload/{token}")
    assert r.status_code == 200
    assert 'name="titel" value="Eneco Services B.V."' in r.text
    assert "voorstel uit het document" in r.text
    assert 'name="documentdatum" value="2024-03-12"' in r.text
    assert "datum uit tekst" in r.text
    assert 'name="tags" value="factuur"' in r.text
    assert "factuur.pdf" in r.text
    assert 'action="/upload/' + token + '"' in r.text
    assert f'formaction="/upload/{token}/annuleer"' in r.text
    assert "Opslaan" in r.text and "Annuleren" in r.text
    # nog steeds niets op schijf
    assert client.app.state.archief.documentmappen() == []  # type: ignore[attr-defined]


def test_scherm2_zonder_treffers(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    # lange tekst zonder naam, datum of documenttype: titel leeg, datum vandaag, geen tags
    mock_cmd.register("pdftotext", stdout=b"\n".join(b"regel %d zonder iets bruikbaars" % i for i in range(40)))
    token = _token(_stap1(client))
    r = client.get(f"/upload/{token}")
    assert 'name="titel" value=""' in r.text
    assert "voorstel uit het document" not in r.text
    assert f'name="documentdatum" value="{_vandaag().isoformat()}"' in r.text
    assert "geen datum gevonden, vandaag" in r.text
    assert 'name="tags" value=""' in r.text


def test_opslaan_datum_ongewijzigd_bron_tekst(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    mock_cmd.register("pdftotext", stdout=_ENECO)
    token = _token(_stap1(client, [("factuur.pdf", _PDF, "application/pdf")]))
    r = client.post(
        f"/upload/{token}",
        data={"titel": "Eneco Services B.V.", "documentdatum": "2024-03-12", "tags": "factuur"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/doc/2024/2024-03-12_eneco-services-b-v?m=Opgeslagen"
    doc = _root(client) / "2024" / "2024-03-12_eneco-services-b-v"
    meta = lees_meta(doc)
    assert meta.titel == "Eneco Services B.V."
    assert meta.documentdatum.isoformat() == "2024-03-12"
    assert meta.datumbron == "tekst"
    assert meta.tags == ["factuur"]
    assert meta.ocr == "done"  # tekst is al in stap 1 gelezen
    assert (doc / "factuur.pdf.txt").exists()
    assert (doc / "factuur.pdf").read_bytes() == _PDF
    assert len(client.app.state.openstaand) == 0  # type: ignore[attr-defined]
    r = client.get(r.headers["location"])
    assert "Opgeslagen" in r.text
    assert "datum uit tekst" in r.text


def test_opslaan_datum_gewijzigd_bron_gebruiker(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    mock_cmd.register("pdftotext", stdout=_ENECO)
    r = _upload(client, titel="Eneco", datum="2026-03-01")  # voorgevuld was 2024-03-12
    assert r.headers["location"] == "/doc/2026/2026-03-01_eneco?m=Opgeslagen"
    meta = lees_meta(_root(client) / "2026" / "2026-03-01_eneco")
    assert meta.datumbron == "gebruiker"
    assert meta.documentdatum.isoformat() == "2026-03-01"
    r = client.get("/doc/2026/2026-03-01_eneco")
    assert "datum uit tekst" not in r.text and "datum van upload" not in r.text


def test_opslaan_zonder_datum_in_tekst_bron_upload(client: TestClient) -> None:
    token = _token(_stap1(client, [("bon.pdf", _PDF, "application/pdf")]))
    r = client.post(f"/upload/{token}", data={"titel": "Bon", "documentdatum": _vandaag().isoformat()}, follow_redirects=False)
    doc = f"/doc/{_vandaag().year}/{_vandaag().isoformat()}_bon"
    assert r.headers["location"] == f"{doc}?m=Opgeslagen"
    assert lees_meta(_root(client) / str(_vandaag().year) / f"{_vandaag().isoformat()}_bon").datumbron == "upload"
    assert "datum van upload" in client.get(doc).text


def test_scherm2_zonder_titel_400(client: TestClient) -> None:
    token = _token(_stap1(client))
    r = client.post(f"/upload/{token}", data={"titel": "  ", "documentdatum": "2026-03-01", "tags": "a, b"})
    assert r.status_code == 400
    assert "Titel is verplicht" in r.text
    assert 'name="tags" value="a, b"' in r.text  # ingevulde waarden blijven staan
    assert 'name="documentdatum" value="2026-03-01"' in r.text
    # de upload staat nog open; alsnog opslaan werkt
    assert client.app.state.archief.documentmappen() == []  # type: ignore[attr-defined]
    r = client.post(f"/upload/{token}", data={"titel": "Alsnog", "documentdatum": "2026-03-01"}, follow_redirects=False)
    assert r.status_code == 303


def test_scherm2_ongeldige_datum_400(client: TestClient) -> None:
    token = _token(_stap1(client))
    r = client.post(f"/upload/{token}", data={"titel": "Test", "documentdatum": "31-03-2026"})
    assert r.status_code == 400
    assert "Ongeldige documentdatum" in r.text
    assert 'value="Test"' in r.text
    r = client.post(f"/upload/{token}", data={"titel": "Test", "documentdatum": ""})
    assert r.status_code == 400


def test_onbekend_token_verlopen_melding(client: TestClient) -> None:
    for methode in ("get", "post"):
        r = getattr(client, methode)("/upload/abcdefghijkl", follow_redirects=False)
        assert r.status_code == 303, methode
        assert r.headers["location"] == "/upload?m=Deze+upload+is+verlopen%3B+kies+de+bestanden+opnieuw.", methode
    r = client.get("/upload?m=Deze upload is verlopen; kies de bestanden opnieuw.")
    assert "Deze upload is verlopen" in r.text
    # misvormd token -> 404
    assert client.get("/upload/kort").status_code == 404
    assert client.get("/upload/met%20spatie%20erin").status_code == 404
    assert client.post("/upload/kort/annuleer").status_code == 404


def test_verlopen_upload(client: TestClient) -> None:
    from datetime import timedelta

    store = client.app.state.openstaand  # type: ignore[attr-defined]
    token = _token(_stap1(client))
    upload = store.haal(token)
    assert upload is not None
    upload.aangemaakt -= timedelta(minutes=61)
    r = client.get(f"/upload/{token}", follow_redirects=False)
    assert r.status_code == 303
    assert "verlopen" in r.headers["location"]
    assert len(store) == 0


def test_dubbel_opslaan_maakt_een_document(client: TestClient) -> None:
    token = _token(_stap1(client))
    velden = {"titel": "Dubbel", "documentdatum": "2026-03-01"}
    r1 = client.post(f"/upload/{token}", data=velden, follow_redirects=False)
    r2 = client.post(f"/upload/{token}", data=velden, follow_redirects=False)
    assert r1.status_code == 303 and "/doc/2026/2026-03-01_dubbel?m=Opgeslagen" in r1.headers["location"]
    assert r2.status_code == 303 and r2.headers["location"].startswith("/upload?m=Deze+upload+is+verlopen")
    mappen = client.app.state.archief.documentmappen()  # type: ignore[attr-defined]
    assert [m.name for m in mappen] == ["2026-03-01_dubbel"]


def test_annuleren(client: TestClient) -> None:
    token = _token(_stap1(client))
    r = client.post(f"/upload/{token}/annuleer", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/upload?m=Upload+geannuleerd"
    assert client.app.state.archief.documentmappen() == []  # type: ignore[attr-defined]
    assert not any(_root(client).glob("*/*"))
    assert len(client.app.state.openstaand) == 0  # type: ignore[attr-defined]
    assert client.get(f"/upload/{token}", follow_redirects=False).status_code == 303
    # nogmaals annuleren is onschuldig
    assert client.post(f"/upload/{token}/annuleer", follow_redirects=False).status_code == 303


def test_upload_maakt_document_en_ocr(client: TestClient) -> None:
    r = _upload(client, tags="a, b ,, c")
    assert r.status_code == 303
    assert "/doc/2026/2026-03-01_test" in r.headers["location"]
    assert "m=Opgeslagen" in r.headers["location"]

    doc = _root(client) / "2026" / "2026-03-01_test"
    assert doc.is_dir()
    assert (doc / "a.pdf").read_bytes() == _PDF
    meta = lees_meta(doc)
    assert meta.bestanden == ["a.pdf"]
    assert meta.tags == ["a", "b", "c"]
    assert meta.datumbron == "gebruiker"
    assert meta.ocr == "done"  # tekst al in stap 1 gelezen
    assert (doc / "a.pdf.txt").read_text(encoding="utf-8") == "x" * 100

    # redirect-doel werkt en toont de melding
    r = client.get(r.headers["location"])
    assert r.status_code == 200
    assert "Opgeslagen" in r.text
    assert "Test" in r.text


def _wacht_op_status(doc: Path, status: str, seconden: float = 2.0) -> bool:
    einde = time.monotonic() + seconden
    while time.monotonic() < einde:
        if lees_meta(doc).ocr == status:
            return True
        time.sleep(0.02)
    return lees_meta(doc).ocr == status


def test_onleesbaar_bestand_wordt_na_opslaan_gequeued(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    """Mislukt het lezen in stap 1 (hier: pdftotext faalt), dan gaat het bestand na Opslaan alsnog naar de OCR-queue."""
    mock_cmd.register("pdftotext", rc=1, stderr=b"kapot")
    r = _upload(client)
    assert r.status_code == 303
    doc = _root(client) / "2026" / "2026-03-01_test"
    assert lees_meta(doc).ocr in ("pending", "failed")
    assert _wacht_op_status(doc, "failed")
    assert not (doc / "a.pdf.txt").exists()


def test_meta_bewerken_zet_datumbron_op_gebruiker(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    mock_cmd.register("pdftotext", stdout=b"Datum: 12-03-2024" + b" x" * 30)
    _upload(client, titel="Brief", datum="2024-03-12", bestanden=[("b.pdf", _PDF, "application/pdf")])
    doc = _root(client) / "2024" / "2024-03-12_brief"
    assert lees_meta(doc).datumbron == "tekst"
    # alleen tags wijzigen: datum blijft uit tekst
    client.post("/doc/2024/2024-03-12_brief/meta", data={"titel": "Brief", "documentdatum": "2024-03-12", "tags": "x"})
    assert lees_meta(doc).datumbron == "tekst"
    # datum wijzigen: bron wordt gebruiker, map blijft
    client.post("/doc/2024/2024-03-12_brief/meta", data={"titel": "Brief", "documentdatum": "2024-03-13"})
    meta = lees_meta(doc)
    assert meta.datumbron == "gebruiker"
    assert meta.documentdatum.isoformat() == "2024-03-13"
    assert doc.is_dir()


def test_bekende_titel_uit_archief_voorgesteld(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    _upload(client, titel="Eneco")
    mock_cmd.register("pdftotext", stdout=b"\n".join(b"regel %d" % i for i in range(30)) + b"\nBetaling aan Eneco voor levering\n")
    token = _token(_stap1(client))
    assert 'name="titel" value="Eneco"' in client.get(f"/upload/{token}").text


def _vandaag():  # type: ignore[no-untyped-def]
    from datetime import date

    return date.today()


# --- ingress --------------------------------------------------------------


def test_ingress_prefix_in_alle_links(client: TestClient) -> None:
    _upload(client)
    for pad in ("/", "/?q=test", "/upload", "/doc/2026/2026-03-01_test", "/beheer"):
        r = client.get(pad, headers={"X-Ingress-Path": _PREFIX})
        assert r.status_code == 200, pad
        urls = re.findall(r'(?:href|action|src)="([^"]*)"', r.text)
        assert urls, pad
        for url in urls:
            assert url.startswith(_PREFIX + "/"), (pad, url)
    assert f'href="{_PREFIX}/static/style.css"' in r.text


def test_ingress_prefix_in_redirect(client: TestClient) -> None:
    r = _stap1(client, headers={"X-Ingress-Path": _PREFIX + "/"})
    assert r.status_code == 303
    assert r.headers["location"].startswith(_PREFIX + "/upload/")
    token = r.headers["location"].rsplit("/", 1)[1]
    # scherm 2: alle actions (ook formaction van Annuleren) met prefix
    r = client.get(f"/upload/{token}", headers={"X-Ingress-Path": _PREFIX})
    assert r.status_code == 200
    acties = re.findall(r'(?:href|action|src)="([^"]*)"', r.text)
    assert f"{_PREFIX}/upload/{token}" in acties
    assert f"{_PREFIX}/upload/{token}/annuleer" in acties
    for url in acties:
        assert url.startswith(_PREFIX + "/"), url
    r = client.post(
        f"/upload/{token}",
        data={"titel": "Ingress", "documentdatum": "2026-03-02"},
        headers={"X-Ingress-Path": _PREFIX + "/"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].startswith(_PREFIX + "/doc/2026/2026-03-02_ingress")
    # verlopen-redirect en annuleren met prefix
    r = client.get(f"/upload/{token}", headers={"X-Ingress-Path": _PREFIX}, follow_redirects=False)
    assert r.headers["location"].startswith(_PREFIX + "/upload?m=")
    token2 = _token(_stap1(client))
    r = client.post(f"/upload/{token2}/annuleer", headers={"X-Ingress-Path": _PREFIX}, follow_redirects=False)
    assert r.headers["location"] == f"{_PREFIX}/upload?m=Upload+geannuleerd"


def test_ingress_static_bereikbaar(client: TestClient) -> None:
    """Regressie: de static-mount gaf 404 zodra root_path gezet was (Starlette wil het prefix ook in `path`)."""
    for naam in ("style.css", "app.js"):
        r = client.get(f"/static/{naam}", headers={"X-Ingress-Path": _PREFIX})
        assert r.status_code == 200, naam
    assert client.get("/static/nietbestaand.css", headers={"X-Ingress-Path": _PREFIX}).status_code == 404


def test_zonder_ingress_geen_prefix(client: TestClient) -> None:
    r = client.get("/")
    assert 'href="/static/style.css"' in r.text
    assert 'action="/"' in r.text


# --- document en bestand ---------------------------------------------------


def test_bestand_serveren(client: TestClient) -> None:
    _upload(client)
    r = client.get("/doc/2026/2026-03-01_test/bestand/a.pdf")
    assert r.status_code == 200
    assert r.content == _PDF
    assert r.headers["content-type"].startswith("application/pdf")
    assert "inline" in r.headers["content-disposition"]
    assert "a.pdf" in r.headers["content-disposition"]


def test_bekijk_pagina(client: TestClient) -> None:
    r = _upload(client, bestanden=[_A_PDF, ("b.png", b"png", "image/png"), ("c.docx", b"docx", "application/octet-stream")])
    doc = "/doc/2026/2026-03-01_test"
    r = client.get(f"{doc}/bekijk/a.pdf")
    assert r.status_code == 200
    assert f'<iframe class="bekijk-vlak" src="{doc}/bestand/a.pdf"' in r.text
    assert f'href="{doc}">' in r.text  # terug naar het document
    assert "<title>a.pdf · Ordner</title>" in r.text
    assert 'target="_blank"' not in r.text

    r = client.get(f"{doc}/bekijk/b.png")
    assert f'<img class="bekijk-vlak" src="{doc}/bestand/b.png"' in r.text
    assert "<iframe" not in r.text

    r = client.get(f"{doc}/bekijk/c.docx")
    assert "kan hier niet getoond worden" in r.text
    assert f'<a href="{doc}/bestand/c.docx">' in r.text
    assert "<iframe" not in r.text and "<img class" not in r.text

    # de zoekopdracht reist mee: Open-knop → kijkpagina → terug naar document, alles met ?q=
    r = client.get(f"{doc}?q=woz&alles=1")
    assert f'href="{doc}/bekijk/a.pdf?q=woz&amp;alles=1">Open</a>' in r.text
    r = client.get(f"{doc}/bekijk/a.pdf?q=woz&alles=1")
    assert f'href="{doc}?q=woz&amp;alles=1">' in r.text


def test_bekijk_404(client: TestClient) -> None:
    _upload(client)
    assert client.get("/doc/2026/2026-03-01_test/bekijk/nietbestaand.pdf").status_code == 404
    assert client.get("/doc/2026/2026-03-01_test/bekijk/..%5Cmeta.md").status_code == 404
    assert client.get("/doc/2026/nietbestaand/bekijk/a.pdf").status_code == 404


def test_bestand_buiten_archief_404(client: TestClient) -> None:
    _upload(client)
    assert client.get("/doc/2026/../x/bestand/a.pdf").status_code == 404
    assert client.get("/doc/2026/..%5C..%5Cx/bestand/a.pdf").status_code == 404
    assert client.get("/doc/2026/2026-03-01_test/bestand/..%5Cmeta.md").status_code == 404
    assert client.get("/doc/2026/nietbestaand/bestand/a.pdf").status_code == 404
    assert client.get("/doc/2026/2026-03-01_test/bestand/nietbestaand.pdf").status_code == 404
    assert client.get("/doc/abcd/2026-03-01_test/bestand/a.pdf").status_code == 404


def test_document_pagina(client: TestClient) -> None:
    _upload(client)
    r = client.get("/doc/2026/2026-03-01_test")
    assert r.status_code == 200
    assert "Test" in r.text
    assert "2026-03-01" in r.text
    assert "/doc/2026/2026-03-01_test/bestand/a.pdf" in r.text


def test_document_nietbestaand_404(client: TestClient) -> None:
    assert client.get("/doc/2026/nietbestaand").status_code == 404
    assert client.get("/doc/2026/..").status_code == 404
    assert client.get("/doc/_inbox/x").status_code == 404


def test_document_map_zonder_meta_404(client: TestClient) -> None:
    map = _root(client) / "2026" / "2026-01-01_los"
    map.mkdir(parents=True)
    assert client.get("/doc/2026/2026-01-01_los").status_code == 404


def test_document_niet_in_index_wordt_herladen(client: TestClient) -> None:
    """Map die na de start is verschenen (bijv. via Samba) wordt bij bezoek in de index geladen."""
    archief = client.app.state.archief  # type: ignore[attr-defined]
    from datetime import date

    doc = archief.maak_document("Handmatig", date(2025, 5, 5))
    assert "2025/2025-05-05_handmatig" not in client.app.state.index.docs  # type: ignore[attr-defined]
    r = client.get("/doc/2025/2025-05-05_handmatig")
    assert r.status_code == 200
    assert "Handmatig" in r.text
    assert "2025/2025-05-05_handmatig" in client.app.state.index.docs  # type: ignore[attr-defined]
    assert doc.is_dir()


# --- static ----------------------------------------------------------------


def test_static(client: TestClient) -> None:
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


# --- documentpagina en -acties (pakket 09) ---------------------------------

_DOC = "/doc/2026/2026-03-01_test"


def _wacht_tot(conditie, seconden: float = 2.0) -> bool:  # type: ignore[no-untyped-def]
    einde = time.monotonic() + seconden
    while time.monotonic() < einde:
        if conditie():
            return True
        time.sleep(0.02)
    return bool(conditie())


def test_document_pagina_volledig(client: TestClient) -> None:
    _upload(client, tags="woz, gemeente")
    r = client.get(_DOC)
    assert r.status_code == 200
    assert 'data-rel="2026/2026-03-01_test"' in r.text
    assert 'data-ocr="' in r.text
    assert 'data-status-url="/api/status"' in r.text
    assert 'class="badge badge-tag" href="/?q=woz">woz<' in r.text
    for actie in ("meta", "bestanden", "ocr", "verwijder"):
        assert f'action="{_DOC}/{actie}"' in r.text, actie
    assert f'<object type="application/pdf" data="{_DOC}/bestand/a.pdf"' in r.text
    # "Open" wijst naar de kijkpagina (0.9.2), nooit naar het kale bestand en nooit met target="_blank":
    # de HA-app opent zo'n link in een externe browser zonder Ingress-sessie (404/401), en een los
    # geopend bestand vult het hele scherm zonder weg terug.
    assert f'<a class="knop" href="{_DOC}/bekijk/a.pdf">Open</a>' in r.text
    assert f'<a href="{_DOC}/bekijk/a.pdf">Open de pdf</a>' in r.text
    assert 'target="_blank"' not in r.text
    assert "De mapnaam verandert niet." in r.text
    assert "confirm('Naar de prullenbak?')" in r.text
    assert 'value="woz, gemeente"' in r.text


def test_document_pagina_afbeelding_en_overig(client: TestClient) -> None:
    r = _upload(
        client,
        titel="Mix",
        datum="2026-03-05",
        bestanden=[
            ("foto.JPG", b"jpg", "image/jpeg"),
            ("notitie.docx", b"docx", "application/octet-stream"),
            ("foto.heic", b"heic", "image/heic"),  # geen echte heic: lezen in stap 1 mislukt netjes, daarna queue
        ],
    )
    assert r.status_code == 303
    r = client.get("/doc/2026/2026-03-05_mix")
    assert r.status_code == 200
    assert '<img src="/doc/2026/2026-03-05_mix/bestand/foto.JPG"' in r.text
    assert 'loading="lazy"' in r.text
    assert "/bekijk/notitie.docx" in r.text  # Open → kijkpagina, ook voor overige bestanden (0.9.2)
    assert "/bekijk/foto.heic" in r.text
    assert "<object" not in r.text
    assert r.text.count("<img ") == 1  # heic en docx niet inline


def test_document_notities_en_tekstbadge(client: TestClient) -> None:
    _upload(client)
    doc = _root(client) / "2026" / "2026-03-01_test"
    assert (doc / "a.pdf.txt").exists()
    meta = lees_meta(doc)
    meta.notities = "Eigen <notitie>"
    from ordner.meta import schrijf_meta

    schrijf_meta(doc, meta)
    client.app.state.index.herlaad(client.app.state.archief, doc)  # type: ignore[attr-defined]
    r = client.get(_DOC)
    assert "tekst aanwezig" in r.text
    assert '<pre class="notities">Eigen &lt;notitie&gt;</pre>' in r.text


def test_meta_bewerken_hernoemt_map_niet(client: TestClient) -> None:
    _upload(client)
    r = client.post(
        f"{_DOC}/meta",
        data={"titel": "Nieuwe titel", "documentdatum": "2025-12-31", "omschrijving": " Omschr ", "tags": "x, y"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"{_DOC}?m=Opgeslagen"
    doc = _root(client) / "2026" / "2026-03-01_test"
    assert doc.is_dir()  # mapnaam ongewijzigd
    assert not (_root(client) / "2025").exists()
    meta = lees_meta(doc)
    assert meta.titel == "Nieuwe titel"
    assert meta.documentdatum.isoformat() == "2025-12-31"
    assert meta.omschrijving == "Omschr"
    assert meta.tags == ["x", "y"]
    assert meta.bestanden == ["a.pdf"]
    # index bijgewerkt
    r = client.get("/?q=nieuwe")
    assert "Nieuwe titel" in r.text
    assert "2025-12-31" in r.text


def test_meta_zonder_titel_400(client: TestClient) -> None:
    _upload(client)
    r = client.post(f"{_DOC}/meta", data={"titel": "  ", "documentdatum": "2026-03-01"})
    assert r.status_code == 400
    assert "Titel is verplicht" in r.text
    assert lees_meta(_root(client) / "2026" / "2026-03-01_test").titel == "Test"


def test_meta_ongeldige_datum_400(client: TestClient) -> None:
    _upload(client)
    r = client.post(f"{_DOC}/meta", data={"titel": "Test", "documentdatum": "01-03-2026"})
    assert r.status_code == 400
    assert "Ongeldige documentdatum" in r.text
    r = client.post(f"{_DOC}/meta", data={"titel": "Test"})
    assert r.status_code == 400


# --- terugknop (herkomst) ---------------------------------------------------


def test_terugknop_zonder_zoekopdracht(client: TestClient) -> None:
    _upload(client)
    r = client.get("/")
    assert f'href="{_DOC}"' in r.text  # geen q meegegeven vanuit Recent
    r = client.get(_DOC)
    assert "Terug naar overzicht" in r.text
    assert 'class="terug"' in r.text
    assert 'name="q"' not in r.text


def test_terugknop_met_zoekopdracht(client: TestClient) -> None:
    _upload(client, titel="WOZ beschikking")
    doc = "/doc/2026/2026-03-01_woz-beschikking"
    r = client.get("/?q=woz+2026")
    assert f'href="{doc}?q=woz%202026"' in r.text
    r = client.get(f"{doc}?q=woz 2026")
    assert "Terug naar zoekresultaten voor “woz 2026”" in r.text
    assert 'href="/?q=woz%202026"' in r.text
    assert r.text.count('<input type="hidden" name="q" value="woz 2026">') == 4  # alle vier formulieren


def test_terugknop_met_toon_alles(client: TestClient) -> None:
    _upload(client)
    r = client.get("/?q=test&alles=1")
    assert f'href="{_DOC}?q=test&amp;alles=1"' in r.text
    r = client.get(f"{_DOC}?q=test&alles=1")
    assert 'href="/?q=test&amp;alles=1"' in r.text
    assert '<input type="hidden" name="alles" value="1">' in r.text
    # alles zonder q wordt genegeerd
    r = client.get(f"{_DOC}?alles=1")
    assert "Terug naar overzicht" in r.text
    assert 'name="alles"' not in r.text


def test_acties_behouden_zoekopdracht(client: TestClient) -> None:
    _upload(client)
    r = client.post(
        f"{_DOC}/meta",
        data={"titel": "Test", "documentdatum": "2026-03-01", "q": "test", "alles": "1"},
        follow_redirects=False,
    )
    assert r.headers["location"] == f"{_DOC}?q=test&alles=1&m=Opgeslagen"
    r = client.post(f"{_DOC}/ocr", data={"q": "test"}, follow_redirects=False)
    assert r.headers["location"] == f"{_DOC}?q=test&m=OCR+gestart"
    r = client.post(f"{_DOC}/bestanden", data={"q": "test"}, follow_redirects=False)
    assert r.headers["location"] == f"{_DOC}?q=test&m=Toegevoegd"
    # validatiefout: formulier opnieuw getoond, herkomst blijft in de verborgen velden
    r = client.post(f"{_DOC}/meta", data={"titel": "", "documentdatum": "2026-03-01", "q": "test"})
    assert r.status_code == 400
    assert '<input type="hidden" name="q" value="test">' in r.text
    r = client.post(f"{_DOC}/verwijder", data={"q": "test"}, follow_redirects=False)
    assert r.headers["location"] == "/?q=test&m=Verplaatst+naar+prullenbak"


def test_meta_nietbestaand_404(client: TestClient) -> None:
    assert client.post("/doc/2026/niets/meta", data={"titel": "x", "documentdatum": "2026-01-01"}).status_code == 404
    assert client.post("/doc/2026/../meta", data={"titel": "x"}).status_code == 404
    assert client.post("/doc/2026/niets/ocr").status_code == 404
    assert client.post("/doc/2026/niets/verwijder").status_code == 404
    assert client.post("/doc/2026/niets/bestanden").status_code == 404


def test_bestand_toevoegen(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    _upload(client)
    doc = _root(client) / "2026" / "2026-03-01_test"
    assert _wacht_op(doc / "a.pdf.txt")
    r = client.post(
        f"{_DOC}/bestanden",
        files=[("bestanden", ("bon.jpg", b"jpgdata", "image/jpeg"))],
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"{_DOC}?m=Toegevoegd"
    assert (doc / "bon.jpg").read_bytes() == b"jpgdata"
    assert lees_meta(doc).bestanden == ["a.pdf", "bon.jpg"]
    assert _wacht_op(doc / "bon.jpg.txt")
    assert (doc / "bon.jpg.txt").read_text(encoding="utf-8") == "tekst"
    assert any(c[0] == "tesseract" for c in mock_cmd.calls)
    assert _wacht_op_status(doc, "done")
    r = client.get("/?q=tekst")
    assert "bon.jpg" in r.text


def test_bestand_toevoegen_zonder_bestanden(client: TestClient) -> None:
    _upload(client)
    r = client.post(f"{_DOC}/bestanden", follow_redirects=False)
    assert r.status_code == 303
    assert lees_meta(_root(client) / "2026" / "2026-03-01_test").bestanden == ["a.pdf"]


def test_ocr_opnieuw(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    _upload(client)
    doc = _root(client) / "2026" / "2026-03-01_test"
    assert (doc / "a.pdf.txt").exists()
    assert lees_meta(doc).ocr == "done"
    eerste = sum(1 for c in mock_cmd.calls if c[0] == "pdftotext")
    assert eerste == 1  # één keer gelezen, in stap 1 van de upload

    r = client.post(f"{_DOC}/ocr", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"{_DOC}?m=OCR+gestart"
    assert _wacht_tot(lambda: sum(1 for c in mock_cmd.calls if c[0] == "pdftotext") == 2)
    assert _wacht_op(doc / "a.pdf.txt")
    assert _wacht_op_status(doc, "done")


def test_ocr_opnieuw_reset_failed(client: TestClient, mock_cmd) -> None:  # type: ignore[no-untyped-def]
    mock_cmd.register("pdftotext", rc=1, stderr=b"kapot")
    _upload(client)  # lezen in stap 1 mislukt; na opslaan probeert de worker het nog eens en zet failed
    doc = _root(client) / "2026" / "2026-03-01_test"
    assert _wacht_op_status(doc, "failed")
    mock_cmd.register("pdftotext", stdout=b"y" * 100)
    client.post(f"{_DOC}/ocr", follow_redirects=False)
    assert _wacht_op(doc / "a.pdf.txt")
    assert _wacht_op_status(doc, "done")
    assert (doc / "a.pdf.txt").read_text(encoding="utf-8") == "y" * 100


def test_ocr_opnieuw_zonder_extraheerbare_bestanden(client: TestClient) -> None:
    _upload(client, titel="Leeg", bestanden=[("notitie.docx", b"docx", "application/octet-stream")])
    doc = _root(client) / "2026" / "2026-03-01_leeg"
    assert lees_meta(doc).bestanden == ["notitie.docx"]
    r = client.post("/doc/2026/2026-03-01_leeg/ocr", follow_redirects=False)
    assert r.status_code == 303
    assert lees_meta(doc).ocr == "done"


def test_verwijderen(client: TestClient) -> None:
    _upload(client, titel="Weg ermee")
    rel = "2026/2026-03-01_weg-ermee"
    r = client.post(f"/doc/{rel}/verwijder", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/?m=Verplaatst+naar+prullenbak"
    root = _root(client)
    assert not (root / "2026" / "2026-03-01_weg-ermee").exists()
    assert (root / "_prullenbak" / "2026-03-01_weg-ermee" / "meta.md").exists()
    assert client.get(f"/doc/{rel}").status_code == 404
    assert "Weg ermee" not in client.get("/?q=ermee").text
    assert "Weg ermee" not in client.get("/").text
    assert rel not in client.app.state.index.docs  # type: ignore[attr-defined]


# --- status-API ------------------------------------------------------------


def test_status_api(client: TestClient) -> None:
    r = client.get("/api/status")
    assert r.status_code == 200
    s = r.json()
    assert set(s) == {"queue", "bezig", "reconcile_bezig", "tellingen"}
    assert s["reconcile_bezig"] is False
    assert s["tellingen"] == {"totaal": 0, "pending": 0, "done": 0, "failed": 0}
    assert s["bezig"] == []

    _upload(client)
    doc = _root(client) / "2026" / "2026-03-01_test"
    assert _wacht_op_status(doc, "done")
    s = client.get("/api/status?rel=2026/2026-03-01_test").json()
    assert s["ocr"] == "done"
    assert s["tellingen"]["totaal"] == 1
    assert client.get("/api/status?rel=2026/bestaat-niet").json()["ocr"] is None


# --- beheer ----------------------------------------------------------------


def test_beheer_pagina(client: TestClient) -> None:
    _upload(client)
    doc = _root(client) / "2026" / "2026-03-01_test"
    assert _wacht_op_status(doc, "done")
    r = client.get("/beheer")
    assert r.status_code == 200
    assert 'data-tel="totaal">1<' in r.text
    assert 'data-tel="done">1<' in r.text
    assert 'data-tel="pending">0<' in r.text
    assert 'data-tel="failed">0<' in r.text
    assert 'data-tel="queue">' in r.text
    assert 'data-tel="reconcile">niet bezig<' in r.text
    assert "Nog niet gedraaid" in r.text
    assert 'action="/beheer/reconcile"' in r.text
    assert "Loopt automatisch elke 60 minuten" in r.text


def test_beheer_reconcile(client: TestClient) -> None:
    app = client.app
    # via Samba toegevoegde map zonder meta.md
    los = _root(client) / "2026" / "2026-02-02_los"
    los.mkdir(parents=True)
    (los / "brief.pdf").write_bytes(_PDF)

    r = client.post("/beheer/reconcile", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/beheer?m=Gestart"
    assert _wacht_tot(lambda: app.state.laatste_rapport is not None)  # type: ignore[attr-defined]
    assert _wacht_tot(lambda: not app.state.reconcile_bezig)  # type: ignore[attr-defined]
    rapport = app.state.laatste_rapport  # type: ignore[attr-defined]
    assert rapport.meta_aangemaakt == 1
    assert (los / "meta.md").exists()
    assert _wacht_op(los / "brief.pdf.txt")

    r = client.get("/beheer")
    assert "Nog niet gedraaid" not in r.text
    assert "meta.md aangemaakt" in r.text


def test_beheer_reconcile_al_bezig(client: TestClient) -> None:
    app = client.app
    app.state.reconcile_bezig = True  # type: ignore[attr-defined]
    try:
        r = client.post("/beheer/reconcile", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/beheer?m=Al+bezig"
        assert app.state.laatste_rapport is None  # type: ignore[attr-defined]
        r = client.get("/beheer")
        assert 'data-tel="reconcile">bezig<' in r.text
        assert "disabled" in r.text
        assert client.get("/api/status").json()["reconcile_bezig"] is True
    finally:
        app.state.reconcile_bezig = False  # type: ignore[attr-defined]


# --- ingress op documentpagina en beheer -----------------------------------


def test_ingress_prefix_op_documentpagina(client: TestClient) -> None:
    _upload(client)
    for pad in (_DOC, "/beheer"):
        r = client.get(pad, headers={"X-Ingress-Path": _PREFIX})
        assert r.status_code == 200
        acties = re.findall(r'action="([^"]*)"', r.text)
        assert acties, pad
        for url in acties:
            assert url.startswith(_PREFIX + "/"), url
        assert f'data-status-url="{_PREFIX}/api/status"' in r.text
        if pad == _DOC:
            assert f'data="{_PREFIX}{_DOC}/bestand/a.pdf"' in r.text
            assert f'href="{_PREFIX}{_DOC}/bekijk/a.pdf">Open</a>' in r.text
    r = client.get(f"{_DOC}/bekijk/a.pdf", headers={"X-Ingress-Path": _PREFIX})
    assert r.status_code == 200
    assert f'src="{_PREFIX}{_DOC}/bestand/a.pdf"' in r.text
    assert f'href="{_PREFIX}{_DOC}">' in r.text

    r = client.post(
        f"{_DOC}/meta",
        data={"titel": "Test", "documentdatum": "2026-03-01"},
        headers={"X-Ingress-Path": _PREFIX},
        follow_redirects=False,
    )
    assert r.headers["location"] == f"{_PREFIX}{_DOC}?m=Opgeslagen"
