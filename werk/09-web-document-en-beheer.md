# Pakket 09 — Web document en beheer

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/09-web-document-en-beheer.md`. Voer pakket 09 uit. Draai `pytest`. Commit met bericht `pakket 09: web document en beheer`. Vink af in `werk/STATUS.md`.

**Doel:** volledige documentpagina en beheerpagina, plus status-API en polling.

**Lees eerst:** `werk/00-contract.md` (tabel Routenamen, Interfaces `index.py` en `worker.py`).
**Vereist:** pakket 08.

## Maakt / wijzigt

- `ordner/web/templates/document.html` (vervangt placeholder), `beheer.html`
- Routes toevoegen in `ordner/web/routes.py`
- `ordner/web/static/app.js` uitbreiden
- Tests toevoegen in `tests/test_web.py`

## Specificatie

### Documentpagina `GET /doc/{jaar}/{map}` (`document`)
- Kop: titel, documentdatum, tags als badges, `ocr`-badge (pending/failed).
- `<section data-ocr="{{ meta.ocr }}" data-rel="{{ rel }}">` om de hele pagina zodat JS kan pollen.
- **Bewerkformulier** (`POST` → `document_meta`): titel (required), omschrijving (textarea), documentdatum (`type="date"`), tags (komma-gescheiden). Knop "Opslaan". Tekst eronder: "De mapnaam verandert niet."
- **Notities**: `meta.notities` tonen als `<pre class="notities">` (alleen tonen; bewerken niet in v1).
- **Bestanden**: per bestand een blok met naam, "Open"-link (`bestand`; sinds 0.9.1 zonder `target="_blank"`, zie STATUS), badge "tekst aanwezig" als er een `.txt` is, en inline weergave: extensie in `.jpg .jpeg .png` → `<img src=... loading="lazy">`; `.pdf` → `<object type="application/pdf" data="..." width="100%" height="600">Kan de pdf hier niet tonen — <a>Open</a></object>`; overige → alleen de link. (HEIC niet inline: browsers tonen het niet; alleen link.)
- **Bestand toevoegen** (`POST` multipart → `document_bestanden`): `bestanden` multiple, zelfde `accept` als upload, geen `capture`.
- **OCR opnieuw** (`POST` → `document_ocr`): knop.
- **Verwijderen** (`POST` → `document_verwijder`): knop met `onclick="return confirm('Naar de prullenbak?')"`; zonder JS gewoon submit.

### Routes
- `POST /doc/{jaar}/{map}/meta` (`document_meta`): `veilig_pad`; `meta = lees_meta`; titel gestript verplicht (anders 400 met pagina + melding); datum parsen (`date.fromisoformat`, ongeldig → 400); tags splitsen; velden zetten; `schrijf_meta`; `index.herlaad`; 303 naar `document` met `?m=Opgeslagen`. **Map wordt niet hernoemd.**
- `POST /doc/{jaar}/{map}/bestanden` (`document_bestanden`): per upload `voeg_bestand_toe` + `enqueue` als extraheerbaar; `index.herlaad`; 303 met `?m=Toegevoegd`.
- `POST /doc/{jaar}/{map}/ocr` (`document_ocr`): voor elk extraheerbaar bestand in `meta.bestanden`: `.txt` verwijderen als aanwezig; `meta.ocr = "pending"` (of `"done"` als er geen extraheerbare bestanden zijn); `schrijf_meta`; `enqueue` voor elk; `index.herlaad`; 303 met `?m=OCR gestart`.
- `POST /doc/{jaar}/{map}/verwijder` (`document_verwijder`): `rel = archief.relatief(doc)`; `archief.naar_prullenbak(doc)`; `index.verwijder(rel)`; 303 naar `zoeken` met `?m=Verplaatst naar prullenbak`.
- `GET /api/status` (`status`): JSON `{"queue": queue.lengte, "bezig": sorted(queue.bezig), "reconcile_bezig": app.state.reconcile_bezig, "tellingen": index.tellingen()}`; met `?rel=<rel>` bovendien `"ocr": index.docs[rel].meta.ocr` (of `null` als onbekend).
- `GET /beheer` (`beheer`, vervangt placeholder): tellingen (totaal/pending/done/failed), queue-lengte, lijst `bezig`, laatste `ReconcileRapport` (velden) of "nog niet gedraaid", knop "Cache verversen en ontbrekende tekst extraheren" (`POST` → `beheer_reconcile`), en een korte uitleg: "Loopt automatisch elke N minuten; gebruik deze knop na wijzigingen via Samba."
- `POST /beheer/reconcile` (`beheer_reconcile`): als `app.state.reconcile_bezig` → 303 met `?m=Al bezig`. Anders `reconcile_bezig = True` en `asyncio.create_task(_run())` waarbij `_run` doet: `try: app.state.laatste_rapport = await asyncio.to_thread(reconciler.run) finally: app.state.reconcile_bezig = False`. 303 met `?m=Gestart`. Bewaar de task op `app.state` zodat hij niet weggegarbaged wordt.

### `app.js` uitbreiden
- Documentpagina: als `section[data-ocr="pending"]` bestaat → elke 3 s `fetch(statusUrl + "?rel=" + encodeURIComponent(rel))`; als `ocr` `done` of `failed` → `location.reload()`. `statusUrl` komt uit een `data-status-url`-attribuut op `<body>` (gerenderd met `url_for("status")`), zodat het onder Ingress klopt.
- Beheerpagina: elke 3 s status ophalen en de elementen `[data-tel="totaal"]`, `pending`, `done`, `failed`, `queue`, `reconcile` bijwerken; als `reconcile_bezig` van `true` naar `false` gaat → `location.reload()` (zodat het rapport verschijnt).

## Tests

- Upload → `POST .../meta` met nieuwe titel en datum → `meta.md` bijgewerkt, **mapnaam ongewijzigd**, 303.
- `POST .../meta` zonder titel → 400.
- `POST .../bestanden` met jpg → in `bestanden`; `tesseract` uiteindelijk aangeroepen (poll tot `.txt` bestaat).
- `POST .../ocr` na afgeronde OCR → `.txt` verwijderd (of direct opnieuw aangemaakt door de queue: test daarom dat `pdftotext` een tweede keer in `mock_cmd.calls` staat).
- `POST .../verwijder` → map in `_prullenbak`, `GET /doc/...` → 404, niet meer in `GET /?q=`.
- `GET /api/status` → JSON met keys `queue`, `bezig`, `reconcile_bezig`, `tellingen`; met `?rel=` ook `ocr`.
- `GET /beheer` → 200 met tellingen.
- `POST /beheer/reconcile` → 303; daarna poll (max 2 s) tot `app.state.laatste_rapport` gezet is.
- Ingress-prefix ook op de documentpagina: alle `action="` beginnen met het prefix; `data-status-url` ook.

## Buiten scope

Add-on-packaging (10).
