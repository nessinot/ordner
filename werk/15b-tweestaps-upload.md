# Pakket 15b — Tweestaps upload met suggesties

> **Agent-prompt:** Lees `werk/00-contract.md`, `werk/14-datum-uit-tekst.md`, `werk/15a-titel-en-tagsuggestie.md` en `werk/15b-tweestaps-upload.md`. Dit pakket is gebouwd en gecommit (release 0.9.0, 2026-09-04); gebruik dit bestand als naslag bij vervolgwerk aan de upload. Afwijkingen bij het bouwen: (1) `extract._heic_naar_jpg` vertaalt PIL-fouten naar `ExtractieFout`, omdat scherm 1 nu altijd leest en een kapotte `.heic` anders een 500 gaf; (2) scherm 2 gebruikt één formulier met een tweede knop met `formaction`+`formnovalidate` voor Annuleren; (3) bij Opslaan wordt de openstaande upload *vóór* het aanmaken uit de store gehaald, zodat een dubbel verzoek nooit een tweede document maakt. Zie `werk/00-contract.md` › Wijzigingen.

**Doel:** Uploaden wordt twee schermen. Scherm 1: alleen bestanden kiezen. Ordner leest dan de tekst, bepaalt datum, titel- en tagsuggestie. Scherm 2: alle velden van het document, voorgevuld; de gebruiker corrigeert en slaat op. Zo typt niemand meer een titel over die al in het document staat, en ziet de gebruiker vóór het opslaan wat er in de mapnaam komt (datum en slug worden immers nooit hernoemd).

**Lees eerst:** `werk/00-contract.md` (Routenamen, `ingest.py`, `suggestie.py`), `werk/15a-titel-en-tagsuggestie.md` (fase-splitsing `lees_vooraf`/`maak_document_uit_voorbereid`), `addon/ordner/web/routes.py` (upload-routes, `_redirect`, `_upload_context`), `addon/ordner/web/templates/upload.html`, `addon/ordner/web/static/app.js` (XHR-upload met voortgang), `tests/test_web.py` (upload-tests), `tests/e2e/test_browser.py` (`test_upload_via_formulier`).

## Beslissingen (afgestemd met Bas op 2026-09-04)

1. **Scherm 1 is strikt alleen bestanden.** `GET /upload` toont een bestandskiezer, de hint over pdf's en foto's, de voortgangsbalk en één knop "Verder". Geen titel-, datum- of tagveld. Minstens één bestand is verplicht (400 met melding "Kies minstens één bestand."); een document zonder bestanden aanmaken kan via de upload niet meer. Wie later een bestand wil toevoegen gebruikt de documentpagina, zoals nu.
2. **Af of weg; niets wordt bewaard.** Tussen scherm 1 en 2 moet de server de bestanden vasthouden, want een HTML-formulier kan ze niet opnieuw meesturen. Dat is de *openstaande upload*: de bytes, de gelezen tekst, de datum en de suggesties, uitsluitend in het geheugen (`app.state.openstaand`), onder een willekeurig token (`secrets.token_urlsafe(16)`) in de URL van scherm 2. `POST /upload` leest de bestanden, draait `lees_vooraf` (in een thread, zoals nu) en `stel_voor`, zet de openstaande upload klaar en doet 303 naar `GET /upload/{token}`. Er komt **niets op schijf** vóór Opslaan: geen map in het archief, niets in `_inbox/`, geen tempbestanden buiten de tempmap die `lees_vooraf` zelf al opruimt. Een openstaande upload verdwijnt bij opslaan, annuleren, herstart of verlopen (3); dan kiest de gebruiker de bestanden opnieuw.
3. **Vuilnisbak, geen bewaarfunctie.** Wie na scherm 1 het tabblad sluit laat bytes in het geheugen achter. Daarom verloopt een openstaande upload na `_TTL` (60 minuten) en zijn er hooguit `_MAXIMUM` (10); bij een nieuwe upload worden verlopen en overtollige (oudste eerst) weggegooid. Verlopen of onbekend token → 303 naar `GET /upload` met melding "Deze upload is verlopen; kies de bestanden opnieuw." (geen 404: de gebruiker heeft niets fout gedaan). Geen achtergrondtaak; opruimen alleen bij aanmaken.
4. **Scherm 2 toont alles voorgevuld.** `GET /upload/{token}`: de bestandslijst (naam, grootte; niet wijzigbaar), en het formulier met: titel = titelsuggestie (leeg veld met placeholder als de suggestie leeg is; `required`), omschrijving leeg, documentdatum = gevonden datum of vandaag (altijd gevuld, `required`), tags = tagsuggestie komma-gescheiden. Onder het datumveld een label zoals op de documentpagina: "datum uit tekst" of "geen datum gevonden, vandaag". Onder de titel een gedempte hint wanneer die uit het archief of de tekst komt ("voorstel uit het document"; leeg bij bron `geen`). Knoppen "Opslaan" en "Annuleren".
5. **Datumbron bij opslaan.** Is de ingezonden datum gelijk aan de voorgevulde, dan blijft de bron uit `lees_vooraf` (`tekst` of `upload`). Is hij anders, dan `gebruiker`. Dat is wat `maak_document_uit_voorbereid(documentdatum=...)` uit 15a al doet; de route geeft `None` mee als de waarde ongewijzigd is.
6. **Opslaan.** `POST /upload/{token}`: validatie zoals het huidige formulier (titel verplicht, datum geldig → anders 400 met scherm 2 opnieuw, ingevulde waarden behouden), dan `maak_document_uit_voorbereid` in een thread, index herladen, openstaande upload verwijderen, 303 naar de documentpagina met melding "Opgeslagen". Dubbel indienen (twee tabs, dubbelklik) → het tweede verzoek vindt niets meer en krijgt de verlopen-melding; er ontstaat geen tweede document.
7. **Annuleren.** `POST /upload/{token}/annuleer` gooit de openstaande upload weg en gaat naar `GET /upload` met melding "Upload geannuleerd". Er is dan niets op schijf gekomen.
8. **Voortgang en wachten.** `app.js` blijft het formulier met `data-upload` (scherm 1) via XHR versturen: voortgangsbalk tijdens het uploaden, daarna "Bestanden ontvangen, tekst lezen…", en volgt `responseURL` naar scherm 2. Scherm 2 is een gewoon formulier zonder JS. Zonder JS werkt scherm 1 ook (gewone POST + redirect).
9. **Melding na opslaan.** De bestaande `?m=Opgeslagen`-melding op de documentpagina is de bevestiging; hij wordt iets prominenter (vinkje-icoon, blijft staan; geen toast, geen JS). Geen extra pagina.
10. **Inbox ongewijzigd.** De inbox heeft geen scherm 2 en gebruikt de suggesties direct (15a).
11. **Oude titel-eerst-flow verdwijnt.** `POST /upload` accepteert geen `titel`/`omschrijving`/`documentdatum`/`tags` meer; die velden worden genegeerd. Tests die in één stap uploadden worden herschreven met een helper die beide stappen doet.

