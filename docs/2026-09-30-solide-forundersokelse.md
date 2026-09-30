# Solide – forundersøkelse og forslag til byggeplan

Dato: 30. september 2026. Forundersøkelse brukt som byggegrunnlag.
Lokal app v0.1.0 er nå implementert; se README og docs/VERIFICATION.md.
Live databasekontoer og klinisk bruk er ikke validert.

## Mål og arbeidsflyt

Importere Ion Reporter- og Genexus-filer, bevare alle rådata, kontrollere kvalitet,
velge varianter i appen, hente dokumenterte databasefunn og lage én Excel-rapport
per pasient. Mosegrønn og hvit profil. Brukeren vurderer funn og rapportinnhold.

Foreslått flyt:

1. Importer TSV og eventuelt komplett Genexus-arbeidsskjema.
2. Bekreft prøve/pasienttilknytning, assay, hg19 og vevstype.
3. Gjennomgå kvalitetsavvik og merk hvilke varianter som skal undersøkes.
4. Kontroller nomenklatur og alternative transkripter der det er nødvendig.
5. Velg databaser og start oppslagskøen.
6. Gjennomgå treff, skjermbilder, mangler og egne kommentarer.
7. Generer Excel-rapport for valgt pasient, eller én fil for hver valgt pasient.

Bekreftet av brukeren: lokal Windows-app på jobb-PC med Edge. Lagringssti på jobb
må velges eksplisitt; dersom den skal være på K-sensitiv, må dette konfigureres.

## Hva de lokale filene faktisk inneholder

Kun strukturer og summer er gjengitt her; ingen prøveidentifikatorer.

| Kilde | Innhold | Konsekvens |
|---|---|---|
| Ion Reporter TSV, langt filnavn | 8 eksporterte rader, 62 kolonner, metadata før tabellen | Header må finnes etter metadata. Oppgitt totalVariantCount er 3385 og er ikke antall eksporterte rader. |
| Snvindel.tsv | 2 rader med SNV/deletion, 24 navngitte kolonner og tom sluttkolonne | Kan brukes til variantimport, men dekker ikke full Genexus-QC. |
| Genexus XLSX | Ett ark, 3220 rader totalt, header foran 3204 datarader, 24 kolonner | Inneholder QC og flere varianttyper. Har også manuelle opplysninger før header. |

Ion A–L: Transcript, Genes, Coding, Amino Acid Change, Variant ID, ClinVar,
Allele Frequency %, Coverage, Phred QUAL Score, Copy Number, CNV Confidence, Locus.
A–G bør prioriteres i visningen. Locus beholdes som alternativt søkegrunnlag.

Genexus-arbeidsskjemaet har Type i B, Call i I, Coverage i K og Copy Number i O,
slik Eva beskriver. TSV-en har annen rekkefølge. Import skal derfor bruke
kolonnenavn og kildeprofil, ikke faste bokstaver.

Genexus-datarader:

| Type | Antall |
|---|---:|
| snp | 1315 |
| del | 263 |
| ins | 258 |
| complex | 172 |
| mnp | 144 |
| CNV | 45 |
| Fusion | 981 |
| ProcControl | 7 |
| RNAExonVariant | 9 |
| RNAExonTiles | 9 |
| GeneExpression | 1 |

Foreløpig telling etter reglene i e-posten: 4 CNV-rader med copy number <1,
5 RNAExonTiles med NO CALL og 4 RNAExonVariant med ABSENT.
Ingen av de 2152 småvariant-radene med numerisk coverage har coverage <500.
Dette er radbaserte summer, ikke en bekreftelse på at alle gener i pakken har
tilstrekkelig dekning. CNV/fusjon/RNA-rader har ikke numerisk coverage her.

Allelfrekvens må håndteres per kilde: Snvindel.tsv bruker fraksjoner (f.eks.
0.211), mens Ion og Genexus-XLSX har prosentkolonner. Enheten må bevares ved
import og normaliseres eksplisitt, slik at 0.211 blir 21.1 % bare for fraksjonskilden.

Ion har også rader med flere gener og transkripter i samme felt. Appen må bevare
disse og avklare koblingen før transkriptspesifikke søk; den skal ikke velge første
transkript uten kontroll.

## Anbefalt teknisk retning

