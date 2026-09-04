# Ideeën (niet in v1)

- MCP-server (FastMCP) met `zoek_documenten`, `lees_document`, `bewerk_metadata`
- Claude-geassisteerd titelen van inbox-documenten
- **Tweestaps upload met titelsuggestie** (idee Bas, 2026-09-04; kandidaat pakket 15, nog niet besloten). Scherm 1: alleen bestanden kiezen. Scherm 2: alle velden van het document, voorgevuld met de datum uit de tekst (wijzigen = `datumbron: gebruiker`) en een automatisch voorgestelde titel die de gebruiker kan aanpassen. Aandachtspunten uit het gesprek: de documentmap kan pas ná scherm 2 worden aangemaakt (mapnaam = datum + slug van de titel, nooit hernoemen), dus de bestanden en de gelezen tekst wachten in een stagingmap (bijv. `_concept/<token>/`, net als `_inbox` buiten de index; onafgemaakte concepten tonen op de uploadpagina en/of na 24 u opruimen door de reconciler). Titelsuggestie als pure functie `titel.stel_titel_voor(tekst, bestandsnaam)` met heuristiek op prioriteit: regel achter "Betreft"/"Onderwerp"/"Subject" → documenttype (factuur, nota, offerte, polis, beschikking, aanslag, jaaropgave, contract, brief, …) + afzender (eerste regel met een bedrijfsnaam) → bestandsnaam als die niet generiek is (`IMG_`, `Scan`, `DSC`) → "Document". Dezelfde functie kan de inbox-titel verbeteren. Later inwisselbaar voor een Claude-suggestie.
- Submap in `_inbox/` = één document met meerdere bestanden
- "Alles opnieuw OCR'en"-knop
- Tag-overzicht
- SQLite FTS5 als de in-memory index te groot wordt (>5000 documenten)
- Prullenbak legen / terugzetten
- PDF/A-kopie met tekstlaag bewaren naast het origineel
- Datumherkenning: Engelse sleutelwoorden ("invoice date"; los "date" is riskant door "due date"/"payment date"); knop "datum opnieuw bepalen" voor bestaande documenten; labels over twee regels ("Factuur-" / "datum")
