# Ideeën (niet in v1)

- MCP-server (FastMCP) met `zoek_documenten`, `lees_document`, `bewerk_metadata`
- Claude-geassisteerd titelen van inbox-documenten
- ~~Tweestaps upload met titel- en tagsuggestie~~ — gedaan in 15c (tags als labels, 0.7.0), 15a (suggestie, 0.8.0) en 15b (tweestaps upload, 0.9.0); keuzes en heuristiek staan in `werk/15a-titel-en-tagsuggestie.md` en `werk/15b-tweestaps-upload.md`.
- Meerdere documenten in één upload (elk bestand een eigen document, of splitsen op scherm 2); nu wordt alles in scherm 1 één document.
- Openstaande uploads naar een tempmap buiten het archief als het geheugen ooit knelt (zelfde interface als `OpenstaandeUploads`).
- Submap in `_inbox/` = één document met meerdere bestanden
- "Alles opnieuw OCR'en"-knop
- Tag-overzicht
- SQLite FTS5 als de in-memory index te groot wordt (>5000 documenten)
- Prullenbak legen / terugzetten
- PDF/A-kopie met tekstlaag bewaren naast het origineel
- Datumherkenning: Engelse sleutelwoorden ("invoice date"; los "date" is riskant door "due date"/"payment date"); knop "datum opnieuw bepalen" voor bestaande documenten; labels over twee regels ("Factuur-" / "datum")
