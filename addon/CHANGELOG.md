# Changelog

Home Assistant toont dit bestand onder het tabblad **Changelog** van de add-on. Nieuwste versie bovenaan; de bovenste kop moet gelijk zijn aan `version` in `config.yaml` (dat controleert `tests/test_addon_config.py`).

## 0.8.0 (2026-09-04)

- Documenten uit de inbox krijgen hun titel uit de tekst: de naam van het bedrijf of de instantie (bijvoorbeeld "Eneco Services B.V." of "Gemeente Amsterdam"). Staat er geen herkenbare naam in, dan blijft de bestandsnaam de titel. Titels die je al eerder in het archief gebruikt hebt, worden het eerst herkend.
- Het documenttype (factuur, offerte, polis, beschikking, bon, herinnering, aanmaning, contract, aanslag, jaaroverzicht en meer) wordt bij inboxdocumenten als tag toegevoegd, zodat je er meteen op kunt klikken.
- Nieuwe sectie "Titel en tags uit de tekst" in de documentatie. Het uploadformulier verandert nog niet; daar komt de suggestie in een volgende versie.

## 0.7.0 (2026-09-04)

- Tags zijn nu klikbare labels, in de resultatenlijst en op de documentpagina. Klik op een tag om alle documenten met die tag te zien; de tag vervangt de huidige zoekopdracht.
- In de resultatenlijst is de hele kaart nog steeds klikbaar, inclusief het tekstfragment bij zoekresultaten; alleen de labels gaan naar de tag-zoekopdracht.

## 0.6.0 (2026-09-04)

- Datum uit tekst herkent nu ook tabellen waarin het label boven de waarde staat, zoals "Factuurdatum / Factuurnummer / Vervaldatum" met de datums op de regel eronder. De datum in dezelfde kolom als het label wint.

## 0.5.0 (2026-09-04)

- Laat je het datumveld bij uploaden leeg, dan leest Ordner de datum uit het document zelf (factuurdatum, notadatum, orderdatum, dagtekening of datum). Geen datum gevonden: de dag van uploaden.
- Documenten uit de inbox krijgen op dezelfde manier hun datum.
- De documentpagina toont een label "datum uit tekst" of "datum van upload"; wijzig je de datum zelf, dan verdwijnt het label. Nieuw veld `datumbron` in `meta.md`.

## 0.4.1 (2026-09-04)

- Terugknop op de documentpagina die de zoekopdracht onthoudt, ook na opslaan, OCR opnieuw, toevoegen of verwijderen.

## 0.4.0 (2026-09-04)

- Eerste publieke versie, installeerbaar via de Add-on store.
- Startscherm toont de 20 nieuwste documenten met het totaal eronder; zoeken toont het echte aantal treffers, kapt af op 50 en biedt "Toon alle".
- Uploaden, zoeken, documentpagina met metadata en bestanden, OCR-wachtrij, inbox, prullenbak en beheerpagina.
