# Pakket 17 — Inbox wacht op een titel

> **Agent-prompt:** Lees `werk/00-contract.md` en dit bestand. Dit pakket is gebouwd en gecommit (release 0.11.0, 2026-09-05); gebruik dit bestand als naslag bij vervolgwerk aan de inbox. Afwijkingen bij het bouwen staan onderaan en in `werk/00-contract.md` › Wijzigingen.

**Doel:** Een inboxbestand waarvoor de tekst geen afzender oplevert krijgt niet langer de bestandsnaam als titel, maar blijft in `_inbox/` wachten. De gebruiker geeft het via een nieuwe inboxpagina een titel in het bestaande scherm 2 van de upload. Zodra die titel in het archief staat herkent de reconciler de overige wachtende bestanden van dezelfde afzender en neemt ze automatisch op. Elk bestand wordt precies één keer door OCR gehaald: de gelezen tekst staat op schijf naast de inbox.

**Aanleiding:** Een oud Evernote-archief (losse pdf's en jpg's) in één keer via de inbox inladen. Tien documenten van dezelfde, nog onbekende afzender worden in dezelfde poll beoordeeld tegen een archief dat die afzender nog niet kent, dus tien keer de bestandsnaam als titel én als mapnaam (die nooit hernoemd wordt).

**Lees eerst:** `werk/00-contract.md` (`ingest.py`, `index.py` › `Reconciler`, `web/openstaand.py`), `werk/15b-tweestaps-upload.md`, `addon/ordner/index.py` (`verwerk_inbox`, `_is_dubbel`, `_ingest`), `addon/ordner/web/routes.py` (`upload`, `upload_gegevens`, `upload_opslaan`, `upload_annuleer`, `zoeken`, `beheer`), templates `upload_gegevens.html`, `zoeken.html`, `beheer.html`.

## Beslissingen (afgestemd met Bas op 2026-09-05)

1. **Geen titel → wachten, niet raden.** `stel_voor` geeft lege titel → het bestand blijft in `_inbox/` liggen en heet *wachtend*. De fallback op de bestandsnaam en `_FALLBACK_TITEL` in `index.py` vervallen. Dit is het enige gedrag; geen optie voor het oude gedrag. Dit geldt ook voor niet-extraheerbare bestanden (`.docx`, `.zip`, …) en voor bestanden waarvan de extractie mislukt: die wachten tot de gebruiker ze opneemt.
2. **Alleen de inbox.** Het uploadformulier verandert niet (scherm 2 toont al een leeg titelveld). Titels van documenten die al in het archief staan worden nooit met terugwerkende kracht aangepast; de reconciler raakt `titel` in een bestaand `meta.md` niet aan. Wachten en herkennen betreffen uitsluitend bestanden die nog in `_inbox/` liggen.
3. **Elk bestand één keer lezen.** De gelezen tekst van een inboxbestand staat in `_inbox/.tekst/<naam>.txt` (verborgen submap; de inbox kijkt alleen naar losse bestanden). Is de sidecar er en niet ouder dan het bestand (mtime), dan wordt hij gebruikt; anders wordt de tekst gelezen en de sidecar geschreven (atomic, zoals `schrijf_txt`). Mislukte extractie → lege sidecar, zodat er niet elke poll opnieuw ge-OCR'd wordt. Bij opname wordt de tekst de `.txt` naast het origineel (zoals `lees_vooraf` nu al doet) en gaat de sidecar weg; een lege sidecar → bestand naar de OCR-queue (zelfde pad als een mislukte upload-extractie). Sidecars zonder bestand worden bij elke poll opgeruimd. Na een herstart is dus niets kwijt en wordt niets opnieuw gelezen.
4. **Herbeoordelen alleen als er iets veranderd is.** De reconciler onthoudt per wachtend bestand tegen welke verzameling archieftitels het is beoordeeld (`frozenset` van de titels uit `index.alle()`). Gelijke verzameling → overslaan. Zo kost een inbox met honderden wachtende bestanden elke vijf seconden niets, en pakt de poll direct na het opslaan van "BSR" alle BSR-bestanden op. Datum en tags komen uit de tekst zoals nu (`vind_datum`, `stel_tags_voor`).
5. **Opnemen via scherm 2.** Nieuwe pagina `GET /inbox` toont de wachtende bestanden (naam, grootte, wacht sinds = mtime) met per bestand een knop **Opnemen**. `POST /inbox/opnemen` (veld `naam`) bouwt uit het bestand en de sidecar een `Voorbereid` plus `Suggestie` en zet een openstaande upload klaar met `inbox_naam` gevuld → redirect naar het bestaande scherm 2. Opslaan maakt het document zoals bij een upload en verwijdert daarna het inboxbestand en de sidecar. Annuleren laat het bestand liggen ("Teruggezet in de inbox"). Scherm 2 vermeldt de herkomst ("Uit de inbox: `<naam>`") en noemt de tweede knop dan **Terug naar inbox**.
6. **Reservering tegen de race met de poll.** Tussen Opnemen en Opslaan mag de inboxloop het bestand niet zelf opnemen (de gebruiker slaat net een titel op die het herkenbaar maakt). `Reconciler.reserveer(naam)` zet het bestand opzij; `verwerk_inbox` slaat gereserveerde bestanden volledig over. Vrijgeven bij opslaan, annuleren, of vanzelf na 60 minuten (zelfde TTL als de openstaande upload; beide leven alleen in het geheugen en verdwijnen bij herstart, wat precies klopt). Bij Opslaan controleert de route bovendien of het bestand nog bestaat en of zijn hash inmiddels in het archief zit (poll was net eerder): dan geen tweede document, maar een redirect naar het bestaande document met melding "Al opgenomen via de inbox".
7. **Zichtbaar op de startpagina.** Zonder zoekterm toont `zoeken.html` onder de kop een regel "*N* bestanden in de inbox wachten op een titel · **bekijk**" (alleen als N > 0). De beheerpagina krijgt een rij "Inbox wacht op titel" met link en het rapport een teller. De hoofdnavigatie verandert niet.
8. **Padveiligheid.** Een inboxnaam uit een formulier gaat altijd door `Archief.inbox_pad(naam)`: alleen een kale bestandsnaam (`Path(naam).name == naam`, niet beginnend met `.`), anders `OngeldigPad` → 404. De routes lezen nooit zelf uit `_inbox/`; alles loopt via `Reconciler`.
9. **Dubbelen blijven zoals in pakket 16.** De hashcontrole gebeurt vóór het lezen van de tekst; een bekend bestand gaat naar `_inbox/_dubbel/` en wordt nooit wachtend.

