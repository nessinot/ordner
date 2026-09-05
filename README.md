# Ordner

Vroeger gingen afschriften, nota's, bonnetjes en andere belangrijke papieren in een ordner. Een map per jaar, een tabblad per onderwerp, en je wist dat alles er lag als je het nodig had. Ordner brengt die eenvoud terug als lokale Home Assistant add-on: een digitale ordner voor je documenten.

Elk document krijgt een eigen map op schijf met het origineel erin. De tekst van pdf's en foto's wordt gelezen en als gewoon tekstbestand ernaast gezet, en de gegevens over het document staan in één leesbaar `meta.md`. Geen database, niets om te ontcijferen. Alles blijft bruikbaar met de Verkenner, Samba of een HA-backup, ook zonder de app.

In de app upload je documenten, zoek je erin en bekijk je ze. Uploaden is twee stappen: bestanden kiezen, en dan de titel, datum en tags controleren die Ordner uit het document heeft gelezen. Dat is alles wat een ordner hoeft te doen.

Gebruikersdocumentatie staat in [`addon/DOCS.md`](addon/DOCS.md) en verschijnt op het tabblad "Documentatie" van de add-on.

## Installatie via de Add-on store

1. **Instellingen › Add-ons › Add-on store › ⋮ (rechtsboven) › Repositories** › `https://github.com/nessinot/ordner` toevoegen.
2. De sectie **Ordner** verschijnt in de store (zo nodig ⋮ › Controleren op updates). Open **Ordner** › **Installeren**. De build draait op de HA-machine en duurt de eerste keer enkele minuten (Debian-image plus OCR-tools).
3. Start de add-on en zet **Toon in zijbalk** aan. Je documenten komen in `/share/ordner`.

Updaten: `version` in `addon/config.yaml` ophogen, committen, pushen; in HA ⋮ › Controleren op updates → knop **Update** bij Ordner. Zonder versiebump ziet HA geen update.

Voorwaarde: de GitHub-repo moet **publiek** zijn; de Supervisor kent geen credentials.

Opties (`ocr_talen`, `ocr_parallel`, `reconcile_interval`) staan op het tabblad Configuratie; zie `addon/DOCS.md`.

## Lokaal ontwikkelen

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:ORDNER_DATA = "./data"
uvicorn --app-dir addon ordner.web.app:app --reload
```

Op Linux/macOS: `ORDNER_DATA=./data uvicorn --app-dir addon ordner.web.app:app --reload`.

De app draait dan op <http://127.0.0.1:8000> met `./data` als ordner. OCR werkt lokaal alleen als `pdftotext`, `pdfinfo`, `ocrmypdf` en `tesseract` op het pad staan; zonder die tools krijgen documenten de status `failed`.

## Tests

Drie lagen; alleen de eerste draait met kaal `pytest`.

| Commando | Wat | Nodig |
|---|---|---|
| `pytest` | Unit-tests, gemockte OCR-tools, geen netwerk. | `pip install -r requirements-dev.txt` |
| `pytest -m e2e` | Browser-laag: Playwright (Chromium, mobiele viewport) tegen een lokaal gestarte uvicorn. Zonder OCR-tools op het pad wordt het `failed`-pad getest, met tools het `done`-pad. | daarnaast éénmalig `playwright install chromium` |
| `pytest -m container` | Container-laag: bouwt het add-on-image en test het via HTTP met echte pdftotext/ocrmypdf/tesseract. Wordt geskipt met reden "docker niet gevonden" als Docker ontbreekt. | Docker (bijv. Docker Desktop) |

De testbestanden in `tests/fixtures/` (pdf met tekstlaag, gescande pdf, png/jpg/heic) worden gegenereerd door `python tests/fixtures/maak_fixtures.py` en zijn meegecommit.

Optioneel, om de browser-laag lokaal met echte OCR te draaien:

```powershell
winget install UB-Mannheim.TesseractOCR oschwartz10612.Poppler ArtifexSoftware.GhostScript
pip install ocrmypdf
```

Vink in de Tesseract-installer de Nederlandse taaldata aan en zorg dat `tesseract`, `pdftotext`, `pdfinfo` en `gs` in `PATH` staan.

## Structuur

- `repository.yaml`: maakt van de repo een add-on-repository voor de Add-on store.
- `addon/`: de add-on (`config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `DOCS.md`); dit is de Docker-build-context.
- `addon/ordner/`: het Python-package; `addon/ordner/web/` de FastAPI-app met templates.
- `tests/`: pytest.
- `CLAUDE.md`: ontwerpbeslissingen en conventies.
- `werk/`: werkpakketten en het bindende interface-contract (`werk/00-contract.md`).
- `IDEAS.md`: wat bewust niet in v1 zit.
