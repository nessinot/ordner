# Ordner — contract

Dit bestand is het bindende contract voor alle werkpakketten in `werk/`. **Elke agent leest dit bestand volledig vóór het eigen pakket.** Wijk niet af van de interfaces hieronder. Als iets ontbreekt of onmogelijk blijkt: kies de kleinste toevoeging, documenteer die in de commit-message én onderaan dit bestand onder "Wijzigingen op het contract".

## Wat Ordner is

Een minimale digitale archiefkast voor privédocumenten (WOZ, facturen, bonnen, digitale post) als lokale Home Assistant add-on via Ingress. Kernprincipe: **de bestanden op schijf zijn de waarheid**. Mappen, originelen, één leesbare `meta.md` per document en OCR-tekst als `.txt` ernaast. Alles blijft bruikbaar zonder de app (Verkenner, Samba, HA-backup). Geen database.

## Ontwerpbeslissingen

| Onderwerp | Keuze |
|---|---|
| Naam | `ordner` overal (add-on slug, Python-package, `/share/ordner`). |
| Mapnaam | `JJJJ/JJJJ-MM-DD_slug/` met de documentdatum zoals ingevuld bij aanmaak + slug van de titel. **Nooit hernoemen**; latere titel-/datumwijziging staat alleen in `meta.md`. Collision → `_2`, `_3`, … |
| Slug | lowercase, NFKD-normalisatie + combining characters strippen, alles buiten `[a-z0-9]` → `-`, herhaalde `-` samenvoegen, `-` aan de randen strippen, max 60 tekens, leeg → `document`. |
| Metadata | `meta.md`: YAML-frontmatter tussen `---`-regels + optionele body (vrije notities, wordt meegezocht). Geen OCR-tekst in `meta.md`. |
| OCR-tekst | Per bronbestand `<naam>.<ext>.txt` naast het origineel (`factuur.pdf` → `factuur.pdf.txt`). |
| `ocr`-status | `pending` (er zijn extraheerbare bestanden zonder `.txt`), `done` (alle extraheerbare bestanden hebben een `.txt`, of er zijn er geen), `failed` (extractie mislukt; reconciler probeert niet opnieuw tot "OCR opnieuw" de status reset). |
| Extraheerbaar | Extensies `.pdf .jpg .jpeg .png .heic` (case-insensitive). Andere bestanden worden opgeslagen en in `bestanden` opgenomen, maar niet geëxtraheerd. |
| Extractie pdf | `pdftotext -layout <pdf> -` → tekst. Paginatelling via `pdfinfo <pdf>` (regel `Pages: N`). Als `len(tekst.strip()) < 50 * N` → `ocrmypdf --force-ocr -l <talen> --sidecar <tmp.txt> <pdf> <tmp.pdf>` en de sidecar lezen; tmp-bestanden verwijderen. |
| Extractie afbeelding | `.heic` → tijdelijke `.jpg` via `pillow_heif` + Pillow; daarna `tesseract <img> - -l <talen>` → stdout. |
| Subprocess | Uitsluitend via `extract.run_cmd` (asyncio subprocess, timeout 600 s). Tests mocken alleen deze functie. |
| Index | In-memory (`index.Index`), gebouwd bij start, bijgewerkt door app/worker, herbouwd door reconciler. Geen indexbestand op schijf. |
| Reconciler | Bij start, elke `reconcile_interval` s, en op knop. Synchroniseert `bestanden` met de werkelijke bestanden, queued ontbrekende `.txt`, maakt `meta.md` voor mappen zonder, ingest `_inbox/`. |
| Inbox | `_inbox/` gepolld elke `inbox_interval` s (default 5); bestand met gelijke grootte in twee opeenvolgende polls wordt beoordeeld (pakket 17): gereserveerd → overslaan; beoordeeld tegen dezelfde verzameling archieftitels als vorige keer → overslaan; bekend (sha256) → `_inbox/_dubbel/`; tekst uit de sidecar `_inbox/.tekst/<naam>.txt` (als die bestaat en niet ouder is dan het bestand, anders lezen en schrijven; mislukt of niet-extraheerbaar → lege sidecar); `stel_voor` met titel → nieuw document (tags = tagsuggestie, datum uit de tekst anders vandaag; sidecar wordt de `.txt` naast het origineel), zonder titel → *wachtend* (blijft liggen; nooit de bestandsnaam als titel). Verweesde sidecars worden elke poll opgeruimd. Wachtende bestanden krijgen een titel via `GET /inbox` → `POST /inbox/opnemen` → scherm 2 van de upload; reservering `INBOX_RESERVERING` houdt de poll eraf. Zie `werk/17-inbox-wacht-op-titel.md`. |
| Datum uit tekst | Bij elke upload (scherm 1 heeft sinds 15b geen datumveld; de gebruiker corrigeert op scherm 2) en bij de inbox. De tekst wordt *vóór* het aanmaken van de map gelezen (`ingest.lees_vooraf`), zodat de map de gevonden datum krijgt en nooit hernoemd hoeft te worden. Sleutelwoorden in prioriteitsvolgorde: factuurdatum, notadatum, orderdatum, dagtekening, datum (optionele spatie, optionele `:`, hoofdletterongevoelig; "vervaldatum" e.d. matchen niet). Per sleutelwoord eerst alle regels met de datum direct achter het woord (max 60 spaties ertussen), daarna kolomlayout: label zonder datum op de eigen regel, datum op de eerstvolgende niet-lege regel waarvan het tekenbereik het dichtst bij dat van het label ligt (afstand hooguit 20 tekens, tabs geëxpandeerd). Notaties dd-mm-jjjj, dd/mm/jjjj, dd.mm.jjjj, jjjj-mm-dd, d maand jjjj (NL/EN maandnamen), tweecijferig jaar. Jaar tussen 1990 en volgend jaar. `meta.datumbron`: `gebruiker` (opgegeven of later handmatig gewijzigd; wordt nooit automatisch overschreven), `tekst`, `upload` (geen treffer → vandaag). Gelezen tekst wordt direct als `.txt` geschreven. |
| Titel en tags uit tekst | Alleen een suggestie (`suggestie.py`, pure functies); de inbox gebruikt hem direct (lege titel → wachten, 17), het uploadformulier toont hem voorgevuld op scherm 2 (15b). Titel = uitsluitend de afzender (bedrijf/instantie), nooit het documenttype of een jaartal; bij twijfel leeg. Heuristiek op prioriteit: (1) bekende archieftitel als heel woord in de tekst (langste wint, dan de vroegste treffer; titels < 3 tekens, `document` en documenttypewoorden overgeslagen), (2) naam achter "t.n.v."/"ten name van" (rest van de cel), (3) eerste kolomcel met rechtsvorm-achtervoegsel (`B.V.`, `BV`, `N.V.`, `NV`, `V.O.F.`, `VOF`, `U.A.`; hoofdlettergevoelig) → cel t/m achtervoegsel, instantie-voorvoegsel (Gemeente, Stichting, Vereniging, Waterschap, Provincie, Coöperatie, Ministerie; alleen met een woord erachter) → vanaf het woord, of los instantiewoord (Belastingdienst, Bank, Verzekeringen, Verzekeraar, Zorgverzekeraar, Ziekenhuis, Universiteit, Hogeschool) → hele cel, (4) bij < 25 niet-lege regels (bon) de eerste cel met ≥ 3 letters die geen documenttype-kopregel of datum(label) is, (5) anders leeg. Cellen = regel gesplitst op 2+ spaties (tabs geëxpandeerd). Opschonen: whitespace samengevoegd, leestekens aan de randen weg (punt van "B.V." blijft), max 60 tekens op woordgrens, hoofdletters zoals in de tekst. Tags = documenttypewoorden die een cel beginnen ("Factuur", "Factuur nr. 123"; niet "Factuurdatum"), lowercase, volgorde van voorkomen, zonder dubbelen; lijst `_DOCUMENTTYPEN` in `suggestie.py`. Meerdere bestanden: teksten aaneengeplakt in uploadvolgorde. Details: `werk/15a-titel-en-tagsuggestie.md`. |
| Zoeken | Alle woorden moeten voorkomen (AND over het hele document), hoofdletterongevoelig, over titel, omschrijving, tags, documentdatum (ISO-string), notities en alle `.txt`-teksten. Snippet ±80 tekens rond de eerste treffer + bron (veldnaam of bestandsnaam). Sortering documentdatum desc. `_inbox`/`_prullenbak` nooit in de index. |
| Prullenbak | `_prullenbak/<mapnaam>`; bij conflict `<mapnaam>_<JJJJMMDD-HHMMSS>`. |
| Schrijven | `meta.md` en `.txt` altijd via tempbestand in dezelfde map + `os.replace()`. |
| Web | FastAPI + Jinja2, geen JS-framework, geen build-stap. Vanilla JS alleen voor upload-voortgang en status-polling. Alle links/actions via `request.url_for` (Ingress `root_path`). |
| Tweestaps upload | Scherm 1 (`GET/POST /upload`) alleen bestanden (minstens één, anders 400). `POST /upload` leest de tekst (`lees_vooraf`, in een thread), bepaalt datum en suggestie (`stel_voor` met de titels uit de index) en zet een *openstaande upload* klaar in het geheugen (`web/openstaand.py`, `app.state.openstaand`, token `secrets.token_urlsafe(16)`, TTL 60 min, max 10, opruimen alleen bij aanmaken), dan 303 naar scherm 2 (`GET /upload/{token}`): bestandslijst en alle velden voorgevuld (titel = suggestie, datum = gevonden of vandaag, tags = suggestie, omschrijving leeg). `POST /upload/{token}` valideert (titel, datum; 400 met formulier), haalt de upload uit de store, maakt het document (`maak_document_uit_voorbereid`; datum gelijk aan de voorgevulde → bron uit `lees_vooraf`, anders `gebruiker`), 303 naar het document met `m=Opgeslagen`. `POST /upload/{token}/annuleer` gooit weg. Onbekend/verlopen token → 303 naar scherm 1 met melding; misvormd token (niet `^[A-Za-z0-9_-]{8,64}$`) → 404. Niets komt op schijf vóór Opslaan; een openstaande upload is weg bij herstart. Details: `werk/15b-tweestaps-upload.md`. |
| Dubbele bestanden | Elk bronbestand krijgt een SHA-256 in `meta.md` (`sha256:` mapping bestandsnaam → hex, blokstijl, sleutel direct na `bestanden`; oude `meta.md` zonder veld → `{}`). `Index` houdt een opzoektabel hash → (rel, bestandsnaam) bij. `POST /upload` en `POST /doc/…/bestanden` hashen de ontvangen bytes vóór het lezen van de tekst; bij minstens één bekend bestand wordt de hele actie geweigerd (409, pagina met per dubbel bestand een link naar het document; geen openstaande upload, niets op schijf). Inbox: bekend bestand → `_inbox/_dubbel/` (conflict → `<naam>_<JJJJMMDD-HHMMSS>`), waarschuwing in het log. Reconciler: verweesde hashes weg, ontbrekende berekenen (`rapport.gehasht`). `Archief.voeg_bestand_toe` registreert alleen. `_prullenbak` telt niet mee. Alleen byte-identiek. Details: `werk/16-dubbele-bestanden.md`. |
| Base image | HA Debian-base bookworm; apt: `python3 python3-venv ocrmypdf tesseract-ocr-nld tesseract-ocr-eng poppler-utils libheif1`. |
| Niet in v1 | Meerdere gebruikers, versiebeheer, autoclassificatie, tag-beheer, map-hernoemen, MCP-server, "alles opnieuw OCR'en", prullenbak legen/terugzetten. Ideeën → `IDEAS.md`. |

