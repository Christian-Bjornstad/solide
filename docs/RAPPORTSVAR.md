# Tekster i rapportcellene

Ved treff vises databasens egen vurdering, for eksempel `Likely Oncogenic`,
`Unknown Oncogenic Effect`, `Pathogenic` eller `Benign`. Disse tekstene oversettes
ikke. Databasene kan endre og utvide vurderingene sine; dette er ikke en fast liste.
OncoKBs eget proteinnavn kan være forskjellig fra TSV-transkriptets navn når samme
genomiske variant er bekreftet. Originale variantopplysninger beholdes.
En feil ved bildetaking sletter ikke det innleste OncoKB-svaret fra Kilder.
Uavhengig bekreftede klassifikasjoner kan fortsatt vises med «Bilde mangler»;
ellers viser oversikten «Bilde mangler» frem til kildebildet kan hentes på nytt.

## Gjennomført søk og kildevurderinger

| Celleinnhold | Betydning |
|---|---|
| Databasens vurdering | Treff på den søkte varianten. |
| Treff | Kilden har et treff uten en egen klassifikasjon. |
| Ingen treff | Søket ble gjennomført uten et godkjent treff. |
| Ingen treff på eksakt GRCh37-variant | ClinVar-kandidater samsvarte ikke med de søkte allelene. |
| OncoKB har ingen geninformasjon | OncoKB oppga at det mangler informasjon om genet. |
| Ingen treff for COSM… / COSV… | COSMIC fant ingen post for denne ID-en. |
| COSM… / COSV… | COSMIC-ID for et godkjent treff. |
| Uendret | Mutalyzer bekreftet variantnavnet uten å endre det. |
| Normalisert | Mutalyzer bekreftet en annen skrivemåte for samme sekvensendring. |
| Maks. delta 0.xxx | Høyeste returnerte SpliceAI-deltaskår. |
| Arvelig: … / Somatisk: … / Onkogenisitet: … | ClinVars separate, samlede klassifikasjoner, vist på hver sin linje når flere finnes. Underposters eller enkeltinnsenderes vurderinger erstatter ikke den samlede vurderingen. |
| Databasens vurdering + Bilde mangler | Kildesvaret er uavhengig bekreftet, men bildet mangler. Teksten vises på separate linjer. |

## Ikke kjørt eller ikke aktuelt

| Celleinnhold | Betydning |
|---|---|
| Tom celle | Ingen registrert søking i denne databasen. |
| Ikke kjørt | SpliceAI er ikke aktuelt etter utvalgsregelen for intronvarianter. |
| COSMIC-ID mangler | Raden mangler COSM-/COSV-ID. Dette er ikke et gjennomført søk uten treff. |
| Ikke aktuelt | Kilden gjelder ikke den valgte varianten. |
| Søket er utsatt | Kilden har utsatt oppslaget. |
| Manuelt søk kreves | Kilden krever manuelt oppslag. |

## Tilgang og nettverk

| Celleinnhold | Betydning |
|---|---|
| Innlogging kreves | Ingen bekreftet innlogging hos kilden. |
| Innlogging mislyktes | Innloggingen ble ikke godkjent. |
| Bekreftelse mangler – åpne kilden | En nødvendig bekreftelse hos kilden mangler. |
| Edge-profil i bruk – lukk innloggingsvinduet | En annen prosess bruker kildens dedikerte Edge-profil. |
| Edge blokkert av IT-policy | Maskinens policy tillater ikke den nødvendige nettleserautomatiseringen. |
| Proxy-tilkobling mislyktes | Tilkoblingen gjennom proxy feilet. |
| Sertifikatet kunne ikke bekreftes | HTTPS-sertifikatet kunne ikke valideres. |
| Nettverkstilkobling mislyktes | Kilden kunne ikke nås over nettverket. |
| Tidsavbrudd – prøv igjen | Kilden svarte ikke innen tidsgrensen. |
| Kilden svarte med HTTP … | Den faktiske HTTP-feilkoden vises. |
| Tilgang avvist – kontroller innlogging/lisens | Kilden avviste tilgangen. |
| API-nøkkel mangler | Kilden krever en API-nøkkel. |
| For mange forespørsler – vent og prøv igjen | Kildens grense for søk er nådd. |
| Kvoten er brukt opp | Kildens tilgjengelige kvote er brukt. |

