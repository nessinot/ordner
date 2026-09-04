# Ordner

Minimale digitale archiefkast voor documenten (facturen, bonnen, digitale post, etc.; privé of zakelijk) als lokale Home Assistant add-on via Ingress. Kernprincipe: **de bestanden op schijf zijn de waarheid**. Mappen, originelen, één leesbare `meta.md` per document en OCR-tekst als `.txt` ernaast. Alles blijft bruikbaar zonder de app. Geen database.

Werkpakketten en het bindende interface-contract staan in `werk/`. Houd het klein; ideeën gaan naar `IDEAS.md`.

## Ontwerpbeslissingen

| Onderwerp | Keuze |
|---|---|
| Naam | `ordner` overal (add-on slug, Python-package, `/share/ordner`). Repo-root is een add-on-repository (`repository.yaml`); de add-on zelf staat in `addon/` en dat is de Docker-build-context. |
| Mapnaam | `JJJJ/JJJJ-MM-DD_slug/` met de documentdatum zoals ingevuld bij aanmaak + slug van de titel. **Nooit hernoemen**; latere titel-/datumwijziging staat alleen in `meta.md`. Collision → `_2`, `_3`, … |
| Slug | lowercase, NFKD-normalisatie + combining characters strippen, alles buiten `[a-z0-9]` → `-`, herhaalde `-` samenvoegen, `-` aan de randen strippen, max 60 tekens, leeg → `document`. |
| Metadata | `meta.md`: YAML-frontmatter tussen `---`-regels + optionele body (vrije notities, wordt meegezocht). Geen OCR-tekst in `meta.md`. |
| OCR-tekst | Per bronbestand `<naam>.<ext>.txt` naast het origineel (`factuur.pdf` → `factuur.pdf.txt`). |
| `ocr`-status | `pending` (extraheerbare bestanden zonder `.txt`), `done` (alle extraheerbare bestanden hebben een `.txt`, of er zijn er geen), `failed` (extractie mislukt; reconciler probeert niet opnieuw tot "OCR opnieuw" de status reset). |
| Extraheerbaar | Extensies `.pdf .jpg .jpeg .png .heic` (case-insensitive). Andere bestanden worden opgeslagen en in `bestanden` opgenomen, maar niet geëxtraheerd. |
| Extractie pdf | `pdftotext -layout`; paginatelling via `pdfinfo`; te weinig tekst (< 50 tekens per pagina) → `ocrmypdf --force-ocr` met sidecar. |
| Extractie afbeelding | `.heic` → tijdelijke `.jpg` via `pillow_heif` + Pillow; daarna `tesseract`. |
| Subprocess | Uitsluitend via `extract.run_cmd` (asyncio subprocess, timeout 600 s). Tests mocken alleen deze functie. |
| Index | In-memory (`index.Index`), gebouwd bij start, bijgewerkt door app/worker, herbouwd door reconciler. Geen indexbestand op schijf. |
| Reconciler | Bij start, elke `reconcile_interval` s, en op knop. Synchroniseert `bestanden`, queued ontbrekende `.txt`, maakt `meta.md` voor mappen zonder, ingest `_inbox/`. |
| Inbox | `_inbox/` gepolld elke `inbox_interval` s; bestand met gelijke grootte in twee opeenvolgende polls → nieuw document (titel en tags uit de tekst, anders bestandsnaam; datum uit de tekst, anders vandaag). |
| Datum uit tekst | Bij elke upload (scherm 1 heeft geen datumveld; correctie op scherm 2) en bij de inbox. Tekst wordt *vóór* het aanmaken van de map gelezen (`ingest.lees_vooraf`), zodat de mapnaam klopt en niets hernoemd wordt. Sleutelwoorden op prioriteit: factuurdatum, notadatum, orderdatum, dagtekening, datum. Per sleutelwoord eerst de datum op dezelfde regel direct achter het woord, daarna kolomlayout: label zonder datum, datum in dezelfde kolom (tekenbereik hooguit 20 tekens uit elkaar) op de eerstvolgende niet-lege regel (`datum.py`). `meta.datumbron`: `gebruiker` (nooit automatisch overschreven), `tekst`, `upload`. Details: `werk/14-datum-uit-tekst.md`. |
| Titel en tags uit tekst | Suggestie (`suggestie.py`, pure functies): titel = alleen de afzender, bij twijfel leeg; heuristiek op prioriteit: bekende archieftitel in de tekst → naam achter "t.n.v." → eerste kolomcel met rechtsvorm (`B.V.` e.d., hoofdlettergevoelig) of instantiewoord (Gemeente …, Belastingdienst …) → bij korte tekst (bon, < 25 regels) de eerste bruikbare regel. Tags = documenttypewoorden als kopregel van een cel (factuur, offerte, polis, …). Cellen = splitsing op 2+ spaties. De inbox gebruikt de suggestie direct (anders bestandsnaam); het uploadformulier toont hem voorgevuld op scherm 2. `ingest.py` in twee fasen: `lees_vooraf` → `maak_document_uit_voorbereid`. Details: `werk/15a-titel-en-tagsuggestie.md`. |
| Tweestaps upload | Scherm 1 (`/upload`): alleen bestanden, minstens één. De server leest de tekst, bepaalt datum en suggesties en houdt alles als *openstaande upload* in het geheugen (`web/openstaand.py`, token in de URL, TTL 60 min, max 10; niets op schijf, weg bij herstart). Scherm 2 (`/upload/{token}`): alle velden voorgevuld; Opslaan maakt het document (datum ongewijzigd → bron uit de tekst/upload, gewijzigd → `gebruiker`), Annuleren gooit weg. Details: `werk/15b-tweestaps-upload.md`. |
| Zoeken | AND over alle woorden, hoofdletterongevoelig, over titel, omschrijving, tags, documentdatum, notities en alle `.txt`-teksten. Snippet ±80 tekens. Sortering documentdatum desc. `_inbox`/`_prullenbak` nooit in de index. |
| Prullenbak | `_prullenbak/<mapnaam>`; bij conflict `<mapnaam>_<JJJJMMDD-HHMMSS>`. |
| Schrijven | `meta.md` en `.txt` altijd via tempbestand in dezelfde map + `os.replace()`. |
| Web | FastAPI + Jinja2, geen JS-framework, geen build-stap. Vanilla JS alleen voor upload-voortgang (scherm 1 volgt de redirect naar scherm 2) en status-polling; scherm 2 werkt zonder JS. Alle links via de Jinja-global `url_for` (pad inclusief Ingress `root_path`). |
| Base image | HA Debian-base bookworm; apt: `python3 python3-venv ocrmypdf tesseract-ocr-nld tesseract-ocr-eng poppler-utils libheif1`. |