## Repo-structuur

```
ordner/                       # repo-root = add-on-repository (Add-on store › Repositories)
  repository.yaml
  README.md CLAUDE.md IDEAS.md
  pyproject.toml requirements-dev.txt .gitignore .gitattributes
  werk/                       # werkpakketten
  tests/ conftest.py test_*.py e2e/
  data/                       # lokale dev-archiefmap (gitignored)
  addon/                      # de add-on; dit is de Docker-build-context
    config.yaml build.yaml Dockerfile run.sh .dockerignore
    DOCS.md                   # tabblad "Documentatie" in de add-on
    CHANGELOG.md              # tabblad "Changelog" in de add-on; bovenste kop = version in config.yaml (test)
    requirements.txt
    ordner/                   # Python-package
      __init__.py config.py slug.py meta.py storage.py extract.py datum.py suggestie.py ingest.py dubbel.py index.py search.py worker.py
      web/ __init__.py app.py routes.py openstaand.py
        templates/ base.html zoeken.html upload.html upload_gegevens.html inbox.html document.html beheer.html bekijk.html _dubbelen.html
        static/ style.css app.js
```

## Datamodel op schijf

```
/share/ordner/
  _inbox/
    _dubbel/                  # inboxbestanden die al in het archief stonden (pakket 16)
    .tekst/                   # <naam>.txt: gelezen tekst van een inboxbestand dat op een titel wacht (pakket 17)
  _prullenbak/
  2026/
    2026-09-03_woz-beschikking/
      meta.md
      beschikking.pdf
      beschikking.pdf.txt
      foto.heic
      foto.heic.txt
```