## Variant, lesing av nettsiden og bilder

| Celleinnhold | Betydning |
|---|---|
| Feil variant – treff utelatt | Returnert variant samsvarer ikke med søket. Klassifikasjon og bilde brukes ikke som treff. |
| Variantidentitet ikke bekreftet – treff utelatt | Ingen av oppslagene bekreftet varianten. |
| Transkript avviker – genomisk treff ikke bekreftet | Et transkriptavvik kunne ikke avklares med genomisk oppslag. |
| Flere mulige treff – ingen valgt | Oppslaget ga flere mulige resultater uten ett entydig treff. |
| Variantnavn og kildealleler avviker | Mutalyzer-navnet og de opprinnelige genomiske allelene beskriver ikke samme endring. |
| Variantnavnet kunne ikke bekreftes | Mutalyzer-kontrollen bekreftet ikke variantnavnet mot de opprinnelige allelene. |
| Endret variantnavn må godkjennes | Et endret navn mangler nødvendig bekreftelse. |
| Flere gener/transkripter – velg annotasjon | Raden har flere uavklarte annotasjoner. |
| Annotasjon uavklart – søket er ikke kjørt | Valgt annotasjon må avklares før oppslaget. |
| Referansegenom må bekreftes som GRCh37 | Referansegenomet er ikke bekreftet. |
| Variantgrunnlaget må avklares før søk | Nødvendig variantavklaring er ikke fullført. |
| Ugyldig søkegrunnlag | Kilden kan ikke bruke de oppgitte søkedataene. |
| Søketypen støttes ikke | Kilden støtter ikke denne typen oppslag. |
| Nytt søk kreves – variantgrunnlaget må avklares | En tidligere kontroll må gjentas. |
| Utdatert | Variant, vev eller utvalg er endret etter at svaret ble hentet. |
| Bilde mangler | Et gyldig kildebilde mangler. Et ubekreftet kildesvar løftes ikke frem som klassifikasjon. |
| Ufullstendig bilde – prøv igjen | Bildet dekker ikke hele det nødvendige innholdet. |
| Skjermbildet kunne ikke tas – prøv igjen | Bildetakingen feilet. |
| Nettsiden er endret – resultatet kunne ikke leses | Kildens sideoppsett kunne ikke leses som forventet. |
| Resultatsiden ble ikke ferdig – prøv igjen | Kildens resultatinnhold ble ikke ferdig lastet. |
| Kilden svarte ikke ferdig – prøv igjen | Oppslaget hadde en midlertidig feil. |
| SpliceAI-svaret samsvarer ikke med varianten/innstillingene | SpliceAI bekreftet ikke forventet variant, genom eller skårinnstillinger. |
| Treff ikke bekreftet – kildegrunnlaget må avklares | Kilden oppga treff uten at nødvendig kontroll kunne fullføres. |
| Treffet kunne ikke bekreftes | Kilden krever manuell avklaring. |
| Søket mislyktes | En feil uten en mer spesifikk gjenkjent kategori. Det opprinnelige feilsvaret bevares i Kilder. |
| Ukjent kildestatus: … | Den faktisk returnerte statusen er ukjent for appen. |

## MTBP

| Celleinnhold | Betydning |
|---|---|
| Valgt variant uavklart – MTBP er ikke kjørt | En valgt variant hindrer innsending av gruppen. |
| Innsending ikke bekreftet – sjekk eksisterende rapport | Det er uavklart om MTBP mottok innsendingen. Den eksisterende rapporten må kontrolleres før en ny innsending. |

MTBPs egne vurderinger og øvrig kildetekst beholdes slik de kommer fra MTBP.
