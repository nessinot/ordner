# Changelog

Home Assistant toont dit bestand onder het tabblad **Changelog** van de add-on. Nieuwste versie bovenaan; de bovenste kop moet gelijk zijn aan `version` in `config.yaml` (dat controleert `tests/test_addon_config.py`).

## 0.18.1 (2026-09-12)

- **Afzender via e-mailadres of website ook met rechtsvorm.** Staat er `info@voorbeeld.nl` in de tekst en verderop "Voorbeeld B.V.", dan wordt de titel nu "Voorbeeld". Voorheen matchte die regel niet door de rechtsvorm erachter, en kon een kopregel als "Algemene voorwaarden Voorbeeld B.V." de titel worden. Bestaande documenten veranderen niet.

## 0.18.0 (2026-09-12)

- **Titelvoorstel zonder rechtsvorm.** Herkent Ordner de afzender aan een rechtsvorm (B.V., N.V., VOF, U.A.) of aan de naam achter "t.n.v.", dan stelt het nu alleen de naam voor: "Voorbeeldshop" in plaats van "Voorbeeldshop B.V.". Dat geldt voor de inbox en voor het uploadformulier. Bestaande documenten veranderen niet. Let op: een titel die je al eerder mét rechtsvorm hebt opgeslagen wordt bij de volgende factuur van dezelfde afzender opnieuw herkend, inclusief die rechtsvorm; pas zo'n titel één keer aan en de volgende krijgt de korte naam.

## 0.17.1 (2026-09-12)

- **Eén keer Terug naar de inbox.** De link onderin het gegevensscherm van een inboxbestand is weg; de terug-link bovenin volstaat. Onderin staan nu alleen Opslaan en Verwijderen.

## 0.17.0 (2026-09-12)

- **Terug naar de inbox is een gewone link.** Op het gegevensscherm van een inboxbestand staat nu bovenin dezelfde terug-link als op de andere pagina's, en onderin een link in plaats van een knop. Het bestand blijft intussen gewoon in de inboxlijst staan; voorheen verdween het daar een uur uit zodra je het opende.
- **Inboxbestand verwijderen.** Op datzelfde scherm staat een knop **Verwijderen** voor een bestand dat je helemaal niet in de ordner wilt. Na een bevestiging wordt het definitief van schijf gewist, samen met de gelezen tekst; het komt niet in de prullenbak.

## 0.16.1 (2026-09-12)

- **Geen voorbeeldtekst meer in de velden Titel en Tags.** Op het gegevensscherm van een nieuw document stond in een leeg titel- of tagveld een grijze voorbeeldtekst ("factuur, energie"). Die leek op een ingevulde waarde, terwijl de andere velden op dat scherm wél echt voorgevuld zijn. Lege velden zijn nu gewoon leeg; de uitleg "komma-gescheiden" bij de tags blijft staan.

## 0.16.0 (2026-09-12)

- **Inboxpagina als gewone lijst.** De knoppen Bekijken en Opnemen zijn weg. Klik op de naam van een wachtend bestand en je komt op het gegevensscherm, met het bestand in beeld, om het een titel te geven. Terug naar inbox laat het bestand liggen, zoals voorheen.
- **Titelvoorstel strenger.** Ordner koos te vaak een onzinnige titel, zoals de bankregel uit de voettekst van een factuur of de bovenste regel van een korte tekst. Beide regels zijn geschrapt: bij twijfel blijft de titel leeg en wacht het bestand in de inbox op jou.
- **Afzender via e-mailadres of website.** Staat er een e-mailadres of website van de afzender in de tekst, dan zoekt Ordner de bijbehorende naam in het document (`info@voorbeeld-installaties.nl` → "Voorbeeld Installaties").

## 0.15.0 (2026-09-10)

- **Inboxbestand bekijken.** Op de inboxpagina staat bij elk bestand dat op een titel wacht een knop Bekijken, zodat je ziet wat het is voordat je het opneemt. Het bestand blijft gewoon in de inbox staan.
- **Bestanden zichtbaar bij het opslaan.** Op het scherm met de gegevens van een nieuw document (na Opnemen uit de inbox, en ook na een gewone upload) staat elk bestand nu in beeld: pdf's en foto's inline, met een knop Open voor een volledig scherm. Zo kun je de titel bepalen met het document ernaast in plaats van alleen de bestandsnaam.