`meta.md`:
```markdown
---
titel: WOZ-beschikking 2026
omschrijving: Gemeente, waarde peildatum 1-1-2025
documentdatum: 2026-03-01
uploaddatum: '2026-09-03T14:12'
tags: [woz, gemeente]
bestanden: [beschikking.pdf, foto.heic]
sha256:
  beschikking.pdf: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
  foto.heic: 2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae
ocr: done
datumbron: gebruiker
---
Eventuele eigen notities (worden meegezocht).
```

## Conventies

- Python ≥ 3.11, type hints overal, `from __future__ import annotations` bovenaan elke module.
- Nederlandse namen voor domeinbegrippen (`titel`, `bestanden`, `prullenbak`), Engelse namen voor techniek (`root_path`, `queue`).
- Geen globale state behalve `Settings`; alles wordt geïnjecteerd (`Archief(root)`, `Index`, …).
- Fouten: eigen excepties per module (`MetaFout`, `OngeldigPad`, `ExtractieFout`); nooit bare `except`.
- Logging via `logging.getLogger(__name__)`.
- Tests: pytest, `tmp_path`, geen netwerk, geen echte OCR-tools. Fixtures in `tests/conftest.py`. Elk pakket levert tests voor de eigen module; `pytest` moet groen zijn bij afronden.
- Testlagen: (1) **unit** — `tests/test_*.py`, gemockt, draait met kaal `pytest`; (2) **e2e** — `tests/e2e/test_browser.py`, marker `e2e`, Playwright tegen een lokale uvicorn; (3) **container** — `tests/e2e/test_container.py`, marker `container`, echt add-on-image met echte OCR via Docker, skipt als Docker ontbreekt. Lagen 2 en 3 komen in pakket 12 en zijn uitgesloten van het standaard `pytest`-commando.
- Commit per pakket met bericht `pakket NN: <titel>`; daarna afvinken in `werk/STATUS.md`.
- Windows-dev: paden altijd via `pathlib`; nooit `/` hardcoden in paden; `os.replace` voor atomic writes; tekstbestanden altijd expliciet `encoding="utf-8"`.
- Lokaal draaien: `ORDNER_DATA=./data uvicorn --app-dir addon ordner.web.app:app --reload` (in PowerShell: `$env:ORDNER_DATA="./data"; uvicorn ...`).

## Interfaces (bindend)

### `ordner/config.py`
```python
@dataclass(frozen=True)
class Settings:
    data_root: Path                 # ORDNER_DATA, default Path("./data").resolve()
    ocr_talen: str = "nld+eng"      # ORDNER_OCR_TALEN
    ocr_parallel: int = 2           # ORDNER_OCR_PARALLEL
    reconcile_interval: int = 300   # ORDNER_RECONCILE_INTERVAL (seconden)
    inbox_interval: int = 5         # ORDNER_INBOX_INTERVAL (seconden)

    @classmethod
    def from_env(cls) -> "Settings": ...

INBOX_DIR = "_inbox"
INBOX_DUBBEL_DIR = "_dubbel"        # submap van _inbox voor geweigerde dubbelen (pakket 16)
INBOX_TEKST_DIR = ".tekst"          # submap van _inbox met de gelezen tekst per wachtend bestand (pakket 17)
INBOX_RESERVERING = timedelta(minutes=60)   # zo lang blijft een via de inboxpagina opgenomen bestand buiten de poll (pakket 17)
TRASH_DIR = "_prullenbak"
META_NAAM = "meta.md"
EXTRAHEERBAAR = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}
```

