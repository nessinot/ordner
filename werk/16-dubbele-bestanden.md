# Pakket 16 — Dubbele bestanden herkennen

> **Agent-prompt:** Lees `werk/00-contract.md` en dit bestand. Dit pakket is gebouwd en gecommit (release 0.10.0, 2026-09-05); gebruik dit bestand als naslag bij vervolgwerk aan dubbelherkenning. Afwijkingen bij het bouwen staan onderaan.

**Doel:** Voorkomen dat hetzelfde bestand per ongeluk twee keer in het archief komt omdat de gebruiker niet meer weet dat het er al staat. Elk bronbestand krijgt een SHA-256-vingerafdruk in `meta.md`; bij uploaden, bij bestanden toevoegen aan een document en in de inbox wordt die vergeleken met het hele archief. Een bekend bestand wordt geweigerd, met een link naar het document waar het al staat.

**Lees eerst:** `werk/00-contract.md` (`meta.py`, `storage.py`, `index.py`, `ingest.py`), `addon/ordner/web/routes.py` (`upload`, `document_bestanden`), `addon/ordner/web/templates/upload.html` en `document.html`, `addon/ordner/web/static/app.js` (scherm 1 toont een 4xx-antwoord via `document.write`).

## Beslissingen (afgestemd met Bas op 2026-09-05)

1. **De vingerafdruk staat op schijf, in `meta.md`.** Er is geen indexbestand; de index leeft in het geheugen en wordt bij elke start uit de mappen opgebouwd. Daarom nieuw veld `sha256:` in de frontmatter, een mapping bestandsnaam → hex-hash, in blokstijl (één regel per bestand, leesbaar zonder de app). Leeg → `sha256: {}`. Oude `meta.md`'s zonder veld blijven geldig (→ `{}`). Geen sidecar-bestand: `meta.md` is al de plek voor per-bestand-informatie.
2. **Het bestaande archief vult zichzelf.** De reconciler berekent bij elke ronde de hash voor bestanden in `bestanden` zonder hash en gooit hashes weg van bestanden die niet meer in `bestanden` staan. Na één ronde (bij start) is het hele archief gedekt; daarna hasht hij alleen wat ontbreekt, dus geen zware I/O op een groot archief. Een bestand dat buiten de app om onder dezelfde naam wordt vervangen krijgt geen nieuwe hash; bewuste beperking.
3. **In-memory opzoektabel.** `Index` houdt naast `docs` een dict hash → (rel, bestandsnaam) bij, gevuld in `herlaad` en opgeschoond in `verwijder`. Staan er (van vóór dit pakket) al twee gelijke bestanden in het archief, dan wint het laatst geladen document; geen melding.
4. **Controle vóór het lezen van de tekst.** `POST /upload` hasht de ontvangen bytes en zoekt in de index vóórdat `lees_vooraf` draait: hashen kost niets, OCR seconden. Bij een treffer komt er geen openstaande upload en niets op schijf.
5. **Weigeren, niet waarschuwen.** Een gelijke SHA-256 is zekerheid. Scherm 1 komt terug met status 409 en per dubbel bestand: bestandsnaam, "bestaat al in *Titel* (datum)" en een link naar dat document. Bij meerdere bestanden waarvan er minstens één al bestaat wordt de **hele** upload geweigerd en worden alle dubbelen genoemd; de gebruiker kiest de overige bestanden opnieuw. Nooit een half document zonder dat de gebruiker het merkt.
6. **Bestand toevoegen aan een bestaand document** (`POST /doc/{jaar}/{map}/bestanden`): dezelfde controle, dezelfde regel (één dubbel → niets toegevoegd, 409 met de documentpagina en de lijst met dubbelen boven het toevoegformulier). Een bestand dat al in ditzelfde document zit valt hier ook onder.
7. **Inbox.** Vóór `_ingest` wordt het inboxbestand gehasht. Bekend → verplaatsen naar `_inbox/_dubbel/` (bij naamconflict `<naam>_<JJJJMMDD-HHMMSS>`) met een waarschuwing in het log die het bestaande document noemt. De inbox kijkt alleen naar losse bestanden, dus `_dubbel/` wordt niet opnieuw opgepakt.
8. **Prullenbak telt niet mee.** `_prullenbak/` zit nooit in de index; een weggegooid document opnieuw uploaden mag. Weggooien was een bewuste keuze.
9. **Alleen byte-identieke dubbelen.** Dezelfde brief twee keer scannen levert andere bytes op en wordt niet herkend; net als een pdf waar het portaal een downloaddatum in stempelt. "Waarschijnlijk hetzelfde" op basis van datum, afzender en factuurnummer blijft een idee (`IDEAS.md`) en zou een waarschuwing zijn, geen weigering.
10. **`Archief.voeg_bestand_toe` weigert niets.** De storage-laag berekent en registreert alleen de hash; weigeren is beleid van de upload en de inbox (en tests maken graag documenten met identieke inhoud).

