# Pakket 12 — End-to-end

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/12-end-to-end.md`. Voer pakket 12 uit. Draai `pytest`, `pytest -m e2e` en (als Docker beschikbaar is) `pytest -m container`. Commit met bericht `pakket 12: end-to-end`. Vink af in `werk/STATUS.md`.

**Doel:** automatisch bewijzen dat Ordner als geheel werkt — echte browser tegen een echte server, en (als Docker beschikbaar is) het echte add-on-image met echte OCR-tools. Dit vervangt het grootste deel van de handmatige checklist.

**Lees eerst:** `werk/00-contract.md` (Conventies "Testlagen", Routenamen).
**Vereist:** pakket 10.

## Twee lagen

| Laag | Marker | Wat | Vereist op de dev-machine |
|---|---|---|---|
| Browser | `e2e` | Playwright (Chromium, mobiele viewport) tegen een lokaal gestarte uvicorn. Test de UI-flows en het JS-gedrag. OCR-tools zijn optioneel: zonder tools wordt de status `failed` en wordt dát pad getest. | `pip install -r requirements-dev.txt` en éénmalig `playwright install chromium` |
| Container | `container` | Bouwt het add-on-image, start het met een gemounte archiefmap en test via HTTP met **echte** pdftotext/ocrmypdf/tesseract. | Docker (bijv. Docker Desktop). Ontbreekt Docker → alle tests in deze laag worden geskipt met reden "docker niet gevonden". |

Standaard `pytest` draait géén van beide lagen (`addopts = "-m 'not e2e and not container'"` in `pyproject.toml`); ze zijn te traag voor de normale loop.

## Maakt / wijzigt

- `requirements-dev.txt`: `pytest-playwright` toevoegen.
- `pyproject.toml`: markers `e2e` en `container` registreren; `addopts` zoals hierboven.
- `tests/fixtures/maak_fixtures.py` + de gegenereerde bestanden `tests/fixtures/tekst.pdf`, `scan.pdf`, `foto.jpg`, `foto.heic`, `foto.png`. Het script maakt ze deterministisch aan; de bestanden zelf worden ook gecommit (klein houden: < 100 KB per stuk).
- `tests/e2e/__init__.py`, `tests/e2e/conftest.py`, `tests/e2e/test_browser.py`, `tests/e2e/test_container.py`.
- `README.md`: sectie "Testen" uitbreiden met de drie commando's en wat je ervoor nodig hebt.

## Testbestanden (`tests/fixtures/maak_fixtures.py`)

Geen extra dependencies; alleen Pillow en pillow-heif (zitten al in requirements).

- `tekst.pdf`: een handgeschreven minimale PDF met een echte tekstlaag (één pagina, Helvetica, regel `Ordner testdocument FACTUURNUMMER 20260903`). Schrijf de PDF-bytes zelf uit (catalog, pages, page, font, content-stream met `BT /F1 24 Tf 72 720 Td (…) Tj ET`, xref-tabel). Zo'n 30 regels Python; valideer door hem in een browser te openen.
- `foto.png` / `foto.jpg`: 1200×400 witte afbeelding met in grote zwarte letters `ORDNER SCANTEST BONNETJE` (Pillow `ImageDraw`, standaardfont vergroot via `ImageFont.load_default(size=72)` — beschikbaar in Pillow ≥ 10.1). Groot en contrastrijk zodat Tesseract het zeker leest.
- `foto.heic`: dezelfde afbeelding via pillow-heif opgeslagen als HEIC.
- `scan.pdf`: `foto.png` opgeslagen als PDF via Pillow (`img.save("scan.pdf")`) — een "gescande" pdf zonder tekstlaag, dus het ocrmypdf-pad.

## Browser-laag (`tests/e2e/test_browser.py`)

### Fixture `server` (session-scope, in `tests/e2e/conftest.py`)
- `tmp_path_factory.mktemp("archief")`; env `ORDNER_DATA=<tmp>`, `ORDNER_INBOX_INTERVAL=1`, `ORDNER_RECONCILE_INTERVAL=3600`.
- `subprocess.Popen([sys.executable, "-m", "uvicorn", "ordner.web.app:app", "--port", "8765"], env=...)`; wacht (max 20 s) tot `GET http://127.0.0.1:8765/` 200 geeft; yield `(url, archiefmap)`; teardown `terminate()` + `wait()`.
- `ocr_beschikbaar = bool(shutil.which("tesseract") and shutil.which("pdftotext"))`.
- Playwright: `browser_context_args` met `viewport={"width": 390, "height": 844}`, `is_mobile=True`, `has_touch=True`.