### `ordner/slug.py`
```python
def maak_slug(titel: str) -> str
```

### `ordner/meta.py`
```python
OcrStatus = Literal["pending", "done", "failed"]
DatumBron = Literal["gebruiker", "tekst", "upload"]   # pakket 14

class MetaFout(Exception): ...

@dataclass
class Meta:
    titel: str
    documentdatum: date
    uploaddatum: datetime            # minuut-precisie, naïef (lokale tijd)
    omschrijving: str = ""
    tags: list[str] = field(default_factory=list)
    bestanden: list[str] = field(default_factory=list)
    ocr: OcrStatus = "done"
    notities: str = ""               # body onder de frontmatter
    datumbron: DatumBron = "gebruiker"   # ontbreekt in oude meta.md → "gebruiker"; onbekende waarde → "gebruiker" + warning
    sha256: dict[str, str] = field(default_factory=dict)   # pakket 16: bestandsnaam → hex-hash; ontbreekt → {}; geen mapping → MetaFout

def parse_meta(tekst: str) -> Meta          # raises MetaFout bij ontbrekende frontmatter/titel/datum
def render_meta(meta: Meta) -> str          # frontmatter (keys: titel, omschrijving, documentdatum, uploaddatum, tags, bestanden, sha256, ocr, datumbron; tags/bestanden als flow-lijst [a, b], sha256 in blokstijl, leeg → {}) + notities
def lees_meta(map: Path) -> Meta            # leest map/meta.md
def schrijf_meta(map: Path, meta: Meta) -> None   # atomic
def bepaal_ocr_status(map: Path, meta: Meta) -> OcrStatus
    # "failed" blijft "failed"; anders "pending" als een extraheerbaar bestand uit meta.bestanden geen .txt heeft, anders "done"
def txt_pad(bestand: Path) -> Path          # bestand.with_name(bestand.name + ".txt")
def schrijf_txt(bestand: Path, tekst: str) -> None   # atomic naar txt_pad(bestand); gebruikt door worker en ingest
def is_extraheerbaar(naam: str) -> bool
```

### `ordner/storage.py`
```python
class OngeldigPad(Exception): ...

class Archief:
    def __init__(self, root: Path)          # maakt root, _inbox en _prullenbak aan als ze ontbreken
    root: Path
    inbox_dir: Path
    trash_dir: Path

    def maak_document(self, titel: str, documentdatum: date, omschrijving: str = "",
                      tags: list[str] | None = None, nu: datetime | None = None,
                      datumbron: DatumBron = "gebruiker") -> Path
        # map JJJJ/JJJJ-MM-DD_slug[_N]; schrijft meta.md (bestanden=[], ocr="done"); geeft absolute map terug
        # web en inbox roepen dit niet direct aan maar via ingest.maak_document_uit_bestanden

    def voeg_bestand_toe(self, doc: Path, naam: str, data: bytes) -> str
        # naam saneren; conflict → stam_2.ext; schrijft bestand atomic;
        # update meta.bestanden, meta.sha256[naam] (pakket 16) + ocr via bepaal_ocr_status; geeft de opgeslagen naam terug
        # weigert nooit een dubbel bestand; dat is beleid van upload en inbox

    def naar_prullenbak(self, doc: Path) -> Path
    def documentmappen(self) -> list[Path]  # alle root/JJJJ/*/ met meta.md, gesorteerd; "_"- en "."-mappen overslaan
    def relatief(self, doc: Path) -> str    # "2026/2026-09-03_slug" (altijd met "/")
    def veilig_pad(self, jaar: str, map: str, naam: str | None = None) -> Path
        # raises OngeldigPad als een component "..", een pad-scheider of niets bevat,
        # als het resultaat buiten root ligt, of als het niet bestaat
    def inbox_pad(self, naam: str) -> Path   # pakket 17: _inbox/<naam>; OngeldigPad als naam geen kale bestandsnaam is
        # (leeg, ".", "..", pad-scheider) of met "." begint; het bestand hoeft niet te bestaan
```

### `ordner/extract.py`
```python
class ExtractieFout(Exception): ...

async def run_cmd(args: list[str], timeout: float = 600) -> tuple[int, bytes, bytes]
    # ENIGE subprocess-ingang. FileNotFoundError/timeout → ExtractieFout met leesbare melding.
async def extract_pdf(pad: Path, talen: str) -> str
async def extract_afbeelding(pad: Path, talen: str) -> str
async def extract_bestand(pad: Path, talen: str) -> str     # dispatch op extensie; niet-extraheerbaar → ExtractieFout
```

### `ordner/dubbel.py` (pakket 16)
```python
def sha256_van(data: bytes) -> str                 # hex, lowercase
def sha256_van_bestand(pad: Path) -> str           # in blokken van 1 MiB

@dataclass(frozen=True)
class Dubbel:
    naam: str            # naam van het aangeboden bestand
    rel: str             # document waar het al staat ("2026/2026-03-01_slug"); properties jaar / map
    bestand: str         # bestandsnaam daar
    titel: str
    documentdatum: date

def zoek_dubbelen(index: Index, bestanden: Iterable[tuple[str, bytes]]) -> list[Dubbel]
    # in aangeboden volgorde; één Dubbel per aangeboden bestand met een treffer in index.zoek_hash
```

