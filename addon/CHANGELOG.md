# Changelog

Home Assistant toont dit bestand onder het tabblad **Changelog** van de add-on. Nieuwste versie bovenaan; de bovenste kop moet gelijk zijn aan `version` in `config.yaml` (dat controleert `tests/test_addon_config.py`).

## 0.11.0 (2026-09-05)

- Een bestand in de inbox waarvan Ordner de afzender niet in de tekst herkent, krijgt niet langer de bestandsnaam als titel. Het blijft in de inbox wachten tot jij het een titel geeft. Zo krijg je geen mappen meer met namen als `scan_0001` die daarna nooit meer veranderen, bijvoorbeeld bij het in één keer inladen van een oud archief.
- Nieuwe pagina **Inbox** (via de regel op het startscherm of de beheerpagina) toont de wachtende bestanden. Met **Opnemen** kom je in het bekende gegevensscherm van de upload, met datum en tags al ingevuld; je typt alleen de titel. **Terug naar inbox** laat het bestand liggen.
- Zodra een titel in het archief staat, herkent Ordner de andere wachtende bestanden van dezelfde afzender vanzelf en neemt ze automatisch op. Tien brieven van dezelfde onbekende afzender: één keer een titel typen.
- Elk inboxbestand wordt maar één keer gelezen (OCR). De gelezen tekst staat in `_inbox/.tekst/`, dus ook na een herstart of een nieuwe beoordeling hoeft er niets opnieuw. Bij opname verhuist de tekst mee naar de documentmap. Kan een bestand niet gelezen worden (of is het geen pdf of foto), dan wacht het ook op jou.
- Het startscherm meldt hoeveel bestanden in de inbox op een titel wachten; de beheerpagina toont hetzelfde aantal, ook in het rapport van de laatste verversing.

## 0.10.1 (2026-09-05)

- Ordner herkent nu ook "Afdrukdatum" als documentdatum, bijvoorbeeld op jaaropgaven en polisbladen. Staat er ook een sterker datumwoord in de tekst (zoals "Datum" of "Factuurdatum"), dan wint dat.

## 0.10.0 (2026-09-05)

- Ordner herkent nu bestanden die al in het archief staan. Upload je een bestand dat er al is (bijvoorbeeld dezelfde factuur voor de tweede keer gedownload), dan wordt de upload geweigerd en zie je in welk document het al staat, met een link ernaartoe. Hetzelfde geldt voor "Bestand toevoegen" op de documentpagina. Kies je meerdere bestanden tegelijk en is er één al bekend, dan wordt er niets opgeslagen; kies de overige bestanden dan opnieuw.
- Herkenning werkt op de inhoud van het bestand (een SHA-256-vingerafdruk), niet op de naam. Elk bestand krijgt zijn vingerafdruk in `meta.md` onder `sha256:`. Bestaande documenten krijgen hem bij de eerste verversing na de update vanzelf; daarna hoef je niets te doen.
- Een bestand in de inbox dat al in het archief staat wordt niet opnieuw opgenomen maar verplaatst naar `_inbox/_dubbel/`, met een melding in het log.
- Alleen exact gelijke bestanden worden herkend. Dezelfde brief twee keer scannen levert twee verschillende bestanden op en wordt niet als dubbel gezien. Een document dat in de prullenbak ligt telt niet mee: opnieuw uploaden mag.
- De beheerpagina toont in het rapport hoeveel vingerafdrukken de laatste verversing heeft berekend.

## 0.9.2 (2026-09-05)

- De knop "Open" bij een bestand toont het bestand nu op een eigen pagina binnen Ordner, met de gewone kop en een terugknop naar het document. Voorheen vulde het bestand op de telefoon het hele scherm en was er geen weg terug. Bij een pdf die de browser niet kan tonen staat er een link om hem los te openen.

## 0.9.1 (2026-09-05)

- De knop "Open" bij een bestand opent het bestand nu in hetzelfde venster. In de Home Assistant-app sprong die link naar een externe browser, die geen toegang tot de add-on heeft en dan een foutmelding (404) gaf, vooral op de telefoon. Met de terugknop kom je weer bij het document.

## 0.9.0 (2026-09-04)

- Uploaden gaat nu in twee stappen. Eerst kies je alleen de bestanden; Ordner leest de tekst en vult daarna de titel (de naam van het bedrijf of de instantie), de documentdatum en de tags (het documenttype) voor je in. In de tweede stap controleer je die gegevens, past ze zo nodig aan en kiest Opslaan. Zo hoef je niet meer over te typen wat al in het document staat, en zie je vóór het opslaan welke datum en titel de mapnaam krijgt.
- Tot je op Opslaan drukt wordt er niets bewaard: Annuleren, het tabblad sluiten of een herstart van de add-on laat geen half document achter. Een niet afgemaakte upload verloopt na een uur; dan kies je de bestanden gewoon opnieuw.
- Een document aanmaken zonder bestanden kan via het uploadformulier niet meer; minstens één bestand is verplicht.
- De bevestiging "Opgeslagen" is duidelijker (vinkje, opvallender kader).
- Een onleesbaar `.heic`-bestand laat de upload niet meer vastlopen; het document krijgt dan de OCR-status `failed`, zoals bij andere onleesbare bestanden.

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
