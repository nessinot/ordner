# Pakket 05 — Index en reconciler

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/05-index-en-reconciler.md`. Voer pakket 05 uit. Draai `pytest`. Commit met bericht `pakket 05: index en reconciler`. Vink af in `werk/STATUS.md`.

**Doel:** in-memory index, zelfherstellende reconciler, inbox-ingest.

**Lees eerst:** `werk/00-contract.md` (Ontwerpbeslissingen "Index", "Reconciler", "Inbox"; Interface `index.py`).
**Vereist:** pakketten 02 en 03.

## Maakt

- `ordner/index.py`
- `tests/test_index.py`

## Specificatie

### `Index`
- `docs: dict[str, DocEntry]` (key = `rel`).
- `herlaad(archief, map)`: `meta = lees_meta(map)`; `teksten = {naam: txt_pad(map/naam).read_text("utf-8", errors="replace") for naam in meta.bestanden if txt_pad(map/naam).exists()}`; `DocEntry(rel=archief.relatief(map), map=map, meta=meta, teksten=teksten)` opslaan en teruggeven.
- `verwijder(rel)`: `docs.pop(rel, None)`.
- `alle()`: `sorted(docs.values(), key=lambda d: (d.meta.documentdatum, d.rel), reverse=True)`.
- `tellingen()`: `{"totaal": n, "pending": ..., "done": ..., "failed": ...}`.

### `bouw_index(archief)`
`Index()`; voor elke map in `archief.documentmappen()`: `herlaad`; `MetaFout` → `log.warning(...)` en overslaan.

### `Reconciler`
- `__init__(archief, index, queue_fn)`; `self._inbox_groottes: dict[Path, int] = {}`.
- `run()` → `ReconcileRapport`. Stappen:

  **A. Mappen zonder `meta.md`.** Voor elke map `root/JJJJ/*/` (jaar vier cijfers, mapnaam niet met `_` of `.`) zonder `meta.md` die minstens één gewoon bestand bevat:
  - Titel: mapnaam; als hij begint met `JJJJ-MM-DD_` dat prefix eraf; `_` en `-` → spatie; gestript.
  - Documentdatum: uit dat prefix als aanwezig, anders `date.today()`.
  - Uploaddatum: `datetime.fromtimestamp(map.stat().st_mtime).replace(second=0, microsecond=0)`.
  - `schrijf_meta(map, Meta(..., bestanden=[], ocr="done"))`; `meta_aangemaakt += 1`. (De sync in stap B vult `bestanden`.)

  **B. Per map in `archief.documentmappen()`:**
  1. `meta = lees_meta(map)` (`MetaFout` → warning, overslaan).
  2. Werkelijke bestanden: entries in de map die een gewoon bestand zijn, niet `meta.md`, niet eindigend op `.txt`, niet beginnend met `.`; gesorteerd op naam.
  3. Als `set(meta.bestanden) != set(werkelijk)`: `meta.bestanden = [n for n in meta.bestanden if n in werkelijk] + [n for n in werkelijk if n not in meta.bestanden]`; `gewijzigd = True`; `gesynchroniseerd += 1`.
  4. `nieuw = bepaal_ocr_status(map, meta)`; als `nieuw != meta.ocr`: `meta.ocr = nieuw`; `gewijzigd = True`.
  5. Als `gewijzigd`: `schrijf_meta`.
  6. Als `meta.ocr == "pending"`: voor elk `naam in meta.bestanden` met `is_extraheerbaar(naam)` en zonder `.txt` → `queue_fn(map, naam)`; `gequeued += 1`.
  7. `index.herlaad(archief, map)`; `documenten += 1`.

  **C. Verdwenen documenten:** elke `rel` in `index.docs` die niet meer bij een bestaande map hoort → `index.verwijder(rel)`.

  **D.** `inbox_verwerkt = len(self.verwerk_inbox())`.

- `verwerk_inbox()` → lijst van aangemaakte documentmappen:
  - Kandidaten: gewone bestanden direct in `archief.inbox_dir`, naam niet beginnend met `.`.
  - Voor elk: `grootte = stat().st_size`. Als `self._inbox_groottes.get(pad) == grootte`: ingest. Anders `self._inbox_groottes[pad] = grootte` en wachten.
  - Ingest: `titel = pad.stem.replace("_", " ").replace("-", " ").strip() or "document"`; `doc = archief.maak_document(titel, date.today())`; `naam = archief.voeg_bestand_toe(doc, pad.name, pad.read_bytes())`; `pad.unlink()`; als `is_extraheerbaar(naam)`: `queue_fn(doc, naam)`; `index.herlaad(archief, doc)`; uit `_inbox_groottes`.
  - Paden in `_inbox_groottes` die niet meer bestaan → verwijderen uit de dict.
  - Fouten per bestand loggen en doorgaan met het volgende.

## Tests

Gebruik de `archief`-fixture en een `queue_fn` die aanroepen in een lijst verzamelt.

- `bouw_index`: document met `a.pdf` + `a.pdf.txt` → `teksten == {"a.pdf": "..."}`; document zonder `.txt` → `teksten == {}`.
- Kapotte `meta.md` (geen frontmatter) → overgeslagen, geen exception.
- `alle()`: drie documenten met verschillende datums → nieuwste eerst; gelijke datum → `rel` desc.
- `tellingen()`.
- Reconciler: bestand "via Samba" in een documentmap geplaatst → na `run()` in `bestanden`, `ocr == "pending"`, `queue_fn` aangeroepen met `(map, naam)`, rapport `gesynchroniseerd == 1`, `gequeued == 1`.
- Bestand van schijf verwijderd → uit `bestanden`.
- `ocr: failed` met bestand zonder `.txt` → niet gequeued, status blijft `failed`.
- Map `2025/2025-05-01_oude_factuur/` met `x.pdf` zonder `meta.md` → `meta.md` aangemaakt met titel `oude factuur`, datum `2025-05-01`, `bestanden == ["x.pdf"]`; rapport `meta_aangemaakt == 1`.
- Map zonder datumprefix → datum vandaag.
- Document uit index waarvan de map verwijderd is → na `run()` niet meer in `index.docs`.
- Inbox: bestand neerzetten → eerste `verwerk_inbox()` doet niets (lijst leeg, inbox nog vol); tweede met gelijke grootte → document aangemaakt in het jaar van vandaag, inbox leeg, `queue_fn` aangeroepen, document in index.
- Inbox: bestand groeit tussen polls → blijft wachten.
- Inbox: `.docx` → document aangemaakt maar niet gequeued.

## Buiten scope

Zoeken (06), asyncio-lussen (07).