### `ordner/index.py`
```python
@dataclass
class DocEntry:
    rel: str
    map: Path
    meta: Meta
    teksten: dict[str, str]         # bestandsnaam → inhoud van de .txt; alleen voor bestanden mét .txt

class Index:
    docs: dict[str, DocEntry]
    def herlaad(self, archief: Archief, map: Path) -> DocEntry   # leest meta.md + .txt's opnieuw; werkt de hash-tabel bij
    def verwijder(self, rel: str) -> None
    def alle(self) -> list[DocEntry]        # documentdatum desc, daarna rel desc
    def tellingen(self) -> dict[str, int]   # {"totaal", "pending", "done", "failed"}
    def zoek_hash(self, sha256: str) -> tuple[DocEntry, str] | None   # pakket 16: (document, bestandsnaam) of None; bij gelijke bestanden in twee documenten wint de laatst geladen

def bouw_index(archief: Archief) -> Index

@dataclass
class ReconcileRapport:
    documenten: int
    gesynchroniseerd: int
    gequeued: int
    meta_aangemaakt: int
    inbox_verwerkt: int
    gehasht: int                    # pakket 16: bestanden waarvoor deze ronde een sha256 is berekend
    inbox_wachtend: int             # pakket 17: aantal wachtende inboxbestanden na deze ronde

@dataclass(frozen=True)
class Wachtend:                     # pakket 17
    naam: str
    grootte: int
    sinds: datetime                 # mtime van het bestand, zonder microseconden

class Reconciler:
    def __init__(self, archief: Archief, index: Index, queue_fn: Callable[[Path, str], None],
                 lees_tekst: LeesTekst | None = None)   # lees_tekst: voor de inbox (datum, titel en tags uit tekst); None = niets lezen (alles zonder titel wacht)
    def run(self) -> ReconcileRapport       # synchroon; de app roept aan via asyncio.to_thread. _sync_map (16): verweesde hashes weg, ontbrekende berekenen
    def verwerk_inbox(self) -> list[Path]   # houdt self._inbox_groottes bij voor de stabiliteitscheck; per stabiel bestand (17):
        # gereserveerd → overslaan · beoordeeld tegen dezelfde titels → overslaan · dubbel → _dubbel/ · tekst uit sidecar of lees_tekst(pad)
        # · stel_voor(tekst, titels): titel → maak_document_uit_voorbereid (voorbereid_uit_teksten), bestand + sidecar weg, index.herlaad;
        # geen titel → wachtend (één logregel). Daarna verweesde sidecars weg. Geeft de aangemaakte documentmappen terug.
    # pakket 17, voor de inboxpagina (alle toegang tot _inbox/ vanuit de routes loopt hierlangs):
    def wachtend(self) -> list[Wachtend]                                    # beoordeeld, zonder titel, niet gereserveerd, bestaat nog; op naam
    def bereid_inbox_voor(self, naam: str) -> tuple[Voorbereid, Suggestie]  # bestand + sidecar (leest zo nodig); FileNotFoundError als weg; OngeldigPad via inbox_pad
    def reserveer(self, naam: str) -> None                                  # buiten de poll tot geef_vrij/verwijder_uit_inbox of na INBOX_RESERVERING
    def geef_vrij(self, naam: str) -> None                                  # ook: het bestand wordt bij de volgende poll opnieuw beoordeeld
    def verwijder_uit_inbox(self, naam: str) -> None                        # bestand + sidecar (missing_ok), reservering en geheugenstaat weg
```

### `ordner/datum.py` (pakket 14)
```python
MIN_JAAR = 1990

@dataclass(frozen=True)
class DatumTreffer:
    datum: date
    sleutelwoord: str               # "factuurdatum" | "notadatum" | "orderdatum" | "dagtekening" | "datum"
    regel: str                      # de regel waarin de datum stond (bij kolomlayout: de waarderegel), voor logging

def vind_datum(tekst: str, vandaag: date | None = None) -> DatumTreffer | None
    # per sleutelwoord in prioriteitsvolgorde: eerst regeltreffers over alle regels, dan kolomtreffers; eerste geldige datum wint. Pure functie.
```

### `ordner/suggestie.py` (pakket 15a)
```python
TitelBron = Literal["archief", "tnv", "rechtsvorm", "eerste-regel", "geen"]

@dataclass(frozen=True)
class Suggestie:
    titel: str                  # "" als er geen betrouwbare naam is
    titelbron: TitelBron        # voor logging en tests
    tags: list[str]             # documenttype(n), lowercase, in volgorde van voorkomen

def stel_voor(tekst: str, bekende_titels: Iterable[str] = ()) -> Suggestie
    # pure functie; combineert stel_titel_voor en stel_tags_voor. Importeert alleen re, dataclasses, typing.
def stel_titel_voor(tekst: str, bekende_titels: Iterable[str] = ()) -> tuple[str, TitelBron]
def stel_tags_voor(tekst: str) -> list[str]
def cellen(regel: str) -> list[str]     # splitst op 2+ spaties, tabs geëxpandeerd; ook bruikbaar voor datum.py later
```

