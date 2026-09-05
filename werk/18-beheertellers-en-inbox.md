# Pakket 18 — Beheertellers: OCR-labels en inboxtabel

> **Agent-prompt:** Lees `werk/00-contract.md` en dit bestand. Bouw alleen wat hier staat; ideeën gaan naar `IDEAS.md`. Werk af met groene `pytest`, release notes in `addon/CHANGELOG.md` (0.12.0), versiebump in `addon/config.yaml`, de regel in `werk/STATUS.md` en de interfacewijzigingen in `werk/00-contract.md`. Afwijkingen onderaan dit bestand noteren.

**Doel:** De tellers op de beheerpagina zeggen precies wat ze tellen, en de inbox krijgt een eigen tabel met drie tellers: hoeveel bestanden er in `_inbox/` liggen, hoeveel daarvan op een titel wachten, en hoeveel er als dubbel in `_inbox/_dubbel/` zijn gezet. Alle tellers worden live bijgewerkt.

**Aanleiding (gesprek met Bas, 2026-09-05):** De vraag "waar zie ik hoeveel documenten er in de inbox zitten?" had als antwoord: nergens. "In wachtrij" bleek de OCR-wachtrij van archiefdocumenten te zijn, en de rij "Inbox wacht op titel" telt alleen het eindstation: een bestand dat net is neergezet doorloopt eerst stabiliteitscheck, hashcontrole en tekstlezen (seconden tot een minuut per bestand, één tegelijk) en telt in die tijd nergens mee. Daarnaast verdwijnen dubbelen stil in `_inbox/_dubbel/` met alleen een logregel; niemand kijkt in die map.

**Lees eerst:** `addon/ordner/index.py` (`Index.tellingen`, `Reconciler.verwerk_inbox`, `wachtend`, `_is_dubbel`), `addon/ordner/web/routes.py` (`status`, `beheer`, `zoeken`, `inbox`), `addon/ordner/web/templates/beheer.html`, `addon/ordner/web/static/app.js` (blok "beheerpagina: tellingen live bijwerken"), `tests/test_web.py` (`test_status_api`, `test_inbox_wachtend_op_pagina_startpagina_en_beheer`), `tests/e2e/test_browser.py` (`test_beheer`), `addon/DOCS.md` (secties "Inbox" en "Beheerpagina").

## Beslissingen (afgestemd met Bas op 2026-09-05)

1. **Labels in de tabel Documenten.** De verwarring zit tussen "OCR wacht" (documenten met `ocr: pending`) en "In wachtrij" (bestanden in de OCR-wachtrij van de worker). De eenheid komt in het label:

   | Nu | Wordt |
   |---|---|
   | Totaal | Totaal |
   | OCR klaar | OCR klaar |
   | OCR wacht | OCR nog te doen |
   | OCR mislukt | OCR mislukt |
   | In wachtrij | OCR-wachtrij (bestanden) |
   | Inbox wacht op titel | *verhuist naar de tabel Inbox* |
   | Cache verversen | Cache verversen |

   Onder de tabel één hintregel: "De eerste vier rijen tellen documenten (klaar, nog te doen en mislukt tellen op tot het totaal). De wachtrij telt bestanden die de tekstlezer nog moet doen." De `data-tel`-namen (`totaal`, `done`, `pending`, `failed`, `queue`, `reconcile`) blijven zoals ze zijn; alleen de zichtbare tekst verandert.

2. **Nieuwe tabel Inbox** als eigen `section.paneel` met `<h3>Inbox</h3>`, tussen "Documenten" en "Nu bezig":

   | Rij | Telt | Link |
   |---|---|---|
   | Totaal | Gewone bestanden direct in `_inbox/` (niet beginnend met `.`; submappen `.tekst/` en `_dubbel/` tellen niet mee). Zelfde filter als de kandidaten in `verwerk_inbox`. Gereserveerde bestanden tellen mee: ze liggen er. | geen |
   | Wacht op titel | `len(reconciler.wachtend())`, zoals de huidige rij. | altijd een link naar `/inbox`, ook bij 0 (de pagina zegt dan "De inbox is leeg."); zo kan de live-update de tekst in de `<a>` vervangen zonder de link te breken |
   | Dubbel | Gewone bestanden in `_inbox/_dubbel/`; map ontbreekt → 0. | geen |

   Het verschil Totaal − Wacht op titel is "wordt nog beoordeeld of gelezen, of staat open op scherm 2". Dat wordt niet apart getoond. Onder de tabel een hintregel met de paden: "Bestanden in `<inbox_map>` neemt Ordner op zodra het de afzender herkent; de rest wacht op een titel. Dubbel: bestanden die al in het archief stonden, in `<inbox_map>/_dubbel`. Die ruimt Ordner niet op." (`inbox_map` zoals de inboxpagina hem al krijgt.)