**Anbefaling: Python + PyQt6, lokal datamodell og Microsoft Edge via CDP.**
Det samsvarer med Archer og MolStat og gir en tabellbasert desktop-app med
arbeidere i bakgrunnen for oppslag og eksport. Endelig Python-versjon og
pakkeinstallasjon må prøves i Python FELLES på jobb-PC.

Alternativer:

- Lokal webapp: god fleksibilitet i UI, men krever lokal server og separat
  koordinering av Edge-oppslag og appens nettleser.
- Intern serverapp: mulig ved flerbrukerbehov, men krever avklart drift,
  autentisering, lagring og en annen løsning for databaseøkter.

Archer har direkte Edge-styring via lokal DevTools-forbindelse, separate profiler,
skjermbilder, oppslagsstatus og gjenopptak. Dette er relevant gjenbruk, men er
ikke testet i Solide. Ingen automatisk overføring av Archer-spesifikke regler,
blod/lymfoide filtre eller standardvevet Blood. Provider-koden må gjennomgås
for solide svulster og skilles i små adaptere. Repoets lisens/gjenbruk må avklares.

MolStat har .cmd-filer som åpner Python FELLES via Ivanti PowerGate, app-ID 15694,
og kopierer en runpy-kommando til utklippstavlen. Python-filene håndterer
brukerinstallasjon, oppstart og logger. Bruk samme mønster med Solide-navn
etter verifikasjon av app-ID og miljø. Ingen installasjon er utført nå.

Foreslåtte modulgrenser:

- Import: egne adaptere for Ion TSV, Genexus TSV og Genexus XLSX.
- Variantmodell: rådata, kilde/rad, prøve, assay, genomversjon og variantidentitet.
- QC: versjonerte regler per assay/pakke, separat fra variantutvalg.
- Nomenklatur: original, normalisert, MANE-alternativ og kontrollstatus.
- Oppslag: én adapter per kilde, kø, pause, stopp, tidsgrenser og gjenopptak.
- Dokumentasjon: kilde-URL, søkevariant, tidspunkt, tekst, skjermbilde og status.
- Rapport: én arbeidsbok per pasient med funn, QC og dokumentasjon.

## Databasekoblinger og genomisk identitet

| Kilde | Mulighet | Hva gjenstår |
|---|---|---|
| ClinVar | Dokumentert E-utilities/data-tilgang; Archer har identitetskontroll | Verifisere GRCh37, REF/ALT og aktuelle varianttyper; bevare konflikter og vurderingsstatus. |
| Mutalyzer | Swagger beskriver normalize, position_convert og map | Teste syntetiske delins og transkriptkonvertering; intron-HGVS kan kreve genomisk referanse med transkriptselektor. |
| SpliceAI Lookup | Offentlig REST API for GRCh37 og GRCh38 | Langsom kø, håndtering av rate limit og registrering av modellparametre. |
| MTBP | Archer har innsending og rapport-/skjermbildefangst | Verifisere Other i faktisk vevsvalg, solide varianter og tillatt bruk. Ingen innsending er gjort. |
| Franklin | Archer har somatiske GRCh37-nettleseroppslag | Kontrollere aktuell tilgang, varianttreff og skjermbildeområder. API-tilgang er ikke bekreftet. |
| OncoKB | Dokumentert API med token; nettleseradapter finnes i Archer | Avklare institusjonens tilgang/lisens for pasientrapportering og vevsmapping. |
| COSMIC | Archer har variantoppslag og skjermbilder | Fjerne lymfoide begrensninger; kontrollere GRCh37 og klinisk rapporttilgang. |
| HSMD | Foreløpig manuelt felt | Avklare hvilken tjeneste navnet viser til og tilgang. |

Oppslag med feil, tidsavbrudd, tvetydig identitet eller delvise bilder skal ha egne
statuser. De skal ikke presenteres som «ikke funnet». Ved gjenopptak brukes tidligere
verifisert dokumentasjon, mens ufullstendige oppslag kan prøves på nytt.

Genomversjon holdes eksplisitt som GRCh37/hg19. Standardverdien i en ekstern
tjeneste er ikke tilstrekkelig. Genomisk nøkkel trenger kromosom, posisjon,
REF og ALT samt normalisering for indels. Locus alene er ikke en unik variant.
Genexus-XLSX mangler separate REF/ALT- og transkriptkolonner; disse må hentes fra
supplerende eksport eller pålitelig referansekartlegging før slike oppslag.