### `ordner/ingest.py` (pakket 14, twee fasen sinds 15a)
```python
LeesTekst = Callable[[Path], str | None]     # synchroon; None als extractie mislukt
QueueFn = Callable[[Path, str], None]

def maak_tekstlezer(talen: str) -> LeesTekst
    # wrapper om extract.extract_bestand met asyncio.run; ExtractieFout → None + warning. Draaien in een thread.

@dataclass
class Voorbereid:
    bestanden: list[tuple[str, bytes]]
    teksten: dict[int, str]            # index in bestanden -> gelezen tekst
    documentdatum: date
    datumbron: DatumBron               # "gebruiker" | "tekst" | "upload"

    @property
    def tekst(self) -> str             # alle gelezen teksten in volgorde, gescheiden door een lege regel

def lees_vooraf(bestanden: list[tuple[str, bytes]], *, documentdatum: date | None,
                lees_tekst: LeesTekst | None, vandaag: date | None = None) -> Voorbereid
    # Fase 1, schrijft niets in het archief. documentdatum gegeven → niets lezen, bron "gebruiker".
    # None → extraheerbare bestanden lezen via lees_tekst (tempbestand met originele extensie);
    #   daarna voorbereid_uit_teksten.

def voorbereid_uit_teksten(bestanden: list[tuple[str, bytes]], teksten: dict[int, str], *,
                           vandaag: date | None = None) -> Voorbereid
    # pakket 17: Voorbereid uit al gelezen teksten (inbox-sidecar). Datum = eerste treffer van vind_datum
    # over de teksten in volgorde van `bestanden` ("tekst"), anders vandaag ("upload").

def maak_document_uit_voorbereid(archief: Archief, titel: str, vb: Voorbereid, *, omschrijving: str = "",
                                 tags: list[str] | None = None, queue_fn: QueueFn,
                                 documentdatum: date | None = None) -> Path
    # Fase 2. documentdatum None → vb.documentdatum en vb.datumbron; anders die datum met bron "gebruiker"
    # (15b: de gebruiker wijzigde het voorgevulde veld). Map aanmaken, bestanden en gelezen .txt's schrijven,
    # ocr-status bepalen; wat niet gelezen is gaat pas daarna naar queue_fn (laatste stap, zie pakket 14).

def maak_document_uit_bestanden(archief: Archief, titel: str, bestanden: list[tuple[str, bytes]], *,
                                documentdatum: date | None, omschrijving: str = "", tags: list[str] | None = None,
                                lees_tekst: LeesTekst | None, queue_fn: QueueFn, vandaag: date | None = None) -> Path
    # = lees_vooraf + maak_document_uit_voorbereid; ongewijzigde signatuur. Sinds 15b door niets in de app
    # aangeroepen (upload en inbox gebruiken de twee fasen apart); blijft bestaan voor tests en scripts.
```

### `ordner/web/openstaand.py` (pakket 15b)
```python
@dataclass
class OpenstaandeUpload:
    token: str
    voorbereid: Voorbereid          # uit ingest.lees_vooraf: bestanden, teksten, datum, datumbron
    suggestie: Suggestie            # uit suggestie.stel_voor
    aangemaakt: datetime
    inbox_naam: str | None = None   # pakket 17: gevuld als de upload uit de inbox komt; het bestand blijft daar tot Opslaan

class OpenstaandeUploads:
    def __init__(self, ttl: timedelta = timedelta(minutes=60), maximum: int = 10, nu: Callable[[], datetime] = datetime.now)
    def maak(self, voorbereid: Voorbereid, suggestie: Suggestie, inbox_naam: str | None = None) -> OpenstaandeUpload
        # gooit eerst verlopen/overtollige (oudste eerst) weg; nieuw token
    def haal(self, token: str) -> OpenstaandeUpload | None                              # None als onbekend of verlopen (verlopen wordt daarbij verwijderd)
    def verwijder(self, token: str) -> None                                             # idempotent
    def __len__(self) -> int
```
`app.state.openstaand = OpenstaandeUploads()` in `create_app`. Alleen geheugen; geen bestand, geen map, niets in `Settings`. Geen locking: alle toegang gebeurt op de event loop (de thread doet alleen `lees_vooraf`/`stel_voor` en `maak_document_uit_voorbereid`, niet de store).

### `ordner/search.py`
```python
@dataclass
class Treffer:
    rel: str
    titel: str
    omschrijving: str
    documentdatum: date
    snippet: str
    bron: str                       # veldnaam ("titel", "omschrijving", "tags", "documentdatum", "notities") of bestandsnaam

def zoek(index: Index, query: str) -> list[Treffer]  # alle treffers; de route kapt af op 50 (tenzij ?alles=1)
```

### `ordner/worker.py`
```python
class OcrQueue:
    def __init__(self, archief: Archief, index: Index, settings: Settings)
    def enqueue(self, doc: Path, naam: str) -> None    # idempotent; veilig aan te roepen vanuit asyncio.to_thread
    async def start(self) -> None
    async def stop(self) -> None
    @property
    def lengte(self) -> int
    bezig: set[tuple[str, str]]     # (rel, naam) die nu geëxtraheerd worden

async def reconcile_lus(reconciler: Reconciler, queue: OcrQueue, settings: Settings, stop: asyncio.Event) -> None
async def inbox_lus(reconciler: Reconciler, queue: OcrQueue, settings: Settings, stop: asyncio.Event) -> None
```

### `ordner/web/app.py`
```python
def create_app(settings: Settings | None = None) -> FastAPI
    # app.state.settings / archief / index / queue / reconciler / lees_tekst / openstaand (15b)
    # lifespan: bouw_index, queue.start, lussen starten; bij afsluiten stop-event zetten en queue.stop
    # Ingress-middleware; static mount op /static

app = create_app()
```

