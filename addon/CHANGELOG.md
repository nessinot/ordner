# Changelog

Home Assistant toont dit bestand onder het tabblad **Changelog** van de add-on. Nieuwste versie bovenaan; de bovenste kop moet gelijk zijn aan `version` in `config.yaml` (dat controleert `tests/test_addon_config.py`).

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
