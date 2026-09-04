# Pakket 03 — Storage

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/03-storage.md`. Voer pakket 03 uit. Draai `pytest`. Commit met bericht `pakket 03: storage`. Vink af in `werk/STATUS.md`.

**Doel:** documentmappen aanmaken, bestanden toevoegen, prullenbak, veilige paden.

**Lees eerst:** `werk/00-contract.md` (Ontwerpbeslissingen, Datamodel, Interface `storage.py`).
**Vereist:** pakket 02.

## Maakt

- `ordner/storage.py`
- `tests/test_storage.py`
- `archief`-fixture toevoegen aan `tests/conftest.py`: `Archief(tmp_path / "archief")`.

## Specificatie

### `Archief.__init__(root)`
Maakt `root`, `root/_inbox` en `root/_prullenbak` aan (`mkdir(parents=True, exist_ok=True)`). Bewaart ze als `root`, `inbox_dir`, `trash_dir` (allemaal `.resolve()`d).

### `maak_document(titel, documentdatum, omschrijving="", tags=None, nu=None)`
- Jaarmap: `root / str(documentdatum.year)`.
- Mapnaam: `f"{documentdatum:%Y-%m-%d}_{maak_slug(titel)}"`; als de map bestaat: `_2`, `_3`, … tot een vrije naam.
- `uploaddatum = (nu or datetime.now()).replace(second=0, microsecond=0)`.
- Schrijft `meta.md` met `Meta(titel=titel.strip(), documentdatum, uploaddatum, omschrijving, tags=list(tags or []), bestanden=[], ocr="done")`.
- Geeft de absolute map terug.

### `voeg_bestand_toe(doc, naam, data)`
Sanering van `naam`, in deze volgorde:
1. `Path(naam).name` (alleen basename; ook backslashes afknippen: neem het deel na de laatste `/` of `\`).
2. Tekens buiten `[A-Za-z0-9._ -]` → `_`.
3. Leading `.` → `_`; leeg resultaat → `bestand`.
4. Naam gelijk aan `meta.md` (case-insensitive) → `meta_1.md`.
5. Als de naam eindigt op `.txt` en `naam[:-4]` bestaat als bestand in de map (dus het zou botsen met een OCR-tekstbestand) → behandel als conflict.
6. Conflict (bestand bestaat al, of stap 5): `stam_2.ext`, `stam_3.ext`, …

Daarna:
- Schrijf `data` atomic: `doc / (".tmp-" + naam)` → `os.replace`.
- `meta = lees_meta(doc)`; `naam` toevoegen aan `meta.bestanden` als hij er nog niet in staat.
- Als `meta.ocr == "failed"` en `is_extraheerbaar(naam)`: `meta.ocr = "pending"` (een nieuw bestand verdient een poging) — daarna `meta.ocr = bepaal_ocr_status(doc, meta)` alleen als de status niet al `pending` is. Simpelste correcte implementatie: `if meta.ocr == "failed" and is_extraheerbaar(naam): meta.ocr = "done"` en daarna altijd `meta.ocr = bepaal_ocr_status(doc, meta)`.
- `schrijf_meta`; geef `naam` terug.

### `naar_prullenbak(doc)`
- Doel: `trash_dir / doc.name`; bestaat het al → `f"{doc.name}_{datetime.now():%Y%m%d-%H%M%S}"`.
- `shutil.move`. Lege jaarmap laten staan. Geeft het nieuwe pad terug.

### `documentmappen()`
`sorted(p.parent for p in root.glob("[0-9][0-9][0-9][0-9]/*/meta.md") if not p.parent.name.startswith(("_", ".")))`.

### `relatief(doc)`
`doc.relative_to(root).as_posix()`.

### `veilig_pad(jaar, map, naam=None)`
- Elke component: niet leeg, geen `/`, geen `\`, niet `..`, niet `.`; `jaar` exact vier cijfers.
- `pad = (root / jaar / map / naam).resolve()` (zonder `naam` als die `None` is).
- `pad.is_relative_to(root)` moet gelden en `pad.exists()`; anders `OngeldigPad`.

## Tests

- Mapnaam `2026/2026-03-01_woz-beschikking-2026`; tweede keer zelfde titel+datum → `_2`, derde → `_3`.
- `meta.md` na aanmaken: titel, datum, `bestanden: []`, `ocr: done`, uploaddatum zonder seconden.
- `voeg_bestand_toe`: `"../../etc/passwd"` → `passwd`; `"foto (1).JPG"` → `foto _1_.JPG`; `".env"` → `_env`; `""` → `bestand`; `"meta.md"` → `meta_1.md`.
- Conflict: twee keer `a.pdf` → tweede wordt `a_2.pdf`; beide in `bestanden`.
- `.txt`-botsing: eerst `a.pdf`, dan upload `a.pdf.txt` → opgeslagen als `a.pdf_2.txt`.
- `ocr` na toevoegen: pdf → `pending`; alleen `.docx` → `done`.
- `failed` + nieuw pdf → `pending`.
- Prullenbak: map staat in `_prullenbak/<naam>`; tweede keer met zelfde naam → suffix met timestamp; origineel weg.
- `documentmappen` slaat `_inbox`, `_prullenbak`, `.hidden`, `abc/` en mappen zonder `meta.md` over; volgorde gesorteerd.
- `veilig_pad`: geldig pad werkt; `..`, `a/b`, `a\b`, lege string, jaar `20x6`, onbestaand bestand → `OngeldigPad`.

## Buiten scope

Extractie, index, web.