### Routenamen (voor `url_for`)

| Naam | Methode + pad |
|---|---|
| `zoeken` | `GET /` |
| `upload` | `GET /upload` (scherm 1: bestanden), `POST /upload` (bestanden → openstaande upload → 303 naar `upload_gegevens`; 409 + scherm 1 met `dubbelen` bij een bekend bestand, pakket 16) |
| `upload_gegevens` | `GET /upload/{token}` (scherm 2: gegevens voorgevuld), `POST /upload/{token}` (opslaan; met `inbox_naam` (17): hash al bekend → 303 naar dat document `m=Al opgenomen via de inbox`, bestand weg → 303 `inbox` `m=Bestand is niet meer in de inbox`, anders document aanmaken en `verwijder_uit_inbox`) |
| `upload_annuleer` | `POST /upload/{token}/annuleer` (met `inbox_naam`: `geef_vrij`, 303 `inbox` `m=Teruggezet in de inbox`) |
| `inbox` | `GET /inbox` (pakket 17: wachtende bestanden met knop Opnemen; leeg → "De inbox is leeg.") |
| `inbox_opnemen` | `POST /inbox/opnemen` (veld `naam`; 404 bij ongeldige of onbekende naam; reserveert, `bereid_inbox_voor` in een thread, openstaande upload met `inbox_naam`, 303 naar `upload_gegevens`) |
| `document` | `GET /doc/{jaar}/{map}` |
| `document_meta` | `POST /doc/{jaar}/{map}/meta` |
| `document_bestanden` | `POST /doc/{jaar}/{map}/bestanden` (409 + documentpagina met `dubbelen` bij een bekend bestand, pakket 16) |
| `document_ocr` | `POST /doc/{jaar}/{map}/ocr` |
| `document_verwijder` | `POST /doc/{jaar}/{map}/verwijder` |
| `bestand` | `GET /doc/{jaar}/{map}/bestand/{naam}` |
| `beheer` | `GET /beheer` |
| `beheer_reconcile` | `POST /beheer/reconcile` |
| `status` | `GET /api/status` |
| `static` | `/static/...` |

## Testfixtures (`tests/conftest.py`)

```python
@pytest.fixture
def mock_cmd(monkeypatch) -> CmdMock         # pakket 01: vervangt ordner.extract.run_cmd
    # mock_cmd.register("pdftotext", rc=0, stdout=b"...")
    # mock_cmd.register("ocrmypdf", handler=fn)   # fn(args: list[str]) -> (rc, stdout, stderr); mag zelf bestanden schrijven
    # mock_cmd.calls: list[list[str]]             # alle aanroepen, in volgorde
    # ongeregistreerd commando → fout (vanaf pakket 04: extract.ExtractieFout)

@pytest.fixture
def archief(tmp_path) -> Archief             # pakket 03: Archief(tmp_path / "archief")

@pytest.fixture
def client(tmp_path, mock_cmd) -> TestClient # pakket 08: create_app(Settings(data_root=tmp_path / "archief"))
```

## Wijzigingen op het contract

_(agents voegen hier regels toe: pakket · wat · waarom)_

