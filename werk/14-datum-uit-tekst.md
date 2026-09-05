# Pakket 14 — Documentdatum uit de tekst

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/14-datum-uit-tekst.md`. Dit pakket is gebouwd en gecommit (release 0.5.0, 2026-09-04; kolomlayout in 0.6.0); gebruik dit bestand als naslag bij vervolgwerk aan datumherkenning.

**Doel:** Documenten die zonder datum worden aangeleverd (uploadformulier met leeg datumveld, of via `_inbox/`) krijgen automatisch de datum die in het document staat, zodat oude documenten die nu pas worden ingescand een historisch juiste documentdatum én mapnaam krijgen. Zonder treffer wordt het vandaag.

**Lees eerst:** `werk/00-contract.md` (Ontwerpbeslissingen "Datum uit tekst", interfaces `ordner/datum.py` en `ordner/ingest.py`), `addon/DOCS.md` (sectie "Documentdatum").

## Beslissingen (afgestemd met Bas op 2026-09-04)

1. **Alleen als de gebruiker geen datum gaf.** Het datumveld in het uploadformulier is optioneel en staat standaard leeg. Ingevulde datum → bron `gebruiker`, gedrag als vroeger (map aanmaken, OCR op de achtergrond). Leeg veld en inbox → tekst eerst lezen.
2. **Nooit hernoemen blijft.** Daarom wordt de tekst *vóór* het aanmaken van de map gelezen, zodat de map direct de gevonden datum in zijn naam krijgt. Prijs: bij foto's en scans wacht de gebruiker op tesseract (5–30 s). De uploadpagina toont daarbij "Bestanden ontvangen, tekst lezen…". Niemand wacht op de inbox.
3. **Bronregistratie** in `meta.md`: `datumbron: gebruiker | tekst | upload`. `gebruiker` wordt nooit automatisch overschreven. Wijzigt de gebruiker later de datum in het formulier, dan wordt de bron `gebruiker`; alleen tags/titel wijzigen laat de bron staan. Oude `meta.md` zonder het veld telt als `gebruiker`.
4. **Sleutelwoorden in prioriteitsvolgorde:** factuurdatum, notadatum, orderdatum, dagtekening, datum, afdrukdatum (0.10.1; laagste prioriteit omdat een printdatum later kan liggen dan de documentdatum). Optionele spatie ("factuur datum"), optionele dubbele punt, hoofdletterongevoelig. Letter-lookarounds zodat "Vervaldatum"/"Betaaldatum"/"Geboortedatum" niet matchen op "datum".
5. **De datum hoort bij het woord** als hij op dezelfde regel staat, direct achter het woord, met alleen spaties (max 60, vanwege `pdftotext -layout`-kolommen) en een optionele dubbele punt ertussen.
   **Kolomlayout (0.6.0, afgestemd 2026-09-04):** staat er geen datum achter het woord, dan telt de eerstvolgende niet-lege regel als waarderegel. Daarin wint de datum waarvan het tekenbereik het dichtst bij dat van het label ligt (afstand tussen de bereiken, 0 bij overlap; werkt voor links- en rechtsuitgelijnde kolommen). Afstand hooguit `datum._MAX_KOLOMAFSTAND` (20 tekens), anders geen treffer: een verkeerde datum in de mapnaam is erger dan de uploaddatum, want de map wordt nooit hernoemd. Tabs worden geëxpandeerd. Per sleutelwoord gaan alle regeltreffers vóór alle kolomtreffers (sterkste bewijs eerst); een kolom-"factuurdatum" wint wél van een regel-"datum". Alleen de eerstvolgende regel, niet verder naar beneden; meerregelige labels ("Factuur-" / "datum") vallen buiten scope.
6. **Notaties:** `12-03-2024`, `12/03/2024`, `12.03.2024`, `2024-03-12`, `12 maart 2024`, `12 mrt 2024`, `12 mrt. 2024`, tweecijferig jaar (`12-03-24` → 2024; valt het boven volgend jaar dan 19xx). Altijd dag-maand, nooit maand-dag. Nederlandse en Engelse maandnamen.
7. **Plausibiliteit:** jaar tussen 1990 (`datum.MIN_JAAR`) en volgend jaar; ongeldige kalenderdatums (31-02) worden overgeslagen en de zoektocht gaat verder.
8. **Meerdere bestanden:** het eerste bestand (in uploadvolgorde) dat een treffer oplevert bepaalt de datum. Alle gelezen teksten worden direct als `.txt` weggeschreven, dus die bestanden hoeven niet meer door de OCR-queue. Bestanden waarvan het lezen mislukt gaan alsnog naar de queue (de worker zet dan zo nodig `failed`).

## Maakt / wijzigt

- `addon/ordner/datum.py` (nieuw): `vind_datum(tekst, vandaag=None) -> DatumTreffer | None`. Pure functie, geen I/O.
- `addon/ordner/ingest.py` (nieuw): `maak_document_uit_bestanden(...)` als enige aanmaakpad voor upload en inbox; `maak_tekstlezer(talen)` maakt een synchrone wrapper om `extract_bestand` (eigen event loop via `asyncio.run`, bedoeld voor `asyncio.to_thread`).
- `meta.py`: `DatumBron`, veld `Meta.datumbron`, `schrijf_txt` (verhuisd uit `worker.py`; `worker._schrijf_txt` is een alias). `datumbron` staat als laatste sleutel in de frontmatter.
- `storage.py`: `Archief.maak_document(..., datumbron="gebruiker")`.
- `index.py`: `Reconciler(..., lees_tekst=None)`; `_ingest` gebruikt `maak_document_uit_bestanden`.
- `web/app.py`: `lees_tekst = maak_tekstlezer(settings.ocr_talen)` op `app.state.lees_tekst` en in de reconciler.
- `web/routes.py`: `POST /upload` roept `maak_document_uit_bestanden` aan via `asyncio.to_thread`; `_upload_context` geeft een lege datum; `document_meta` zet `datumbron="gebruiker"` als de datum wijzigt.
- Templates: `upload.html` (hint, "optioneel", bezig-melding), `document.html` (badge "datum uit tekst" / "datum van upload"); `app.js` toont de bezig-melding na de upload en maakt de voortgangsbalk indeterminate.
- Tests: `tests/test_datum.py`, `tests/test_ingest.py`; uitbreidingen in `test_meta.py`, `test_storage.py`, `test_index.py`, `test_web.py`.
- Docs: `CLAUDE.md`, `werk/00-contract.md`, `addon/DOCS.md`, `README.md`.

## Let op: gelijktijdigheid

`maak_document_uit_bestanden` draait voor het uploadformulier in een thread (`asyncio.to_thread`) en voor de inbox in de reconciler-thread, terwijl de OCR-worker op de event loop `meta.md` leest en schrijft. Daarom worden bestanden pas ná de laatste schrijfactie aan de queue aangeboden; eerder queuen gaf een lost update en op Windows een `PermissionError` bij `os.replace` (gevonden met `pytest -m e2e`). De bredere race tussen reconciler-thread en worker bestaat al sinds pakket 07 en is hier niet aangepakt.

## Bekende beperkingen / vervolg

- **Kolomlayout** wordt sinds 0.6.0 herkend (beslissing 5). De tolerantie van 20 tekens is niet geijkt op echte facturen (er lagen geen `.txt`-bestanden in `data/`); bij een misser in de praktijk eerst de `.txt` bekijken en dan `_MAX_KOLOMAFSTAND` of de regelkeuze bijstellen, met een test erbij.
- Alleen Nederlandse sleutelwoorden. Engelse ("Invoice date") zijn bewust weggelaten; toevoegen is één regel in `_SLEUTELWOORDEN`.
- Het lezen vooraf gebeurt per upload sequentieel; bij veel bestanden zonder datum in één upload duurt het opslaan navenant langer.
- Bestaande documenten krijgen met terugwerkende kracht geen datum uit tekst; `datumbron` blijft `gebruiker`. Een "datum opnieuw bepalen"-knop staat in `IDEAS.md`.
