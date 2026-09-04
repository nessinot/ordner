# Pakket 02 — Meta en slug

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/02-meta-en-slug.md`. Voer pakket 02 uit. Draai `pytest`. Commit met bericht `pakket 02: meta en slug`. Vink af in `werk/STATUS.md`.

**Doel:** `meta.md` betrouwbaar lezen en schrijven; slug-regels.

**Lees eerst:** `werk/00-contract.md` (secties Ontwerpbeslissingen, Datamodel, Interfaces `slug.py` en `meta.py`).
**Vereist:** pakket 01.

## Maakt

- `ordner/slug.py`
- `ordner/meta.py`
- `tests/test_slug.py`
- `tests/test_meta.py`

## Specificatie

### `maak_slug`
Regels volgens contract. Voorbeelden die moeten kloppen:

| Invoer | Uitvoer |
|---|---|
| `"WOZ-beschikking 2026"` | `woz-beschikking-2026` |
| `"Café Zürich — bon"` | `cafe-zurich-bon` |
| `"   "` | `document` |
| `"a" * 80` | 60 tekens |
| `"x" * 59 + " y"` | 60 tekens, eindigt niet op `-` |

Implementatie: `unicodedata.normalize("NFKD", titel)`, combining characters (`unicodedata.combining(c)`) weglaten, `.lower()`, `re.sub(r"[^a-z0-9]+", "-", ...)`, `.strip("-")`, afkappen op 60, opnieuw `.strip("-")`, leeg → `"document"`.

### `parse_meta(tekst)`
- Tekst moet beginnen met `---` op de eerste regel; frontmatter loopt tot de volgende regel die exact `---` is. Anders `MetaFout("geen frontmatter")`.
- Frontmatter via `yaml.safe_load`; resultaat moet een dict zijn.
- `titel` verplicht (string, gestript, niet leeg) → anders `MetaFout`.
- `documentdatum` verplicht; accepteert `date` (PyYAML parseert `2026-03-01` al als date) of ISO-string; anders `MetaFout`.
- `uploaddatum`: `datetime` of string `JJJJ-MM-DDTHH:MM` (ook met seconden accepteren); ontbrekend → `datetime.combine(documentdatum, time())`.
- `omschrijving` ontbrekend of `None` → `""`. `tags`/`bestanden` ontbrekend of `None` → `[]`; elementen naar `str`.
- `ocr` ontbrekend of ongeldig → `"done"`.
- `notities` = alles na de sluitende `---`-regel; één leading newline strippen; trailing whitespace behouden zoals het is maar `\r\n` → `\n`.

### `render_meta(meta)`
Exact formaat:
```
---
titel: WOZ-beschikking 2026
omschrijving: ''
documentdatum: 2026-03-01
uploaddatum: '2026-09-03T14:12'
tags: [woz, gemeente]
bestanden: [beschikking.pdf]
ocr: done
---
<notities>
```
- Keys in exact deze volgorde. Gebruik `yaml.safe_dump(dict, sort_keys=False, allow_unicode=True, default_flow_style=None, width=1000)`.
- `documentdatum` als `date` doorgeven (PyYAML schrijft `2026-03-01`); `uploaddatum` als string `meta.uploaddatum.strftime("%Y-%m-%dT%H:%M")` (PyYAML zet daar quotes omheen — prima).
- Lijsten moeten flow-style zijn (`[a, b]`), ook als ze leeg zijn (`[]`). `default_flow_style=None` doet dit voor lijsten van scalars; verifieer in de test.
- Na de sluitende `---` een newline en dan `notities`. Als `notities` leeg is eindigt het bestand op `---\n`.
- Roundtrip-eis: `parse_meta(render_meta(m)) == m` voor elke geldige `Meta`.

### `lees_meta` / `schrijf_meta`
- `lees_meta(map)`: leest `map / META_NAAM` met `encoding="utf-8"`; bestand ontbreekt → `MetaFout`.
- `schrijf_meta(map, meta)`: schrijf naar `map / ".meta.md.tmp"` (utf-8, newline `"\n"`), daarna `os.replace(tmp, map / META_NAAM)`.

### Overig
- `bepaal_ocr_status(map, meta)`: `"failed"` → `"failed"`; anders `"pending"` als er een `naam in meta.bestanden` is met `is_extraheerbaar(naam)` en `not txt_pad(map / naam).exists()`; anders `"done"`.
- `txt_pad(bestand)`: `bestand.with_name(bestand.name + ".txt")`.
- `is_extraheerbaar(naam)`: `Path(naam).suffix.lower() in EXTRAHEERBAAR`.

## Tests

- Slug: alle voorbeelden uit de tabel.
- Meta roundtrip: volledig gevulde `Meta` met unicode in titel en meerdere regels notities.
- Meta roundtrip: minimale `Meta` (lege lijsten, lege omschrijving, lege notities) — controleer dat de output letterlijk `tags: []` en `bestanden: []` bevat.
- Rendering: output begint met `---\ntitel:` en key-volgorde klopt.
- `parse_meta`: geen frontmatter → `MetaFout`; geen titel → `MetaFout`; geen documentdatum → `MetaFout`; datum als string wordt `date`.
- Defaults: `ocr` ontbreekt → `"done"`; `tags` ontbreekt → `[]`.
- `schrijf_meta` + `lees_meta` op `tmp_path`: gelijk, en geen `.meta.md.tmp` achtergebleven.
- `bepaal_ocr_status`: alle drie de takken (failed blijft failed; pdf zonder txt → pending; pdf met txt → done; alleen `.docx` → done).

## Buiten scope

Mappen aanmaken, bestanden opslaan (pakket 03).