- 08 · Templates gebruiken de Jinja-global `url_for(naam, **params)` (in `web/app.py`, wrapper om `request.url_for(...).path`) in plaats van `request.url_for` direct; redirects via `routes._redirect` · `request.url_for` levert een absolute URL met scheme+host uit de ASGI-scope; achter Ingress/https zou dat `http://…`-links geven (mixed content) en de ingress-test uit pakket 08 verwacht paden die met `/api/hassio_ingress/...` beginnen. De global geeft het pad inclusief `root_path` terug.
- 08 · `POST /upload` gebruikt `titel: str = Form("")` i.p.v. `Form(...)` · een ontbrekende titel moet 400 met het formulier opleveren, niet FastAPI's 422.
- 08 · `app.state.templates` toegevoegd · routes in `routes.py` hebben de `Jinja2Templates`-instantie nodig zonder globale state.
- 14 · `Meta.datumbron` toegevoegd (laatste frontmatter-sleutel), `meta.schrijf_txt`, `Archief.maak_document(datumbron=)`, `Reconciler(lees_tekst=)`, nieuwe modules `datum.py` en `ingest.py`; het uploadformulier heeft geen voorgevulde datum meer · documenten zonder opgegeven datum krijgen de datum uit de tekst (factuurdatum enz.), en omdat de map nooit hernoemd wordt moet die datum vóór het aanmaken bekend zijn. Zie `werk/14-datum-uit-tekst.md`.
- 0.6.0 · `vind_datum` herkent ook kolomlayout (label boven waarde); interface ongewijzigd · facturen zetten factuurdatum, factuurnummer en vervaldatum vaak in een tabel, en `pdftotext -layout` bewaart de kolomposities. Zie `werk/14-datum-uit-tekst.md`.
- 15c · `routes.Kaart` krijgt een veld `tags: list[str]` (default lege lijst), gevuld uit `DocEntry.meta.tags` in beide takken van de route `zoeken`; `search.Treffer` ongewijzigd · tags worden klikbare labels in de resultatenlijst en op de documentpagina (link naar `url_for('zoeken')?q=<tag>`); de route heeft de `DocEntry` al bij de hand, dus de zoeklaag hoeft niets te weten van tags-als-labels. Zie `werk/15c-tags-als-labels.md`.
- 13 · Add-on-bestanden en het Python-package verhuisd naar `addon/`; `repository.yaml` in de root; `pythonpath = ["addon", "."]` in `pyproject.toml` · de Supervisor accepteert een git-URL alleen als add-on-repository (elke add-on in een eigen submap met `config.yaml`), zodat installeren en updaten via de Add-on store kan i.p.v. kopiëren naar `/addons/` via Samba.
- 15a · Nieuwe module `suggestie.py` (`Suggestie`, `stel_voor`, `stel_titel_voor`, `stel_tags_voor`, `cellen`); `ingest.py` gesplitst in `Voorbereid`, `lees_vooraf` en `maak_document_uit_voorbereid`, met `maak_document_uit_bestanden` als ongewijzigde wrapper; `Reconciler._ingest` gebruikt de suggestie voor titel en tags van inboxdocumenten · de titel is pas na het lezen bekend en 15b zet tussen lezen en aanmaken een tweede scherm. Twee kleine aanscherpingen t.o.v. `werk/15a-titel-en-tagsuggestie.md`, beide omdat een verkeerde naam erger is dan geen naam: rechtsvorm-achtervoegsels matchen hoofdlettergevoelig ("b.v." in lopende tekst is "bijvoorbeeld") en een instantie-voorvoegsel telt alleen met minstens één woord erachter ("Gemeente" alleen is geen naam). De bestaande test `test_inbox_met_tekstlezer_haalt_datum_uit_tekst` kreeg een tekst zonder bruikbare naamregel, omdat de korte testtekst anders terecht een bon-titel opleverde.
- 15b · Nieuwe module `web/openstaand.py` (`OpenstaandeUpload`, `OpenstaandeUploads`), `app.state.openstaand`, routes `upload_gegevens` (`GET/POST /upload/{token}`) en `upload_annuleer`; `POST /upload` accepteert alleen nog bestanden (minstens één) en negeert titel/datum/tags; nieuwe template `upload_gegevens.html`; `maak_document_uit_bestanden` wordt door de app niet meer aangeroepen · uploaden in twee schermen zodat titel, datum en tags uit de tekst voorgevuld zijn vóór het opslaan. Eén afwijking buiten het pakketbestand: `extract._heic_naar_jpg` vertaalt PIL-fouten (`OSError`/`ValueError`, o.a. `UnidentifiedImageError`) naar `ExtractieFout`; interface ongewijzigd. Nodig omdat scherm 1 nu altijd de tekst leest en `maak_tekstlezer` alleen `ExtractieFout` opvangt: een kapotte `.heic` gaf anders een 500 (de worker ving dit al breed op, de inbox en de datumloze upload uit 14 niet). Zie `werk/15b-tweestaps-upload.md`.
- 17 · `INBOX_TEKST_DIR`, `INBOX_RESERVERING`, `Archief.inbox_pad`, `ingest.voorbereid_uit_teksten` (door `lees_vooraf` hergebruikt), `Wachtend`, `ReconcileRapport.inbox_wachtend`, `Reconciler.wachtend/bereid_inbox_voor/reserveer/geef_vrij/verwijder_uit_inbox`, `OpenstaandeUpload.inbox_naam`, routes `inbox` en `inbox_opnemen`, template `inbox.html`; de bestandsnaam-fallback voor inboxtitels vervalt · een inboxbestand zonder herkende afzender wacht op een titel van de gebruiker in plaats van een mapnaam te krijgen die nooit meer verandert. Drie kleine afwijkingen van `werk/17-inbox-wacht-op-titel.md`: (1) de volgorde in `verwerk_inbox` is gereserveerd → grootte → *titels ongewijzigd → overslaan* → dubbel → tekst, dus de hashcontrole staat ná de goedkope overslaan-check (anders wordt elke wachtende file elke vijf seconden gehasht); een bestand dat pas ná zijn beoordeling een dubbel wordt gaat daardoor bij de eerstvolgende herbeoordeling naar `_dubbel/`; (2) `geef_vrij` laat het bestand bij de volgende poll opnieuw beoordelen, zodat na "Al opgenomen via de inbox" de poll het als dubbel opruimt in plaats van eindeloos te blijven wachten; (3) de inbox leest het bestand ter plekke (`lees_tekst(pad)`), zonder tempkopie, en gebruikt `lees_vooraf` niet meer. Ook niet-extraheerbare bestanden krijgen een (lege) sidecar, en `.tekst/` blijft staan als hij leeg is. Zie `werk/17-inbox-wacht-op-titel.md`.
- 16 · `Meta.sha256` (mapping, sleutel direct na `bestanden`, blokstijl), nieuwe module `dubbel.py` (`sha256_van`, `sha256_van_bestand`, `Dubbel`, `zoek_dubbelen`), `Index.zoek_hash` met interne hash-tabel, `ReconcileRapport.gehasht`, `INBOX_DUBBEL_DIR`, `Archief.voeg_bestand_toe` registreert de hash; `POST /upload` en `POST /doc/…/bestanden` antwoorden 409 met de lijst `dubbelen` (template `_dubbelen.html`) · hetzelfde bestand mag niet per ongeluk twee keer in het archief komen; de vingerafdruk staat op schijf omdat er geen indexbestand is. De sleutel staat niet als laatste (zoals `datumbron` in 14) maar bij `bestanden`, omdat het per-bestand-informatie is. Tests die twee keer hetzelfde bestand uploadden (`test_bekende_titel_uit_archief_voorgesteld`, `test_ingress_prefix_in_redirect`, `test_inbox_fout_blokkeert_rest_niet`) kregen andere bytes voor het tweede bestand. Zie `werk/16-dubbele-bestanden.md`.