## Routes (worden toegevoegd aan de tabel in `werk/00-contract.md`)

| Naam | Methode + pad |
|---|---|
| `upload` | `GET /upload` (scherm 1), `POST /upload` (bestanden → openstaande upload → 303 naar `upload_gegevens`) |
| `upload_gegevens` | `GET /upload/{token}` (scherm 2), `POST /upload/{token}` (opslaan) |
| `upload_annuleer` | `POST /upload/{token}/annuleer` |

`token` matcht `^[A-Za-z0-9_-]{8,64}$`; anders 404. De bestaande route `bestand` (`/doc/...`) en `beheer` botsen niet.

## Interfaces (worden toegevoegd aan `werk/00-contract.md`)

### `ordner/web/openstaand.py` (nieuw)
```python
@dataclass
class OpenstaandeUpload:
    token: str
    voorbereid: Voorbereid          # uit ingest.lees_vooraf: bestanden, teksten, datum, datumbron
    suggestie: Suggestie            # uit suggestie.stel_voor
    aangemaakt: datetime

class OpenstaandeUploads:
    def __init__(self, ttl: timedelta = timedelta(minutes=60), maximum: int = 10, nu: Callable[[], datetime] = datetime.now)
    def maak(self, voorbereid: Voorbereid, suggestie: Suggestie) -> OpenstaandeUpload   # gooit eerst verlopen/overtollige weg; nieuw token
    def haal(self, token: str) -> OpenstaandeUpload | None                              # None als onbekend of verlopen
    def verwijder(self, token: str) -> None                                             # idempotent
    def __len__(self) -> int
```
`app.state.openstaand = OpenstaandeUploads()` in `create_app`. Alleen geheugen; geen bestand, geen map, niets in `Settings`. Geen locking nodig: alle toegang gebeurt op de event loop (de thread doet alleen `lees_vooraf` en `maak_document_uit_voorbereid`, niet de store).

## Maakt / wijzigt