3. **Eén telfunctie, drie afnemers.** `Reconciler.inbox_telling()` levert een `InboxTelling(totaal, wachtend, dubbel)`. De routes `beheer` en `status` gebruiken hem; `zoeken` gebruikt `inbox_telling().wachtend` in plaats van `len(wachtend())` (gedrag gelijk). De routes lezen nooit zelf uit `_inbox/`; alles loopt via `Reconciler` (beslissing 8 van pakket 17 blijft gelden).

4. **Live bijwerken.** `GET /api/status` krijgt een sleutel `inbox` met `{"totaal": n, "wachtend": n, "dubbel": n}`. `app.js` zet de drie waarden in `data-tel="inbox-totaal"`, `inbox-wachtend` en `inbox-dubbel`; bij `inbox-wachtend` staat het attribuut op de `<a>` zelf, zodat `zet()` ongewijzigd `textContent` kan vervangen. De poll van 3 s blijft; de telling kost drie directory-scans plus één `stat` per wachtend bestand, wat bij honderden bestanden nog niets is. Geen cache.

5. **Rapport "Laatste verversing" ongewijzigd.** De rijen "Inbox verwerkt" en "Inbox wacht op titel" daar zijn een momentopname van die ronde en blijven staan; e2e `test_beheer` leunt op de tekst "Inbox verwerkt".

6. **Inboxpagina ongewijzigd.** Geen upload naar de inbox via een formulier, geen lijst van alle inboxbestanden met status (beide besproken en voor nu niet gewild; het idee staat in `IDEAS.md`). Daarom linkt alleen "Wacht op titel" naar de inboxpagina: bij "Totaal" zou de lijst korter zijn dan het getal belooft.

7. **Versie 0.12.0.** Zichtbaar nieuw gedrag (labels, tabel, statusantwoord), geen wijziging op schijf.

## Interfaces (worden toegevoegd aan `werk/00-contract.md`)

### `ordner/index.py`
```python
@dataclass(frozen=True)
class InboxTelling:
    totaal: int      # gewone bestanden direct in _inbox/ (naam niet beginnend met "."); gereserveerde tellen mee
    wachtend: int    # len(wachtend())
    dubbel: int      # gewone bestanden in _inbox/_dubbel/; map ontbreekt -> 0

class Reconciler:
    def inbox_telling(self) -> InboxTelling   # drie directory-scans, geen cache; veilig vanaf de event loop (alleen stat/iterdir)
```

### Web
- `GET /api/status`: antwoord krijgt `"inbox": {"totaal": int, "wachtend": int, "dubbel": int}` naast `queue`, `bezig`, `reconcile_bezig`, `tellingen` (en `ocr` bij `?rel=`).
- `GET /beheer`: context `inbox: InboxTelling` en `inbox_map: str` (vervangt `inbox_wachtend`).
- `GET /` (zoeken zonder `q`): `inbox_wachtend` blijft, nu uit `inbox_telling().wachtend`.
- `beheer.html`: labels volgens beslissing 1; nieuwe sectie Inbox volgens beslissing 2; rij "Inbox wacht op titel" uit de tabel Documenten weg.
- `app.js`: na `zet("queue", ...)`: `zet("inbox-totaal", s.inbox.totaal); zet("inbox-wachtend", s.inbox.wachtend); zet("inbox-dubbel", s.inbox.dubbel);`.

## Maakt / wijzigt