Geirs FGFR1/MET-par bevares som oppgitte startregler:

- FGFR1: NM_001127500.3 → NM_023110.3.
- MET: NM_001174067.1 → NM_000245.4.

Dette er ikke bare tekstutskifting av NM-nummer: varianten må kartlegges til
genomisk referanse og så til måltranskriptet. Begge uttrykk beholdes med sporbarhet.
NCBI oppgir at MANE bygger på GRCh38; bruk på hg19 må derfor valideres særskilt.
Gjeldende MANE-versjon og laboratoriets ønskede transkriptversjoner må avklares.

Alle delins får Mutalyzer-kontroll. Type complex bør markeres for kontroll slik
at feil annoterte delins også blir fanget opp. Resultatet bevarer original HGVS,
normalisert HGVS, advarsler og hvem som har kontrollert endringen.

Intronvarianter med avstand 1–100 bp på hver side av ekson markeres for
SpliceAI, også intervaller/komplekse varianter som berører dette området.
Manglende eller tvetydig avstandsannotasjon gir kontrollbehov.
Utvalgsregelen ±100 bp er forskjellig fra SpliceAIs distance-parameter, som
bestemmer modellens søkevindu rundt varianten. Modellvindu, mask og genmodell
registreres separat og avtales med laboratoriet.

## QC-regler og avklaringer

- Coverage <500: brukeren har bekreftet at dette gjelder selve variant-raden.
  Alle slike rader flagges, med berørte gener i rapporten. Variantcoverage alene
  bekrefter ikke heldekkende gen-QC.
- CNV <1: flagg som feilet etter Evas regel. CNV =1 må avklares, fordi e-posten
  også sier at alle aktuelle gener skal ha CNV >1. Manglende verdi er «ukjent».
- RNAExonTiles og «RNA Exon Tiles» behandles som samme type. NO CALL gir
  feilet uttrykksubalanse etter oppgitt regel.
- RNAExonVariant med ABSENT skal rapporteres, men den ønskede rapportteksten
  må avklares. ABSENT skal ikke automatisk kalles et positivt variantfunn.
- Pakke-/genliste må avklare hvilke gener kontrollene gjelder. Regler for Ion,
  andre assays, fusjoner, ProcControl og GeneExpression er ikke oppgitt.
- QC kjøres også på rader som ikke er valgt til databaseoppslag.

## UI-forslag etter ui-ux-pro-max

Skill-søket anbefalte Data-Dense Dashboard og Fira Sans/Fira Code. Søket ga
også en irrelevant produktanmeldelsesflyt og gullpalett; disse brukes ikke.
Fargeprofilen nedenfor følger brukerens mosegrønn/hvit-ønske.

- Mosegrønn hovedfarge #425B3D; hvite arbeidsflater #FFFFFF.
- Lys bakgrunn #F4F6F2; mørk tekst #1F2A22; rolig kant #D6DED2.
- Gul/oransje for kontrollbehov, rød for feil; alltid tekststatus i tillegg.
- Lokal/systemfont eller medfølgende font; ingen behov for Google Fonts-kall.
- Faste navigasjonsfaner: Import, Kvalitet, Variantutvalg, Databaseoppslag,
  Rapport og Innstillinger.
- Variantutvalg: søk/filter, avkrysning per rad, antall valgte og detaljpanel
  med original og alternativ nomenklatur. Alle data forblir tilgjengelige.
- Databaseoppslag: kildevalg, MTBP-vev inkludert Other, køstatus, pause/stopp,
  feilforklaring og gjenopptak. Brukervev lagres per prøve/kjøring.
- Rapport: forhåndsvisning av innhold, kontrollstatus og eksportknapp.
- Tastaturnavigasjon, tydelig fokus, tabellhoder, numerisk sortering og
  kontrastkontroll inngår i verifikasjonen.

## Excel-rapport

Forslag, som må tilpasses laboratoriets ønskede eksempelrapport:

1. Oversikt: prøve, assay, hg19, vev, valgte funn, allelfrekvens, nomenklatur,
   kildeoppsummeringer og egne kommentarer.
2. Kvalitet: feilet coverage, CNV, uttrykksubalanse, RNAExonVariant-status og
   manglende data, med regelgrunnlag og berørte gener/regioner.
3. Variantark: kildehenvisninger og lesbare skjermbilder for hvert valgt funn.
4. MTBP-vedlegg når tilgjengelig; rådata/kjørehistorikk for sporbarhet.