- `addon/ordner/web/openstaand.py` (nieuw), `tests/test_openstaand.py` (nieuw): maak/haal/verwijder, TTL via injecteerbare `nu`, maximum (oudste weg), onbekend token → None, tokens uniek.
- `addon/ordner/web/routes.py`: `upload_formulier` (scherm 1), `upload` (POST: bestanden verplicht, `lees_vooraf` + `stel_voor` in thread, openstaande upload, redirect), `upload_gegevens` (GET scherm 2 / POST opslaan), `upload_annuleer`. `_upload_context` verdwijnt of wordt de scherm-2-context. Bekende titels: `{e.meta.titel for e in index.alle()}`.
- `addon/ordner/web/app.py`: `app.state.openstaand`.
- Templates: `upload.html` wordt scherm 1; nieuw `upload_gegevens.html` (scherm 2) met bestandslijst, formulier, datumlabel, titelhint, knoppen Opslaan/Annuleren (annuleren als apart klein formulier, of één formulier met twee `formaction`s; kies wat zonder JS het eenvoudigst werkt). `base.html`/`style.css`: prominentere melding.
- `app.js`: alleen de tekst van de bezig-melding controleren; logica ongewijzigd (volgt `responseURL`).
- Tests `tests/test_web.py`: helper `_upload(client, bestanden, **velden)` die POST /upload doet, het token uit de `Location` haalt en POST /upload/{token} met velden doet; alle bestaande upload-tests erop overzetten. Nieuw: scherm 1 zonder bestanden → 400; scherm 2 toont voorgevulde titel/tags/datum uit gemockte tekst (`mock_cmd` met "Factuur … Eneco B.V. … Factuurdatum 12-03-2024"); datum ongewijzigd → `datumbron: tekst`, gewijzigd → `gebruiker`; onbekend token → 303 naar upload met melding; dubbel opslaan → één document; annuleren → geen documentmap; na scherm 1 is het archief ongewijzigd (`documentmappen()` gelijk, `_inbox/` leeg); titel leeg op scherm 2 → 400 met formulier; Ingress-prefix in de redirect naar scherm 2 en in de formulier-actions van scherm 2. `test_upload_zonder_bestanden` vervalt (gedrag bewust veranderd; noteren in `STATUS.md`).
- e2e `tests/e2e/test_browser.py`: `test_upload_via_formulier` in twee stappen (bestanden kiezen → "Verder" → titel controleren/aanpassen → "Opslaan"); de `TITEL`-constante wordt op scherm 2 ingevuld zodat de vervolgtests ongewijzigd blijven.
- Docs: `addon/DOCS.md` nieuwe sectie "Uploaden" (twee stappen, wat voorgevuld wordt, dat er niets bewaard wordt tot Opslaan en een openstaande upload bij herstart weg is), sectie "Documentdatum" (verwijst nu naar scherm 2), sectie "Titel en tags uit de tekst" uit 15a aanvullen; `README.md` als de uploadstap er beschreven staat; `addon/CHANGELOG.md` 0.9.0; `addon/config.yaml` version 0.9.0; `CLAUDE.md` (Web-regel: JS ook voor de tweestaps upload is niet nodig, het blijft upload-voortgang); `werk/00-contract.md` (routes, `openstaand.py`, Wijzigingen); `werk/STATUS.md`; `IDEAS.md` (het idee afvoeren of inkorten tot "gedaan in 15a/15b").

## Let op

- **Geheugen.** Een openstaande upload houdt de bestandsbytes vast (foto's van 5–10 MB). Met maximaal 10 is dat hooguit enkele honderden MB in een uitzonderlijk geval; normaal staat er één open. Als dat ooit knelt: `Voorbereid` naar een tempmap buiten het archief (`tempfile.mkdtemp`), zelfde interface.
- **Ingress.** Alle actions en de redirect naar scherm 2 via `url_for`/`_redirect`; `responseURL` in `app.js` komt van de browser en bevat de prefix vanzelf.
- **Gelijktijdigheid.** `lees_vooraf` en `maak_document_uit_voorbereid` draaien in `asyncio.to_thread`; de regel uit pakket 14 (queuen pas na de laatste schrijfactie) zit in `maak_document_uit_voorbereid`. `OpenstaandeUploads` wordt alleen op de event loop aangeraakt.
- **Slug-preview.** Scherm 2 toont geen mapnaam-preview; de titel en datum staan er al, en de slugregels staan in `DOCS.md`. Niet bouwen tenzij Bas erom vraagt.
- **Formuliervelden behouden bij 400.** Zoals de huidige `_upload_context`: ingevulde waarden terug in het formulier, met `fout`-melding.

## Bekende beperkingen / vervolg

- Suggesties komen uit `suggestie.py` (15a) en zijn zo goed als de woordenlijsten daar; missers verbeteren gebeurt in dat pakket, niet in de UI.
- Geen "onthoud mijn correctie" (bijv. tekst → titel-mapping): de archief-heuristiek uit 15a leert al van opgeslagen titels.
- Meerdere documenten in één upload (elk bestand een eigen document) is niet mogelijk; alles in scherm 1 wordt één document. Idee voor later, in `IDEAS.md`.
- Een openstaande upload is weg bij herstart of na 60 minuten; de gebruiker kiest de bestanden dan opnieuw. Bewuste keuze (beslissing 2): af of weg, niets wordt bewaard.
