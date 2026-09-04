# Pakket 15a — Titel- en tagsuggestie uit de tekst

> **Agent-prompt:** Lees `werk/00-contract.md`, `werk/14-datum-uit-tekst.md` en `werk/15a-titel-en-tagsuggestie.md`. Dit pakket is gebouwd en gecommit (release 0.8.0, 2026-09-04); gebruik dit bestand als naslag bij vervolgwerk aan de suggestie en bij 15b. Afwijkingen bij het bouwen: rechtsvorm-achtervoegsels matchen hoofdlettergevoelig ("b.v." is in lopende tekst "bijvoorbeeld") en een instantie-voorvoegsel telt alleen met minstens één woord erachter; zie `werk/00-contract.md` › Wijzigingen.

**Doel:** Uit de gelezen tekst van een document een titel (alleen de bedrijfs- of instantienaam) en tags (het documenttype) voorstellen. Een pure module zonder I/O, met dezelfde opzet als `datum.py`, zodat 15b hem in het uploadformulier kan tonen en de inbox er nu al betere titels van krijgt dan de bestandsnaam. Daarnaast wordt `ingest.py` in twee fasen gesplitst (lezen vooraf, daarna aanmaken), omdat de titel pas ná het lezen bekend is en 15b tussen die fasen een tweede scherm zet.

**Lees eerst:** `werk/00-contract.md` (Ontwerpbeslissingen "Datum uit tekst", interfaces `datum.py`, `ingest.py`, `index.py`), `werk/14-datum-uit-tekst.md` (beslissingen 2 en 8, sectie gelijktijdigheid), `addon/ordner/ingest.py`, `addon/ordner/index.py` (`Reconciler._ingest`), `IDEAS.md` (het idee met de keuzes van Bas).

## Beslissingen (afgestemd met Bas op 2026-09-04)

1. **Titel = alleen de afzender.** De titel bevat uitsluitend de bedrijfs- of instantienaam ("Eneco", "Gemeente Amsterdam", "Belastingdienst"), nooit het documenttype of een jaartal. Wordt niets gevonden, dan is de titelsuggestie leeg; een verkeerde naam is erger dan geen naam.
2. **Documenttype = tag.** Woorden als factuur, offerte, polis, beschikking worden als tag voorgesteld, nooit in de titel of omschrijving.
3. **Omschrijving blijft leeg.** De module stelt geen omschrijving voor; die vult de gebruiker.
4. **Titelheuristiek, op prioriteit; de eerste stap met resultaat wint:**
   1. *Bekende titel uit het archief.* Een bestaande documenttitel die als heel woord (of hele woordreeks) in de tekst voorkomt, hoofdletterongevoelig. Langste titel wint; bij gelijke lengte de vroegste treffer in de tekst. Overgeslagen: titels korter dan 3 tekens, de fallback-titel `document`, en titels die zelf een documenttypewoord zijn (anders matcht een oud document "Factuur" op alles). Dit leert vanzelf: wie eenmaal "Eneco" heeft getypt, krijgt het bij de volgende Eneco-factuur voorgesteld.
   2. *Naam achter "t.n.v." of "ten name van"* (facturen: de begunstigde is de afzender). Hoofdletterongevoelig, optionele dubbele punt; de rest van de kolomcel (zie 5) tot maximaal 60 tekens, zonder leestekens aan de randen.
   3. *Eerste regel met een rechtsvorm of instantiewoord.* Achtervoegsels `B.V.`, `BV`, `N.V.`, `NV`, `V.O.F.`, `VOF`, `U.A.` → de kolomcel vanaf het begin tot en met het achtervoegsel ("Eneco Services B.V."). Voorvoegsels `Gemeente`, `Stichting`, `Vereniging`, `Waterschap`, `Provincie`, `Coöperatie`, `Ministerie` → vanaf het woord tot het eind van de cel ("Gemeente Amsterdam"). Losse woorden `Belastingdienst`, `Bank`, `Verzekeringen`, `Verzekeraar`, `Zorgverzekeraar`, `Ziekenhuis`, `Universiteit`, `Hogeschool` → de hele cel. Hele-woordmatch, hoofdletterongevoelig.
   4. *Korte tekst (bon): de eerste regel.* Alleen als de tekst minder dan `_MAX_REGELS_BON` (25) niet-lege regels heeft: de eerste niet-lege regel die minstens drie letters bevat en niet zelf een documenttypewoord of datum is.
   5. *Anders leeg.* De bovenste regel van een brief is meestal de ontvanger, dus nooit blind de eerste regel nemen.
   Woordenlijsten zijn module-constanten; uitbreiden is één regel plus een test.