## Interfaces (worden toegevoegd aan `werk/00-contract.md`)

### `ordner/config.py`
```python
INBOX_TEKST_DIR = ".tekst"                      # submap van _inbox met de gelezen tekst per wachtend bestand
INBOX_RESERVERING = timedelta(minutes=60)       # zo lang blijft een via de webpagina opgenomen bestand buiten de poll
```

### `ordner/storage.py`
```python
class Archief:
    def inbox_pad(self, naam: str) -> Path      # _inbox/<naam>; OngeldigPad als naam geen kale bestandsnaam is of met "." begint
```

### `ordner/ingest.py`
```python
def voorbereid_uit_teksten(
    bestanden: list[tuple[str, bytes]], teksten: dict[int, str], *, vandaag: date | None = None
) -> Voorbereid
# datum: eerste treffer van vind_datum over de teksten in volgorde (bron "tekst"), anders vandaag ("upload").
# lees_vooraf gebruikt deze functie na het lezen; gedrag van lees_vooraf ongewijzigd.
```

### `ordner/index.py`
```python
@dataclass(frozen=True)
class Wachtend:
    naam: str
    grootte: int
    sinds: datetime          # mtime van het bestand

@dataclass
class ReconcileRapport:
    ...
    inbox_wachtend: int = 0  # aantal wachtende bestanden na deze ronde

class Reconciler:
    def wachtend(self) -> list[Wachtend]                                  # op naam gesorteerd; beoordeeld, zonder titel, niet gereserveerd
    def bereid_inbox_voor(self, naam: str) -> tuple[Voorbereid, Suggestie]  # bestand + sidecar (leest zo nodig); FileNotFoundError als weg
    def reserveer(self, naam: str) -> None
    def geef_vrij(self, naam: str) -> None
    def verwijder_uit_inbox(self, naam: str) -> None                      # bestand + sidecar; geeft ook vrij; missing_ok
```
`verwerk_inbox`: per stabiel bestand → gereserveerd? overslaan · dubbel? `_dubbel/` · tekst uit sidecar of lezen · titels ongewijzigd sinds vorige beoordeling? overslaan · `stel_voor` → titel: opnemen (`maak_document_uit_voorbereid`, sidecar weg, `index.herlaad`), geen titel: wachtend (één logregel bij de eerste keer). Daarna sidecars zonder bestand opruimen. Geeft nog steeds de aangemaakte documentmappen terug.