## 0.14.0 (2026-09-10)

- Een document in de prullenbak is weer te openen: klik op de prullenbakpagina op de titel en je ziet de bestanden, de gegevens en de notities, net als op de gewone documentpagina. Bewerken kan daar niet; daarvoor zet je het document eerst terug.
- **Terugzetten**: met één knop op die pagina gaat het document terug naar zijn jaarmap en is het meteen weer te doorzoeken. Is een van de bestanden inmiddels al in een ander document opgeslagen, dan weigert Ordner het terugzetten en laat zien in welk document het bestand staat.
- **Ongedaan maken**: direct na "Verwijderen" staat in de groene melding een knop Ongedaan maken, zodat een misklik meteen te herstellen is.
- De hint om een map via Samba terug te zetten is van de prullenbakpagina verdwenen; dat kan nog steeds, maar hoeft niet meer.

## 0.13.2 (2026-09-10)

- Het icoon van Ordner in de zijbalk van Home Assistant is nu een boekenplank (`mdi:bookshelf`) in plaats van een archiefdoos, passend bij het nieuwe add-on-icoon. Verandert het icoon niet direct, herstart dan de add-on of herlaad de pagina.

## 0.13.1 (2026-09-10)

- De add-on heeft nu een eigen icoon en logo: drie ordners op een plank. Je ziet het icoon in de lijst met add-ons en het logo bovenaan de pagina van de add-on. Aan de app zelf verandert niets.

## 0.13.0 (2026-09-06)

- Nieuwe pagina **Prullenbak**, bereikbaar via de beheerpagina. Je ziet wat er in `_prullenbak/` staat: per weggegooid document de titel, de mapnaam (zoals je die via Samba terugziet), de documentdatum, het aantal bestanden en de grootte. Tot nu toe was een verwijderd document in de app onzichtbaar en kon je alleen via Samba opruimen.
- Per item een knop **Definitief verwijderen** en bovenaan een knop **Prullenbak legen**. Beide vragen eerst om bevestiging. Dit kan niet ongedaan gemaakt worden; de map wordt echt van schijf gehaald. Terugzetten werkt zoals voorheen: de map met Samba of de Verkenner terug naar de jaarmap en daarna **Cache verversen**.
- De beheerpagina heeft een tabel **Prullenbak** met het aantal items (live bijgewerkt, met een link naar de pagina) en de totale grootte.
- Ordner ruimt de prullenbak nooit vanzelf op; legen doe je zelf.

## 0.12.1 (2026-09-05)

- Het eerste tabblad heet **Documenten** in plaats van **Zoeken**. Het is de pagina met je documenten; zoeken doe je in het veld bovenaan. De link bovenaan de documentpagina heet daarom **Terug naar documenten** (na een zoekopdracht nog steeds **Terug naar zoekresultaten**).
- In de teksten heet de verzameling documenten nu overal "de ordner" in plaats van "het archief", passend bij de naam van de app.

## 0.12.0 (2026-09-05)

- De beheerpagina heeft een eigen tabel **Inbox** met drie tellers: hoeveel bestanden er in `_inbox/` liggen, hoeveel daarvan op een titel wachten (met een link naar de inboxpagina) en hoeveel er als dubbel in `_inbox/_dubbel/` zijn gezet. Tot nu toe telde alleen het eindstation mee: een bestand dat net was neergezet en nog beoordeeld of gelezen werd, stond nergens, en dubbelen verdwenen stil met alleen een regel in het log.
- De tellers in de tabel **Documenten** zeggen nu wat ze tellen. "OCR wacht" heet "OCR nog te doen" (documenten waarvan nog niet alle tekst gelezen is) en "In wachtrij" heet "OCR-wachtrij (bestanden)" (losse bestanden die de tekstlezer nog moet doen). Onder de tabel staat in één regel wat de rijen tellen.
- Alle tellers op de beheerpagina worden live bijgewerkt, ook die van de inbox.

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

- Documenten uit de inbox krijgen hun titel uit de tekst: de naam van het bedrijf of de instantie (bijvoorbeeld "Voltaria Services B.V." of "Gemeente Voorbeeldstad"). Staat er geen herkenbare naam in, dan blijft de bestandsnaam de titel. Titels die je al eerder in het archief gebruikt hebt, worden het eerst herkend.
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