Kommentarer skal overleve regenerering via stabil variantidentitet.
Excel-lås skal gi mulighet for ny lagring uten å gjenta databaseoppslag.
Rapporten må vise når noen oppslag mangler eller ikke er verifisert.

## Foreslått rekkefølge og akseptansekriterier

1. **Avklar miljø og rapportformat.** Bekreft Python FELLES, Edge remote debugging,
   datalagring, pasienttilknytning, pakker og kildebruk.
2. **Import og variantutvalg.** Alle tre kildeformater leses med rett header,
   tallskala og originaldata. Kontroller mot 8/2/3204 lokale datarader.
3. **QC og grunnrapport.** Eksemplet gjengir de observerte 4/5/4 radflaggene;
   grenseverdiene 499/500 og CNV under/lik/over 1 testes med syntetiske data.
4. **Nomenklatur og identitet.** Test delins, minusstreng, flergenerader,
   transkriptomregning og intronavstand 100/101 med syntetiske varianter.
5. **Databaseadaptere enkeltvis.** Start med ClinVar og nomenklaturverktøy,
   deretter øvrige kilder og skjermbilder. Test feiltreff, tomt resultat,
   autentiseringsfeil, rate limit, tidsavbrudd og avbrutt kjøring.
6. **Samlet rapport og gjenopptak.** Kontroller bilder, kildeidentitet,
   kommentarbevaring, pasientskille og låste Excel-filer.
7. **Jobb-PC-pilot.** Prøv install/start via Python FELLES og Edge, deretter
   sammenlign utvalgte resultater med manuell laboratorieflyt før ordinær bruk.

Ingen pasientfiler er sendt til databasene i forundersøkelsen. Nettundersøkelsen
brukte dokumentasjon og offentlig kildekode. Endelig app skal skille lokal
prøveidentitet fra søkeinnhold; bare nødvendige variantdata og valgt vev brukes
eksternt. Autentiserte profiler og tilgangsnøkler holdes utenfor prosjektfiler.

## Prioriterte mangler

1. Lagringssti på jobb-PC (lokal kjøring er bekreftet).
2. Hvordan filer kobles til pasient/prøve når metadata og filnavn avviker;
   behov for flervalgsimport og flere prøver per pasient.
3. Hvilke pakker/gener QC gjelder. Radbasert coverage <500 er avklart.
4. CNV =1 og manglende verdier; formulering for RNAExonVariant ABSENT.
5. Hvilke varianter som vises/forvelges, og om CNV/fusjon/RNA også skal søkes.
6. Ønsket ferdig rapport og skjermbildeinnhold; obligatoriske kilder.
7. Databasekontoer/tilgang, MTBP Other og hva HSMD betyr.
8. Laboratoriets transkriptliste og ønskede SpliceAI-parametre.

## Kilder undersøkt

- [Archer-prosess](https://github.com/Christian-Bjornstad/Archer-prosess)
- [Archer browser_review.py](https://github.com/Christian-Bjornstad/Archer-prosess/blob/main/src/archer_processor/services/browser_review.py)
- [MolStat jobb-PC](https://github.com/Christian-Bjornstad/MolStat/blob/main/JOBBS-PC.md)
- [MolStat installasjon](https://github.com/Christian-Bjornstad/MolStat/blob/main/install_python_felles.py)
- [MolStat oppstart](https://github.com/Christian-Bjornstad/MolStat/blob/main/start_python_felles.py)
- [Mutalyzer API-schema](https://mutalyzer.nl/api/swagger.json)
- [ClinVar data-tilgang](https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/)
- [SpliceAI Lookup API og begrensninger](https://github.com/broadinstitute/SpliceAI-lookup/blob/master/README.md)
- [NCBI MANE](https://www.ncbi.nlm.nih.gov/refseq/MANE/)
- [MTBP](https://mtbp.org/)
- [OncoKB API](https://api.oncokb.org/oncokb-website/api)
- [OncoKB lisens](https://faq.oncokb.org/licensing)
- [COSMIC vilkår](https://www.cosmickb.org/terms/)

Mulighet for automatisering er dokumentert på grensesnitt-/referansekodenivå.
Solide-integrasjoner, live kontoer, skjermbildefangst og transkriptomregning er
ikke ende-til-ende-testet i dette miljøet.
