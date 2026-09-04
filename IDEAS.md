# Ideeën (niet in v1)

- MCP-server (FastMCP) met `zoek_documenten`, `lees_document`, `bewerk_metadata`
- Claude-geassisteerd titelen van inbox-documenten
- **Tweestaps upload met titel- en tagsuggestie** (idee Bas, 2026-09-04; kandidaat pakket 15, nog geen pakketbestand). Scherm 1: strikt alleen bestanden kiezen, geen titelveld (besloten 2026-09-04). Scherm 2: alle velden van het document, voorgevuld met de datum uit de tekst (wijzigen = `datumbron: gebruiker`), een voorgestelde titel en voorgestelde tags; de gebruiker kan alles aanpassen. Na opslaan een duidelijke melding "Opgeslagen".
  Vaste keuzes van Bas: (1) concepten hoeven een herstart niet te overleven, een upload is pas compleet na scherm 2, dus staging mag in het geheugen of een tijdelijke map buiten het archief, geen `_concept/` in `/share/ordner`; (2) de titel bevat alléén de bedrijfs- of instantienaam ("Eneco", "Gemeente Amsterdam"), nooit het documenttype; (3) het documenttype (factuur, offerte, polis, beschikking, …) wordt een tag, niet een titel- of omschrijvingsdeel; (4) de omschrijving blijft altijd leeg, die vult de gebruiker.
  Voorstel Claude voor de titelheuristiek, op prioriteit: bestaande titel uit het archief die als woord in de tekst voorkomt (langste wint; leert vanzelf van eerdere documenten) → naam achter "t.n.v."/"ten name van" (facturen) → eerste regel met rechtsvorm of instantiewoord (B.V., N.V., Stichting, Gemeente, Waterschap, Belastingdienst, Bank, Verzekeringen) → bij korte teksten (bonnen) de eerste regel → leeg, want de bovenste regel van een brief is meestal de ontvanger. Tagsuggestie: documenttypewoord alleen als het als kopregel voorkomt (regel is of begint met het woord). Pure functies, later inwisselbaar voor een Claude-suggestie. Dezelfde functies kunnen de inbox bedienen.
  Opdeling en volgorde (akkoord Bas 2026-09-04): 15c tags als labels (eerst, klein) → 15a titel- en tagsuggestie (pure module, ook voor de inbox) → 15b tweestaps upload. Volgende stap: de drie pakketbestanden schrijven in `werk/`.
  Los onderdeel, ook apart te doen: tags als afgeronde labels rechts in het zoekresultaat en op de documentpagina; klikken zet het woord in het zoekveld.
- Submap in `_inbox/` = één document met meerdere bestanden
- "Alles opnieuw OCR'en"-knop
- Tag-overzicht
- SQLite FTS5 als de in-memory index te groot wordt (>5000 documenten)
- Prullenbak legen / terugzetten
- PDF/A-kopie met tekstlaag bewaren naast het origineel
- Datumherkenning: Engelse sleutelwoorden ("invoice date"; los "date" is riskant door "due date"/"payment date"); knop "datum opnieuw bepalen" voor bestaande documenten; labels over twee regels ("Factuur-" / "datum")