- `addon/ordner/index.py` (`InboxTelling`, `Reconciler.inbox_telling`), `web/routes.py` (`status`, `beheer`, `zoeken`), `templates/beheer.html`, `static/app.js`. Geen wijziging in `storage.py`, `config.py` of de templates van de inboxpagina.
- Tests:
  - `test_index.py`: `inbox_telling` op lege inbox → `(0, 0, 0)`; bestanden plus een `.`-bestand en de submappen `.tekst/` en `_dubbel/` → alleen de gewone bestanden in `totaal`, de bestanden in `_dubbel/` in `dubbel`; na een poll die een bestand zonder titel beoordeelt → `wachtend` 1 en `totaal` 1; na `reserveer` → `wachtend` 0 en `totaal` 1; `_dubbel/` ontbreekt → `dubbel` 0.
  - `test_web.py`: `test_status_api` verwacht de sleutel `inbox` erbij (de set-assertie op regel 1149 en de lege telling); beheerpagina toont de drie rijen met `data-tel="inbox-totaal"`, `inbox-wachtend` (met `href="/inbox"`, ook bij 0) en `inbox-dubbel`; de labels "OCR nog te doen" en "OCR-wachtrij (bestanden)" staan erin en "In wachtrij" niet meer; `test_inbox_wachtend_op_pagina_startpagina_en_beheer` past de assertie `data-tel="inbox"><a href="/inbox">1</a>` aan; een bestand in `_inbox/_dubbel/` telt op de beheerpagina en in `/api/status`.
  - `tests/e2e/test_browser.py` › `test_beheer`: `.beheer table` wordt drie tabellen (Documenten, Inbox, rapport); de wachtlus en de assertie op `== 2` worden `== 3`.
- Docs: `addon/DOCS.md` (sectie "Beheerpagina" herschrijven met de twee tabellen en wat elke rij telt; sectie "Inbox": de beheerpagina toont ook het totaal en de dubbelen), `addon/CHANGELOG.md` 0.12.0, `addon/config.yaml` 0.12.0, `werk/00-contract.md` (interfaces hierboven, routetabel `status` en `beheer`, regel bij Wijzigingen), `werk/STATUS.md`, `CLAUDE.md` (rij Inbox: "Teller op startpagina en beheer" → "Teller op startpagina; tabel Inbox met totaal, wachtend en dubbel op beheer"), `IDEAS.md` (upload naar de inbox via een formulier met multiselect, en de inboxpagina die alle bestanden met status toont: besproken 2026-09-05, voorlopig niet).

## Let op

- **Threads.** `inbox_telling` draait op de event loop terwijl de poll-thread `_inbox/` verandert; `iterdir` en `stat` kunnen `OSError` geven voor een bestand dat net verhuisd is. Overslaan, zoals `wachtend()` al doet; nooit een 500 op de beheerpagina door een bestand dat net is opgenomen.
- **`_dubbel/` kan ontbreken.** `_is_dubbel` maakt de map pas aan bij het eerste dubbel; `inbox_telling` mag hem niet aanmaken.
- **Link altijd renderen.** De huidige template rendert bij 0 een kale "0" zonder link; dat wordt bij "Wacht op titel" altijd `<a data-tel="inbox-wachtend" href="...">n</a>`. De bestaande assertie in `test_web.py` op `data-tel="inbox">` moet daarop mee.
- **Geen nieuwe `data-tel`-collisions.** `zet()` zoekt op `[data-tel="..."]` binnen `[data-beheer]`; de rapporttabel heeft geen `data-tel` en blijft statisch.

## Afwijkingen bij het bouwen

Gebouwd 2026-09-05 (release 0.12.0). Geen afwijkingen van de beslissingen en interfaces hierboven. Twee kleine aanvullingen:

- De telling zit in een modulefunctie `_tel_bestanden(map)` in `index.py`, gedeeld door `totaal` en `dubbel`; `is_file()` per bestand en `iterdir()` op de map zitten elk in een eigen `try/except OSError` (bestand net verhuisd → niet geteld, map net weg → 0). `_dubbel/` wordt niet aangemaakt.
- `test_web.py` heeft naast de genoemde aanpassingen een eigen test `test_beheer_telt_inbox_totaal_en_dubbel` (bestand dat nog niet beoordeeld is telt in `totaal` maar niet in `wachtend`; bestand in `_dubbel/`; `.`-bestand telt niet). De e2e-test controleert bovendien dat de rij "Wacht op titel" een `href` naar `/inbox` heeft.
