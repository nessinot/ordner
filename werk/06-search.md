# Pakket 06 — Search

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/06-search.md`. Voer pakket 06 uit. Draai `pytest`. Commit met bericht `pakket 06: search`. Vink af in `werk/STATUS.md`.

**Doel:** de losse zoekfunctie (later ook via een MCP-server te gebruiken).

**Lees eerst:** `werk/00-contract.md` (Ontwerpbeslissing "Zoeken", Interface `search.py`).
**Vereist:** pakket 05.

## Maakt

- `ordner/search.py`
- `tests/test_search.py`

## Specificatie

### `zoek(index, query, limiet=50)`
- `woorden = query.lower().split()`; leeg → `[]`.
- Per `DocEntry` de doorzoekbare velden, in deze volgorde:
  ```python
  velden = [
      ("titel", meta.titel),
      ("omschrijving", meta.omschrijving),
      ("tags", " ".join(meta.tags)),
      ("documentdatum", meta.documentdatum.isoformat()),
      ("notities", meta.notities),
  ] + [(naam, tekst) for naam, tekst in entry.teksten.items()]
  ```
- Vergelijk op `.lower()` van elk veld. Een document matcht als **elk** woord in **minstens één** veld voorkomt (substring-match; geen tokenisatie).
- Snippet: neem het eerste woord; het eerste veld (in bovenstaande volgorde) waarin dat voorkomt is de bron. `i = veld_lower.find(woord)`; neem `tekst[max(0, i-80) : i+len(woord)+80]`; whitespace-runs → één spatie; `…` vooraan als `i-80 > 0`, achteraan als het einde afgekapt is. `bron` = veldnaam of bestandsnaam.
- Resultaten in de volgorde van `index.alle()` (documentdatum desc, rel desc), afgekapt op `limiet`.
- Houd het simpel: lowercasen per zoekopdracht is acceptabel. Geen voorberekende cache, geen ranking.

## Tests

Bouw in een fixture een `Index` met een paar handmatig aangemaakte `DocEntry`'s (via `archief.maak_document` + `.txt`-bestanden schrijven + `index.herlaad`).

- Eén woord in titel → één treffer, `bron == "titel"`.
- Woord alleen in een `.txt` → treffer, `bron` = bestandsnaam.
- AND: `"woz gemeente"` waarbij `woz` in de titel en `gemeente` in een `.txt` staat → treffer; `"woz nietbestaand"` → geen treffer.
- Hoofdletterongevoelig: query `"CAFÉ"` matcht titel `"café"`; query `"café"` matcht titel `"CAFÉ"`.
- Datum: `"2026-03"` matcht document met `documentdatum = 2026-03-01`, `bron == "documentdatum"`.
- Tags en notities worden doorzocht.
- Snippet: lange `.txt` met het woord in het midden → snippet begint en eindigt met `…` en bevat het woord.
- Lege query en whitespace-query → `[]`.
- `limiet=1` → één resultaat, het nieuwste.
- Volgorde: nieuwste documentdatum eerst.

## Buiten scope

Web-weergave (08).