## Interfaces (worden toegevoegd aan `werk/00-contract.md`)

### `ordner/config.py`
```python
INBOX_DUBBEL_DIR = "_dubbel"        # submap van _inbox voor geweigerde dubbelen
```

### `ordner/meta.py`
```python
@dataclass
class Meta:
    ...
    sha256: dict[str, str] = field(default_factory=dict)   # bestandsnaam -> hex-hash; ontbreekt in oude meta.md -> {}
# render_meta: sleutel `sha256` direct na `bestanden`, blokstijl; parse: geen mapping -> MetaFout
```

### `ordner/dubbel.py` (nieuw)
```python
def sha256_van(data: bytes) -> str                 # hex, lowercase
def sha256_van_bestand(pad: Path) -> str           # in blokken van 1 MiB

@dataclass(frozen=True)
class Dubbel:
    naam: str            # naam van het aangeboden bestand
    rel: str             # document waar het al staat ("2026/2026-03-01_slug")
    bestand: str         # bestandsnaam daar
    titel: str
    documentdatum: date

def zoek_dubbelen(index: Index, bestanden: Iterable[tuple[str, bytes]]) -> list[Dubbel]
    # in aangeboden volgorde; één Dubbel per aangeboden bestand met een treffer
```

### `ordner/index.py`
```python
class Index:
    def zoek_hash(self, sha256: str) -> tuple[DocEntry, str] | None   # (document, bestandsnaam) of None

@dataclass
class ReconcileRapport:
    ...
    gehasht: int = 0        # bestanden waarvoor deze ronde een hash is berekend
```
`Reconciler.verwerk_inbox` verplaatst dubbelen naar `_inbox/_dubbel/` en telt ze niet mee in het resultaat.

### `ordner/storage.py`
`voeg_bestand_toe` zet `meta.sha256[naam]`; `maak_document` begint met `sha256={}`.

### Web
- `POST /upload`: 409 + `upload.html` met `dubbelen: list[Dubbel]` als er een treffer is; anders ongewijzigd.
- `POST /doc/{jaar}/{map}/bestanden`: 409 + `document.html` met `dubbelen` als er een treffer is; anders ongewijzigd.
- Template `_dubbelen.html` (include) rendert de lijst met links via `url_for('document', jaar=..., map=...)`.
- `beheer.html` toont `rapport.gehasht`.

## Maakt / wijzigt

- `addon/ordner/dubbel.py` (nieuw), `tests/test_dubbel.py` (nieuw).
- `addon/ordner/config.py`, `meta.py`, `storage.py`, `index.py`, `web/routes.py`, templates `upload.html`, `document.html`, `_dubbelen.html` (nieuw), `beheer.html`, `style.css`.
- Tests: `test_meta.py` (veldvolgorde, contractvoorbeeld, roundtrip, oude meta zonder veld, geen mapping → MetaFout), `test_storage.py` (hash geregistreerd), `test_index.py` (reconciler vult ontbrekende hash en verwijdert verweesde; `zoek_hash`; inbox-dubbel naar `_dubbel/`), `test_web.py` (upload 409 met link en zonder openstaande upload; deels dubbel → niets; toevoegen 409; prullenbak telt niet mee; twee bestaande tests krijgen andere bytes voor de tweede upload).
- Docs: `addon/DOCS.md` (veld `sha256`, sectie "Dubbele bestanden", inbox, beheerpagina), `addon/CHANGELOG.md` 0.10.0, `addon/config.yaml` 0.10.0, `CLAUDE.md`, `werk/00-contract.md`, `werk/STATUS.md`, `IDEAS.md`.

## Let op

- **Tests met identieke inhoud.** Veel tests maken bestanden met `b"x"`; daarom weigert de storage-laag niets (beslissing 10) en controleren alleen de routes en de inbox.
- **`app.js`** toont elk antwoord ≥ 400 van scherm 1 via `document.write`; 409 werkt daarmee zonder wijziging.
- **YAML.** Een hex-hash wordt door PyYAML als string gelezen; alleen een hash van 64 cijfers zou een int worden (kans verwaarloosbaar), `parse_meta` doet `str()`.

## Afwijkingen bij het bouwen

_(zie `werk/00-contract.md` › Wijzigingen en `werk/STATUS.md`)_