## Niet in v1

Meerdere gebruikers, versiebeheer, autoclassificatie, tag-beheer, map-hernoemen, MCP-server, "alles opnieuw OCR'en", prullenbak legen/terugzetten. Ideeën → `IDEAS.md`.

## Conventies

- Python ≥ 3.11, type hints overal, `from __future__ import annotations` bovenaan elke module.
- Nederlandse namen voor domeinbegrippen, Engelse namen voor techniek.
- Geen globale state behalve `Settings`; alles wordt geïnjecteerd.
- Eigen excepties per module (`MetaFout`, `OngeldigPad`, `ExtractieFout`); nooit bare `except`.
- Logging via `logging.getLogger(__name__)`.
- Tests: pytest, `tmp_path`, geen netwerk, geen echte OCR-tools. Fixtures in `tests/conftest.py`. `pytest` moet groen zijn bij afronden van elk pakket.
- Windows-dev: paden via `pathlib`, `os.replace` voor atomic writes, tekstbestanden altijd `encoding="utf-8"`.
- Commit per pakket met bericht `pakket NN: <titel>`; daarna afvinken in `werk/STATUS.md`.
- **Vóór elke push:** release notes in `addon/CHANGELOG.md` (gebruikerstaal, nieuwste bovenaan, kop `## x.y.z (datum)`) en de regel in `werk/STATUS.md` › Releases (technisch, voor de volgende sessie). Bij nieuw gedrag een versiebump. `tests/test_addon_config.py` faalt als de bovenste changelog-kop niet gelijk is aan `version` in `config.yaml`.
- Lokaal draaien: `$env:ORDNER_DATA="./data"; uvicorn --app-dir addon ordner.web.app:app --reload`.

## Draaien

- **Lokaal**: `ORDNER_DATA=./data uvicorn --app-dir addon ordner.web.app:app --reload` (PowerShell: `$env:ORDNER_DATA="./data"; uvicorn ...`). Zonder OCR-tools op het pad worden documenten `failed`.
- **Add-on**: Add-on store › ⋮ › Repositories › `https://github.com/nessinot/ordner` toevoegen › Ordner › Installeren (repo moet publiek zijn). Updaten = `version` in `addon/config.yaml` ophogen, `addon/CHANGELOG.md` aanvullen (tabblad Changelog in HA) en pushen. `run.sh` zet `ORDNER_DATA=/share/ordner` en de opties uit `config.yaml` als `ORDNER_*`-omgevingsvariabelen; uvicorn luistert op 8099 voor Ingress. `run.sh` en `Dockerfile` moeten LF-regeleinden houden (`.gitattributes`).
- Gebruikersdocumentatie in `addon/DOCS.md`, release notes in `addon/CHANGELOG.md`, installatie in `README.md`.