### `ordner/web/openstaand.py`
```python
@dataclass
class OpenstaandeUpload:
    ...
    inbox_naam: str | None = None   # gevuld als de upload uit de inbox komt

class OpenstaandeUploads:
    def maak(self, voorbereid, suggestie, inbox_naam: str | None = None) -> OpenstaandeUpload
```

### Web
- `GET /inbox` (name `inbox`) → `inbox.html`: lijst `wachtend: list[Wachtend]`, leeg → "De inbox is leeg." met uitleg waar `_inbox/` staat.
- `POST /inbox/opnemen` (name `inbox_opnemen`, veld `naam`): 404 bij ongeldige/onbekende naam; reserveert, `bereid_inbox_voor` in een thread, `openstaand.maak(..., inbox_naam=naam)`, redirect `upload_gegevens`.
- `POST /upload/{token}` met `inbox_naam`: bestand weg of hash bekend → `geef_vrij`, redirect naar het bestaande document ("Al opgenomen via de inbox") resp. naar `inbox` ("Bestand is niet meer in de inbox"); anders document aanmaken, `verwijder_uit_inbox`, redirect document ("Opgeslagen").
- `POST /upload/{token}/annuleer` met `inbox_naam`: `geef_vrij`, redirect `inbox` ("Teruggezet in de inbox").
- `upload_gegevens.html`: regel met herkomst en knoptekst afhankelijk van `inbox_naam`.
- `zoeken.html` (zonder `q`): regel met aantal en link naar `inbox` als `inbox_wachtend > 0`.
- `beheer.html`: rij "Inbox wacht op titel" (aantal + link).

## Maakt / wijzigt

- `addon/ordner/config.py`, `storage.py`, `ingest.py`, `index.py`, `web/openstaand.py`, `web/routes.py`, templates `inbox.html` (nieuw), `upload_gegevens.html`, `zoeken.html`, `beheer.html`, `style.css` (lijst en meldregel).
- Tests: `test_ingest.py` (`voorbereid_uit_teksten`), `test_storage.py` (`inbox_pad`), `test_index.py` (geen titel → wachtend en niets aangemaakt; sidecar geschreven en hergebruikt, `lees_tekst` één keer aangeroepen over meerdere polls; titel in archief erbij → volgende poll neemt op; gereserveerd → overgeslagen; verlopen reservering; mislukte extractie → lege sidecar, geen tweede poging; verweesde sidecar opgeruimd; niet-extraheerbaar → wachtend; `verwijder_uit_inbox`), `test_web.py` (inboxpagina toont wachtende; opnemen → scherm 2 met voorgevulde datum/tags en herkomst; opslaan → document, bestand en sidecar weg; annuleren → bestand blijft; bestand inmiddels weg → melding; hash inmiddels bekend → redirect naar bestaand document; startpagina toont teller; ongeldige naam → 404). Bestaande test op de bestandsnaam-fallback in `test_index.py` vervalt.
- e2e: controleer `tests/e2e` op inboxtests die op de bestandsnaam-fallback leunen; de containertest met echte OCR (bon-titel) blijft werken.
- Docs: `addon/DOCS.md` (sectie Inbox herschrijven: wachten, inboxpagina, `.tekst/`, startpagina; sectie "Titel en tags uit de tekst" laatste alinea), `addon/CHANGELOG.md` 0.11.0, `addon/config.yaml` 0.11.0, `CLAUDE.md` (rij Inbox), `werk/00-contract.md`, `werk/STATUS.md`, `IDEAS.md` (later: eerste tekstregels in de inboxlijst; meerdere wachtende bestanden in één keer dezelfde titel geven).

## Let op

