# Ordner

## Wat is Ordner

Vroeger gingen afschriften, nota's, bonnetjes en andere belangrijke papieren in een ordner. Een map per jaar, een tabblad per onderwerp, en je wist dat alles er lag als je het nodig had. Ordner brengt die eenvoud terug: een digitale ordner voor je documenten.

Je uploadt een pdf of foto, controleert de titel en datum die Ordner uit de tekst heeft gelezen, en Ordner bewaart het document als gewone bestanden in `/share/ordner`. Elk document krijgt een eigen map met het origineel erin. De tekst van pdf's en foto's wordt gelezen (OCR) en als gewoon tekstbestand ernaast gezet, zodat je later op elk woord kunt zoeken. De gegevens over het document staan in één leesbaar `meta.md`.

Kernprincipe: **de bestanden op schijf zijn de waarheid**. Er is geen database, niets om te ontcijferen. Alles wat Ordner weet staat in mappen en tekstbestanden die je ook zonder de add-on kunt lezen, kopiëren en back-uppen, bijvoorbeeld via Samba of de Verkenner.

## Mapstructuur

Per document één map, gegroepeerd per jaar. De mapnaam is de documentdatum plus een korte versie van de titel:

```
/share/ordner/
  _inbox/                          # hier bestanden droppen om ze automatisch op te nemen
    .tekst/                        # de gelezen tekst van bestanden die nog in de inbox wachten
  _prullenbak/                     # verwijderde documenten
  2026/
    2026-03-01_woz-beschikking-2026/
      meta.md                      # titel, datum, tags, bestandslijst, notities
      beschikking.pdf              # het origineel, ongewijzigd
      beschikking.pdf.txt          # de gelezen tekst van beschikking.pdf
      foto.heic
      foto.heic.txt
```

De mapnaam wordt bij aanmaak bepaald en daarna **nooit meer hernoemd**, ook niet als je later de titel of datum aanpast. Zo blijven links, back-ups en Samba-snelkoppelingen geldig. De actuele titel en datum staan altijd in `meta.md`.

Bij elk origineel (`factuur.pdf`, `bon.jpg`) hoort een tekstbestand met dezelfde naam plus `.txt` (`factuur.pdf.txt`). Dat is de tekst waarop gezocht wordt. Bestanden met een andere extensie (bijvoorbeeld `.docx` of `.eml`) worden wel bewaard en in de bestandslijst opgenomen, maar er wordt geen tekst uit gelezen.

## `meta.md` uitgelegd

```markdown
---
titel: WOZ-beschikking 2026
omschrijving: Gemeente, waarde peildatum 1-1-2025
documentdatum: 2026-03-01
uploaddatum: '2026-09-03T14:12'
tags: [woz, gemeente]
bestanden: [beschikking.pdf, foto.heic]
sha256:
  beschikking.pdf: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
  foto.heic: 2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae
ocr: done
datumbron: gebruiker
---
Eventuele eigen notities. Deze tekst wordt meegezocht.
```

| Veld | Betekenis |
|---|---|
| `titel` | Verplicht. Wordt getoond in de lijst en meegezocht. |
| `omschrijving` | Korte toelichting, één regel. Meegezocht. |
| `documentdatum` | Verplicht, `JJJJ-MM-DD`. Datum van het document zelf, niet van het uploaden. Bepaalt de sortering. |
| `uploaddatum` | Wanneer het document is aangemaakt. Informatief. |
| `tags` | Lijst met trefwoorden. Meegezocht. |
| `bestanden` | De originelen in deze map. Wordt door Ordner bijgehouden; bestanden die je via Samba toevoegt worden bij de volgende verversing opgenomen. |
| `sha256` | Per bestand een vingerafdruk van de inhoud, waarmee Ordner dubbele bestanden herkent (zie "Dubbele bestanden"). Wordt door Ordner bijgehouden; ontbreekt hij, dan vult de volgende verversing hem aan. |
| `ocr` | `pending` (tekst wordt nog gelezen), `done` (klaar) of `failed` (mislukt, zie hieronder). |
| `datumbron` | Waar de documentdatum vandaan komt: `gebruiker` (zelf ingevuld of later gewijzigd), `tekst` (uit het document gelezen) of `upload` (geen datum gevonden, dag van uploaden). Zie "Documentdatum". |