### Tests (alle `@pytest.mark.e2e`)
1. **Upload via formulier**: `/upload` → `set_input_files` met `tekst.pdf` + `foto.jpg` → titel "E2E factuur" → klik Opslaan → URL bevat `/doc/` → h1 bevat de titel → op schijf bestaat `<jaar>/<datum>_e2e-factuur/` met beide bestanden en `meta.md`.
2. **Status-polling**: op die documentpagina wachten (`page.wait_for_function`, timeout 90 s) tot `section[data-ocr]` niet meer `pending` is. Verwacht `done` als `ocr_beschikbaar`, anders `failed`. Beide bewijzen dat het JS-pollen en de herlaad werken.
3. **Zoeken**: `/?q=e2e` toont de titel. Als `ocr_beschikbaar`: `/?q=factuurnummer` toont de titel met bron `tekst.pdf`.
4. **Bewerken zonder hernoemen**: titel wijzigen naar "E2E factuur bewerkt" → opslaan → h1 bijgewerkt → mapnaam op schijf ongewijzigd.
5. **Bestand toevoegen**: `foto.png` toevoegen → staat in de bestandslijst en in `meta.md`.
6. **OCR opnieuw**: klik → melding "OCR gestart" → status wordt weer `pending` en daarna `done`/`failed`.
7. **Verwijderen met confirm**: `page.once("dialog", lambda d: d.accept())` → klik Verwijderen → landt op `/` met melding → map staat in `_prullenbak/`.
8. **Inbox**: kopieer `foto.jpg` naar `<archief>/_inbox/` → binnen 15 s toont `/?q=foto` een document (poll met `page.reload()`).
9. **Beheer**: `/beheer` toont tellingen; klik reconcile → binnen 10 s verschijnt een rapport (poll).
10. **Ingress-prefix**: nieuwe context met `extra_http_headers={"X-Ingress-Path": "/api/hassio_ingress/abc"}` → `/` openen → alle `a[href]`, `form[action]`, `link[rel=stylesheet]` en `body[data-status-url]` beginnen met `/api/hassio_ingress/abc/`. (Niet doorklikken: de lokale server serveert dat prefix niet.)

## Container-laag (`tests/e2e/test_container.py`)

### Fixture `container` (session-scope)
- `shutil.which("docker")` ontbreekt → `pytest.skip("docker niet gevonden")`.
- `docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm -t ordner-e2e .` (timeout 15 min; output bij falen tonen).
- Archiefmap `<tmp>/share` en `<tmp>/data/options.json` met `{"ocr_talen": "nld+eng", "ocr_parallel": 2, "reconcile_interval": 3600}` (nodig omdat `run.sh` `bashio::config` gebruikt).
- Vooraf in `<tmp>/share/2025/2025-01-01_pending-test/` een `meta.md` met `ocr: pending`, `bestanden: [foto.png]` en `foto.png` zonder `.txt` neerzetten → test "pending wordt na start opgepakt".
- `docker run -d --rm --name ordner-e2e -p 18099:8099 -v <tmp>/share:/share/ordner -v <tmp>/data:/data ordner-e2e`; wacht tot `GET http://127.0.0.1:18099/` 200 (max 60 s); yield; teardown `docker stop ordner-e2e`.
- Op Windows: paden voor `-v` als absolute Windows-paden doorgeven; Docker Desktop vertaalt ze.

### Tests (alle `@pytest.mark.container`, via `httpx`)
1. `GET /` → 200.
2. **Pending bij start**: binnen 60 s bestaat `<share>/2025/2025-01-01_pending-test/foto.png.txt` en bevat `SCANTEST`; `meta.md` heeft `ocr: done`.
3. **Digitale pdf**: upload `tekst.pdf` → binnen 60 s `.txt` met `FACTUURNUMMER` (pdftotext-pad; bewijs dat ocrmypdf níet nodig was: snel klaar, tekst exact).
4. **Gescande pdf**: upload `scan.pdf` → binnen 120 s `.txt` met `SCANTEST` (ocrmypdf-pad).
5. **HEIC**: upload `foto.heic` → binnen 60 s `.txt` met `BONNETJE` (heic→jpg→tesseract).
6. **Zoeken op OCR-tekst**: `GET /?q=bonnetje` bevat de titel van het HEIC-document.
7. **Ingress-header** in de container: zelfde controle als browser-test 10, via httpx + eenvoudige regex over `href="`/`action="`.
8. **Inbox via volume**: kopieer `foto.jpg` naar `<share>/_inbox/` → binnen 30 s is `_inbox/` leeg en bestaat een documentmap van vandaag met `foto.jpg`.
9. **Herstart**: `docker restart ordner-e2e` → na opnieuw bereikbaar zijn zijn alle eerder gemaakte documenten nog zichtbaar in `GET /`.

## Optioneel op de dev-machine (niet vereist voor dit pakket)

Om de browser-laag met echte OCR te draaien zonder Docker:
```
winget install UB-Mannheim.TesseractOCR oschwartz10612.Poppler ArtifexSoftware.GhostScript
pip install ocrmypdf
```
Tesseract-installer: Nederlandse taaldata aanvinken. Zorg dat `tesseract`, `pdftotext`, `pdfinfo` en `gs` in `PATH` staan. Voor de container-laag: `winget install Docker.DockerDesktop` (vereist WSL2).

## Klaar als

- `pytest` groen (unit-laag ongewijzigd).
- `pytest -m e2e` groen op deze machine (zonder OCR-tools: status-pad `failed`).
- `pytest -m container` groen, óf geskipt met reden "docker niet gevonden" — in dat geval noteren in `STATUS.md`: "container-laag nog niet gedraaid; draai `pytest -m container` zodra Docker beschikbaar is".
- Commit `pakket 12: end-to-end`.

## Buiten scope

Alles wat een echte telefoon of een echte Home Assistant-installatie vereist (pakket 11).