- **Threads.** `verwerk_inbox` draait in een thread, de routes op de event loop. Reserveringen en de wachtlijst zijn gewone dicts/sets; reserveren gebeurt vóór `bereid_inbox_voor` zodat een lopende poll hooguit het bestand nét heeft opgenomen, wat Opslaan afvangt (beslissing 6). Sluit het venster aan de andere kant door in `upload_opslaan` het inboxbestand pas te verwijderen ná `index.herlaad` van het nieuwe document.
- **Sidecar-mtime op Windows en Samba.** Vergelijk `sidecar.stat().st_mtime >= bestand.stat().st_mtime`; een bestand dat via Samba wordt vervangen krijgt een nieuwere mtime en wordt dus opnieuw gelezen.
- **`.tekst/` is geen documentmap.** `Archief.documentmappen` kijkt alleen in jaarmappen; `_inbox` begint met `_` en zit nooit in de index. Wel: de reconciler mag `.tekst/` zelf aanmaken (`mkdir(exist_ok=True)`) bij de eerste sidecar.
- **Logging.** "wacht op een titel" één keer per bestand (bij de eerste beoordeling), niet elke poll; bij opname zoals nu met de titelbron.

## Afwijkingen bij het bouwen

Gebouwd op 2026-09-05 (release 0.11.0). Alle beslissingen hierboven zijn uitgevoerd; drie details wijken af van de interfacebeschrijving, alle drie om een concreet gat te dichten:

1. **Volgorde in `verwerk_inbox`.** Hierboven staat "gereserveerd → dubbel → tekst → titels ongewijzigd → overslaan". Gebouwd is "gereserveerd → grootte stabiel → *titels ongewijzigd → overslaan* → dubbel → tekst → `stel_voor`". De hashcontrole (`_is_dubbel`) leest het hele bestand; met honderden wachtende bestanden zou die elke vijf seconden draaien, precies wat beslissing 4 wil voorkomen. Gevolg: een bestand dat pas ná zijn beoordeling een dubbel wordt (de gebruiker uploadt hetzelfde bestand via het formulier) gaat bij de eerstvolgende *herbeoordeling* naar `_dubbel/`, niet bij de eerstvolgende poll. Bij een nieuwe titel in het archief of na vrijgave via de inboxpagina gebeurt dat vanzelf.
2. **`geef_vrij` laat herbeoordelen.** Vrijgeven (Terug naar inbox, "Al opgenomen via de inbox", "Bestand is niet meer in de inbox") wist ook de onthouden beoordeling, zodat de volgende poll het bestand opnieuw bekijkt. Zonder dat zou na "Al opgenomen via de inbox" het bestand eindeloos blijven wachten als de titel al in het archief bestond (verzameling titels ongewijzigd), terwijl de poll het nu als dubbel naar `_dubbel/` verplaatst. Kost: één hash en één sidecar-read per vrijgave.
3. **Inbox leest ter plekke.** De reconciler roept `lees_tekst(pad)` op het inboxbestand zelf aan, zonder tempkopie, en bouwt `Voorbereid` met `voorbereid_uit_teksten`; `lees_vooraf` wordt door `index.py` niet meer geïmporteerd. `lees_vooraf` zelf is intern herschreven op `voorbereid_uit_teksten` en gedraagt zich ongewijzigd (tests `test_ingest.py` groen).

Kleinere keuzes: niet-extraheerbare bestanden en mislukte extracties krijgen dezelfde lege sidecar (uniform: "sidecar aanwezig" = "beoordeeld", ook na herstart); de map `_inbox/.tekst/` blijft bestaan als hij leeg is; `Wachtend.sinds` heeft geen microseconden; de rij op de beheerpagina heeft `data-tel="inbox"` (nog niet live bijgewerkt door `app.js`); `Reconciler.lees_tekst=None` betekent nu "alles zonder titel wacht" (voorheen: bestandsnaam als titel), wat de oude unit-tests met de kale `reconciler`-fixture raakte. Tests: `test_inbox_zonder_treffer_houdt_bestandsnaam` en `test_inbox_docx_niet_gequeued` vervangen door `test_inbox_zonder_titel_wacht_en_leest_een_keer` en `test_inbox_niet_extraheerbaar_wacht_zonder_lezen`; e2e `test_inbox` doet de Opnemen-flow (zonder tesseract) en accepteert automatische opname (met tesseract, bon-titel); containertest ongewijzigd en niet gedraaid (geen Docker).

Ideeën die hieruit voortkwamen staan in `IDEAS.md` (eerste tekstregels op de inboxpagina, meerdere bestanden in één keer titelen, bekijken vanaf de inboxpagina).