Alles onder de tweede `---` is vrije tekst voor eigen notities en wordt meegezocht.

Je mag `meta.md` zelf bewerken in een teksteditor. Houd de drie streepjes en de veldnamen intact. Een map zonder `meta.md` krijgt er bij de volgende verversing automatisch een, met de mapnaam als titel.

## Uploaden

Uploaden gaat in twee stappen.

1. **Bestanden kiezen.** Kies een of meer pdf's of foto's; samen vormen ze één document. Minstens één bestand is verplicht. Na "Verder" leest Ordner de tekst van de bestanden (bij foto's en scans kan dat even duren; de pagina meldt "tekst lezen…").
2. **Gegevens controleren.** Je ziet de gekozen bestanden en een formulier dat al is ingevuld: de titel (de naam van het bedrijf of de instantie uit de tekst; leeg als er geen herkenbare naam in staat), de documentdatum (uit de tekst, anders vandaag; een label eronder zegt welke van de twee), en de tags (het documenttype, zoals `factuur`). De omschrijving is altijd leeg. Pas aan wat niet klopt en kies **Opslaan**. Let op de datum en de titel: samen bepalen ze de mapnaam, en die verandert daarna niet meer.

Tot je op Opslaan drukt wordt er niets bewaard. **Annuleren** gooit de gekozen bestanden weg; het tabblad sluiten of de add-on herstarten heeft hetzelfde effect. Een niet afgemaakte upload verloopt na een uur; kom je daarna terug, dan vraagt Ordner je de bestanden opnieuw te kiezen. Na Opslaan kom je op de documentpagina met de bevestiging "Opgeslagen".

Een bestand toevoegen aan een bestaand document doe je op de documentpagina.

Staat een gekozen bestand al in het archief, dan wordt de upload geweigerd; zie "Dubbele bestanden".

## Dubbele bestanden

Ordner voorkomt dat hetzelfde bestand twee keer in het archief komt. Elk bestand krijgt bij het opslaan een vingerafdruk van zijn inhoud (SHA-256, in `meta.md` onder `sha256:`). Bij uploaden, bij "Bestand toevoegen" op de documentpagina en in de inbox vergelijkt Ordner de vingerafdruk met alle documenten:

- **Uploaden.** Is een gekozen bestand al bekend, dan wordt er niets opgeslagen. Je ziet per bestand in welk document het al staat, met een link ernaartoe. Kies je meerdere bestanden en is er één al bekend, dan wordt de hele upload geweigerd; kies de overige bestanden daarna opnieuw.
- **Bestand toevoegen.** Zelfde regel: één bekend bestand, en er wordt niets toegevoegd. Dat geldt ook voor een bestand dat al in ditzelfde document zit.
- **Inbox.** Een bekend bestand wordt niet opgenomen maar verplaatst naar `_inbox/_dubbel/`; het log noemt het document waar het al staat.

Goed om te weten:

- Alleen **exact gelijke** bestanden worden herkend, ongeacht de bestandsnaam. Dezelfde brief nog een keer scannen of fotograferen geeft een ander bestand en wordt niet herkend. Sommige portalen zetten bij elke download een datum in de pdf; ook dan verschilt het bestand.
- Een document in de **prullenbak** telt niet mee. Heb je iets weggegooid, dan mag je het opnieuw uploaden.
- Bestaande documenten van vóór deze functie krijgen hun vingerafdrukken vanzelf bij de eerste verversing (bij het starten van de add-on of via de beheerpagina). Vervang je buiten Ordner om een bestand door een ander bestand met dezelfde naam, dan blijft de oude vingerafdruk staan.

## Bestanden bekijken

Op de documentpagina staan de bestanden van het document. Foto's zie je meteen; een pdf wordt op een breed scherm ook op de pagina zelf getoond. Met **Open** bij een bestand krijg je het op een eigen pagina, groot en met een terugknop naar het document, ook in de Home Assistant-app op de telefoon. Kan de browser een pdf niet zelf tonen (sommige Android-browsers), dan staat onder het lege vlak een link om het bestand los te openen of te downloaden.

## Documentdatum

In de tweede stap van het uploaden staat de documentdatum al ingevuld. Ordner leest daarvoor de tekst van het document en zoekt daarin naar een datum achter een van deze woorden, in deze volgorde: **factuurdatum**, **notadatum**, **orderdatum**, **dagtekening**, **datum**. Het woord mag met of zonder spatie geschreven zijn ("factuur datum") en er mag een dubbele punt achter staan. De datum staat direct achter het woord op dezelfde regel, of, zoals in tabellen op facturen, in dezelfde kolom op de regel eronder; "vervaldatum" of "betaaldatum" tellen niet mee. Herkende notaties: `12-03-2024`, `12/03/2024`, `12.03.2024`, `2024-03-12`, `12 maart 2024`, `12 mrt 2024` en een tweecijferig jaar. Staat er geen bruikbare datum in, dan wordt het de dag van uploaden.

De gevonden datum bepaalt ook de mapnaam, dus een oude factuur die je nu inscant komt in de juiste jaarmap terecht. Laat je de voorgestelde datum staan, dan onthoudt Ordner dat hij uit de tekst komt (of van de dag van uploaden, als er niets gevonden is); wijzig je hem, dan geldt hij als door jou ingevuld.

Op de documentpagina zie je achter de datum een label **datum uit tekst** of **datum van upload** als de datum niet door jou is ingevuld. Wijzig je de datum zelf, dan verdwijnt het label en wordt hij nooit meer automatisch aangepast. Documenten uit de inbox krijgen altijd op deze manier hun datum.

## Zoeken

Het startscherm toont de 20 nieuwste documenten. Staan er meer in het archief, dan zegt een regel onder de lijst hoeveel er in totaal zijn; oudere documenten vind je via het zoekveld.

Zoeken werkt op alle woorden tegelijk (elk woord moet voorkomen), zonder onderscheid in hoofdletters, over titel, omschrijving, tags, documentdatum, notities en de gelezen tekst van de bestanden. Een datum of jaartal (`2024`, `2024-03`) telt als zoekwoord, dus `energie 2024` vindt alleen energiedocumenten uit 2024. Bij meer dan 50 treffers worden de 50 nieuwste getoond; de kop noemt het echte aantal en onder de lijst staat een link **Toon alle** voor de volledige lijst. Meestal is een extra zoekwoord sneller.

Tags staan als labels in de resultatenlijst en op de documentpagina. Klik op een label om alle documenten met die tag te zien; de tag komt dan in het zoekveld in plaats van je vorige zoekopdracht. Een tag met een spatie (bijvoorbeeld `gemeente amsterdam`) zoekt op beide woorden.

Open je een document vanuit de resultaten, dan staat bovenaan de documentpagina **Terug naar zoekresultaten**; die brengt je terug bij dezelfde zoekopdracht, ook na opslaan of verwijderen. Vanuit het startscherm heet die link **Terug naar overzicht**.

## Inbox

Bestanden die je in `/share/ordner/_inbox/` zet worden automatisch opgenomen zodra Ordner weet van wie ze zijn. Elke vijf seconden kijkt Ordner of er een bestand ligt dat niet meer groeit (twee keer achter elkaar dezelfde grootte). Dan leest het de tekst en beoordeelt het bestand:

- staat het bestand al ergens in het archief, dan wordt het niet opgenomen maar verplaatst naar `_inbox/_dubbel/` (zie "Dubbele bestanden");
- herkent Ordner in de tekst de naam van het bedrijf of de instantie (zie "Titel en tags uit de tekst"), dan wordt er direct een document van gemaakt: die naam als titel, het documenttype als tag, de datum uit de tekst (anders vandaag, zie "Documentdatum"). Het bestand verhuist naar de nieuwe documentmap, samen met de al gelezen tekst;
- is er geen herkenbare afzender, dan blijft het bestand in de inbox **wachten op een titel**. Ordner raadt geen titel meer uit de bestandsnaam, want de mapnaam wordt daarna nooit meer aangepast.

**Wachtende bestanden een titel geven.** Het startscherm meldt hoeveel bestanden wachten, met een link naar de pagina **Inbox** (ook bereikbaar via de beheerpagina). Daar staat per bestand de naam, de grootte en sinds wanneer het wacht, met een knop **Opnemen**. Die brengt je naar het bekende gegevensscherm van de upload: datum en tags staan al ingevuld uit de tekst, jij typt de titel en kiest **Opslaan**. Het bestand wordt dan een document en verdwijnt uit de inbox. **Terug naar inbox** laat het liggen. Zolang je op dat scherm bezig bent, blijft Ordner van het bestand af (een uur lang; daarna wordt het weer gewoon beoordeeld).

**Leren van je titels.** Zodra een titel in het archief staat, kijkt Ordner opnieuw naar alle wachtende bestanden. Staat die naam letterlijk in de tekst van een ander wachtend bestand, dan wordt dat automatisch opgenomen. Laad je een oud archief met tien brieven van dezelfde onbekende afzender in de inbox, dan geef je er één een titel en volgen de andere negen vanzelf.

**Eén keer lezen.** De tekst van een wachtend bestand staat in `_inbox/.tekst/<bestandsnaam>.txt`. Daardoor draait de OCR per bestand maar één keer, ook na een herstart van de add-on of als het bestand opnieuw beoordeeld wordt. Vervang je een bestand in de inbox door een nieuwere versie, dan wordt het opnieuw gelezen. Bij opname gaat de tekst mee als `.txt` naast het origineel; het bestandje in `.tekst/` verdwijnt dan. Een bestand dat niet gelezen kan worden (beschadigd, of geen pdf of foto) wacht ook op jou; na opname probeert Ordner de tekst alsnog te lezen zoals bij een gewone upload.

Handig voor scanners, e-mailregels of een gedeelde map op de telefoon. Controleer na een automatische opname de titel, tags en datum op de documentpagina; de naam uit de tekst is een gok, en bij een bankafschrift kan dat je eigen naam zijn.

## Titel en tags uit de tekst

Ordner probeert uit de gelezen tekst af te leiden van wie een document komt en wat voor document het is. Bij uploaden staan die als voorstel in het formulier van de tweede stap (onder de titel staat dan "voorstel uit het document"); de inbox gebruikt ze direct.

De **titel** is alleen de naam van de afzender, dus "Eneco Services B.V." of "Gemeente Amsterdam", nooit het soort document of een jaartal. Ordner kijkt in deze volgorde en neemt het eerste wat lukt:

1. Een titel die je al eerder in het archief hebt gebruikt en die letterlijk in de tekst voorkomt. Heb je eenmaal "Eneco" getypt, dan wordt dat bij de volgende Eneco-factuur herkend.
2. De naam achter "t.n.v." of "ten name van", zoals bij de betaalgegevens op een factuur.
3. De eerste regel met een rechtsvorm (B.V., N.V., VOF, U.A.) of een instantiewoord (Gemeente, Stichting, Vereniging, Waterschap, Provincie, Coöperatie, Ministerie, Belastingdienst, Bank, Verzekeraar, Ziekenhuis, Universiteit, Hogeschool).
4. Bij een korte tekst, zoals een kassabon, de eerste regel met tekst.

Bij een langere brief zonder zo'n aanknopingspunt blijft de titel leeg, want de bovenste regel van een brief is meestal de ontvanger. Bij uploaden is dat een leeg veld dat je zelf invult; in de inbox blijft het bestand wachten tot je het via de inboxpagina een titel geeft (zie "Inbox"). Hoofdletters blijven zoals ze in de tekst staan.

De **tags** zijn de documenttypen die als kopje in de tekst staan: factuur, creditnota, offerte, polis, beschikking, nota, bon (ook kassabon), herinnering (ook betalingsherinnering), aanmaning, contract, overeenkomst, aanslag, jaaroverzicht, jaarafrekening en garantie (garantiebewijs). Het woord moet een regel of kolom beginnen ("Factuur nr. 123" telt, "Factuurdatum" of "deze factuur" niet).

De omschrijving wordt nooit automatisch ingevuld. Klopt een voorstel niet, pas het dan aan vóór het opslaan, of later op de documentpagina; de mapnaam verandert door een latere wijziging niet.

## Prullenbak

"Verwijderen" op de documentpagina verplaatst de hele documentmap naar `/share/ordner/_prullenbak/`. Er wordt niets echt gewist. Terugzetten doe je door de map met Samba of de Verkenner terug te verplaatsen naar de juiste jaarmap en daarna "Cache verversen" te gebruiken op de beheerpagina. Definitief opruimen doe je door de map uit `_prullenbak` te verwijderen.

## Beheerpagina

De beheerpagina toont tellingen (totaal, OCR klaar, wacht, mislukt), hoeveel inboxbestanden op een titel wachten (met een link naar de inboxpagina), wat er nu in de wachtrij staat en het rapport van de laatste verversing.

De knop **Cache verversen en ontbrekende tekst extraheren** doet in één keer:

1. alle documentmappen opnieuw inlezen in het geheugen;
2. de bestandslijst in `meta.md` gelijktrekken met wat er echt in de map staat;
3. voor elk bestand zonder vingerafdruk de `sha256` berekenen (zie "Dubbele bestanden");
4. voor elk pdf- of afbeeldingsbestand zonder `.txt` de tekst laten lezen;
5. `meta.md` aanmaken voor mappen die er geen hebben;
6. de inbox verwerken (zie "Inbox"); het rapport noemt ook hoeveel bestanden daarna nog op een titel wachten.

Dit gebeurt automatisch bij het starten van de add-on en daarna elke `reconcile_interval` seconden (standaard vijf minuten). Gebruik de knop als je iets via Samba hebt gewijzigd en niet wilt wachten.

## Opties

| Optie | Standaard | Betekenis |
|---|---|---|
| `ocr_talen` | `nld+eng` | Talen voor Tesseract, gescheiden door `+`. Alleen `nld` en `eng` zijn in de add-on geïnstalleerd. |
| `ocr_parallel` | `2` | Hoeveel bestanden tegelijk gelezen worden. Verhogen op een snelle machine, verlagen als de add-on te veel geheugen gebruikt. |
| `reconcile_interval` | `300` | Seconden tussen automatische verversingen. |

Na een wijziging de add-on herstarten.

## Als OCR faalt

Krijgt een document de status `failed`, dan is de tekst van minstens één bestand niet gelezen. Oorzaken: een beschadigde of met wachtwoord beveiligde pdf, een te grote afbeelding, of een time-out (tien minuten per bestand). Details staan in het add-on-log.

Wat je kunt doen:

- **OCR opnieuw** op de documentpagina: verwijdert de bestaande `.txt`-bestanden van dat document, zet de status op `pending` en plaatst alle bestanden opnieuw in de wachtrij.
- **`.txt` handmatig plaatsen**: zet zelf een tekstbestand naast het origineel met de naam `<bestandsnaam>.txt` (bijvoorbeeld `factuur.pdf.txt`). Bij de volgende verversing wordt het opgepikt en telt het document als `done`. Zo kun je ook tekst toevoegen voor bestanden die Ordner niet zelf kan lezen.
- **Status resetten**: `ocr: failed` in `meta.md` wijzigen in `ocr: pending` heeft hetzelfde effect als "OCR opnieuw", maar dan zonder de bestaande `.txt`-bestanden te verwijderen.

Een document met status `failed` wordt door de automatische verversing met rust gelaten, zodat een kapot bestand niet elke vijf minuten opnieuw geprobeerd wordt.

## Backup

Het hele archief staat in `/share/ordner`. De map `/share` zit standaard in een Home Assistant-backup, dus Ordner heeft geen eigen back-upmechanisme nodig. Omdat het gewone bestanden zijn, kun je de map ook los kopiëren of met een ander programma synchroniseren. De add-on zelf bewaart niets buiten deze map.