5. **Kolomcellen.** `pdftotext -layout` zet adresblokken naast elkaar. Een regel wordt eerst gesplitst op twee of meer spaties (tabs geëxpandeerd) in cellen; stappen 2–4 werken per cel, niet per regel. Zo levert de regel "Eneco B.V.        Factuurnummer 123" de titel "Eneco B.V." en niet de hele regel.
6. **Opschonen.** Whitespace samengevoegd, leestekens aan de randen weg (`,;:.-` maar de punt van "B.V." blijft), maximaal 60 tekens (afkappen op woordgrens). Hoofdletters blijven zoals in de tekst ("ENECO" wordt niet "Eneco"); de gebruiker kan het aanpassen, en `maak_slug` maakt de mapnaam toch lowercase.
7. **Tagsuggestie.** Een documenttypewoord telt alleen als kopregel: een cel die gelijk is aan het woord of ermee begint gevolgd door een niet-letter ("Factuur", "FACTUUR", "Factuur nr. 123"; niet "Factuurdatum", niet "…deze factuur…"). Woordenlijst `_DOCUMENTTYPEN: dict[str, str]` (gevonden woord → tag): factuur, creditnota, offerte, polis, beschikking, nota, bon, kassabon → bon, herinnering, betalingsherinnering → herinnering, aanmaning, contract, overeenkomst, aanslag, jaaroverzicht, jaarafrekening, garantiebewijs → garantie. Tags in volgorde van eerste voorkomen, zonder dubbelen, lowercase. Geen kopregel → lege lijst.
8. **Meerdere bestanden.** De teksten van alle gelezen bestanden worden in uploadvolgorde aaneengeplakt (met een lege regel ertussen) en als één tekst beoordeeld; dat past bij een titel per document.
9. **Inbox gebruikt de suggestie.** Titel = suggestie als die niet leeg is, anders de bestandsnaam zoals nu (`_`/`-` → spatie, fallback `document`). Tags = tagsuggestie. Bekende titels komen uit de index (`{e.meta.titel for e in index.alle()}`). Documentdatum blijft zoals in pakket 14.
10. **Ingest in twee fasen.** `maak_document_uit_bestanden` wordt gesplitst in `lees_vooraf` (tempbestanden, tekst lezen, `vind_datum`) en `maak_document_uit_voorbereid` (map aanmaken, bestanden en `.txt` schrijven, queuen). De bestaande functie blijft bestaan als samenstelling van beide, zodat het uploadformulier tot 15b ongewijzigd werkt en de tests van pakket 14 blijven slagen. De gelijktijdigheidsregel uit pakket 14 blijft: queuen pas na de laatste schrijfactie.
11. **Het uploadformulier verandert in dit pakket niet.** Geen suggestie in de UI; dat is 15b. Gebruikers merken alleen de inbox-titels.

## Interfaces (worden toegevoegd aan `werk/00-contract.md`)

### `ordner/suggestie.py` (nieuw)
```python
TitelBron = Literal["archief", "tnv", "rechtsvorm", "eerste-regel", "geen"]

@dataclass(frozen=True)
class Suggestie:
    titel: str                  # "" als er geen betrouwbare naam is
    titelbron: TitelBron        # voor logging en tests
    tags: list[str]             # documenttype(n), lowercase, in volgorde van voorkomen

def stel_voor(tekst: str, bekende_titels: Iterable[str] = ()) -> Suggestie
    # pure functie; combineert stel_titel_voor en stel_tags_voor
def stel_titel_voor(tekst: str, bekende_titels: Iterable[str] = ()) -> tuple[str, TitelBron]
def stel_tags_voor(tekst: str) -> list[str]
def cellen(regel: str) -> list[str]     # splitst op 2+ spaties, tabs geëxpandeerd; ook bruikbaar voor datum.py later
```

### `ordner/ingest.py` (gesplitst)
```python
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
    # documentdatum gegeven → niets lezen, bron "gebruiker". None → zoals pakket 14: tekst lezen,
    # vind_datum op de eerste treffer (bron "tekst"), anders vandaag (bron "upload").

def maak_document_uit_voorbereid(archief: Archief, titel: str, vb: Voorbereid, *, omschrijving: str = "",
                                 tags: list[str] | None = None, queue_fn: QueueFn,
                                 documentdatum: date | None = None) -> Path
    # documentdatum None → vb.documentdatum en vb.datumbron; anders die datum met bron "gebruiker"
    # (15b: de gebruiker wijzigde het voorgevulde veld). Schrijft bestanden, .txt's, ocr-status; queued daarna.

def maak_document_uit_bestanden(...)   # ongewijzigde signatuur = lees_vooraf + maak_document_uit_voorbereid
```

### `ordner/index.py`
`Reconciler._ingest` gebruikt `lees_vooraf` → `stel_voor(vb.tekst, bekende_titels)` → `maak_document_uit_voorbereid`. Geen signatuurwijziging aan `Reconciler`.

## Maakt / wijzigt

- `addon/ordner/suggestie.py` (nieuw), `tests/test_suggestie.py` (nieuw): per heuristiekstap minstens één positieve en één negatieve test, plus: bekende titel wint van rechtsvorm; langste bekende titel wint; "document"/documenttypewoord als bekende titel wordt genegeerd; cel-splitsing bij layout-kolommen; "Factuurdatum" levert geen tag; "Vervaldatum"-achtige regels leveren geen titel; lege tekst → lege suggestie; afkappen op 60 tekens.
- `addon/ordner/ingest.py`: `Voorbereid`, `lees_vooraf`, `maak_document_uit_voorbereid`; `maak_document_uit_bestanden` als wrapper. `tests/test_ingest.py`: bestaande tests blijven groen; erbij: `lees_vooraf` zonder datum leest en vindt; `maak_document_uit_voorbereid` met afwijkende `documentdatum` zet bron `gebruiker`; `.txt` wordt geschreven en niet gequeued.
- `addon/ordner/index.py`: `_ingest` met suggestie; `tests/test_index.py`: inbox-bestand met "Eneco B.V." in de (gemockte) tekst krijgt titel "Eneco B.V." en tag `factuur` bij kopregel "Factuur"; zonder treffer blijft de bestandsnaam-titel.
- Docs: `addon/DOCS.md` sectie "Inbox" (titel uit de tekst, anders bestandsnaam; documenttype als tag) en een nieuwe korte sectie "Titel en tags uit de tekst" die de heuristiek in gebruikerstaal uitlegt (wordt in 15b uitgebreid); `addon/CHANGELOG.md` 0.8.0; `addon/config.yaml` version 0.8.0; `CLAUDE.md` (regel "Titel en tags uit tekst" in de ontwerptabel); `werk/00-contract.md` (interfaces + Wijzigingen); `werk/STATUS.md`.

## Let op

- **Pure functies.** `suggestie.py` importeert niets uit `storage`, `index` of `web`; alleen `re`, `dataclasses`, `typing`. Tests zonder fixtures.
- **Regex-hygiëne.** Bekende titels via `re.escape` en `\b`-grenzen (let op: `\b` werkt niet aan de rand van een titel die met een leesteken eindigt zoals "B.V."; gebruik lookarounds op `[^\W_]` of test dat expliciet).
- **Gelijktijdigheid.** `_ingest` draait in de reconciler-thread en leest `index.alle()`; dat gebeurde al voor de sync-stappen en is hier niet nieuw. Queuen blijft de laatste stap.
- **Logging.** Eén `log.info` per aanmaak met titelbron en tags, zoals `datum uit tekst voor …` in pakket 14.

## Bekende beperkingen / vervolg

- De woordenlijsten zijn Nederlands en niet geijkt op echte documenten; bij missers eerst de `.txt` bekijken en dan de lijst of de celregel bijstellen, met een test erbij. Engelse varianten ("Invoice", "Ltd.") later, één regel per woord.
- Een bankafschrift heeft "t.n.v. <eigen naam>": dan wordt de eigen naam voorgesteld. Acceptabel omdat de gebruiker in 15b de suggestie ziet vóór het opslaan; voor de inbox is het een verkeerde titel die achteraf gecorrigeerd moet worden.
- Later inwisselbaar voor een Claude-suggestie met dezelfde `Suggestie`-vorm (`IDEAS.md`, MCP/Claude-titelen).
- `cellen()` zou ook `datum.py` kunnen bedienen (kolomlayout); niet in dit pakket aanraken.
