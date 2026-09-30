# Solide

Lokal Windows-app for Ion Reporter- og Genexus-variantgjennomgang.
Mosegrønn og hvit PyQt6-arbeidsflate med import, QC, variantutvalg,
databaseoppslag og én Excel-rapport per pasient.

## Start på denne PC-en

```powershell
python -m pip install -e ".[dev]"
python start_python_felles.py
```

Alternativt: dobbeltklikk `SOLIDE_START.cmd` etter installasjon.

## Jobb-PC / Python FELLES

1. Legg prosjektet i en fast mappe som du har tilgang til.
2. Kjør `SOLIDE_INSTALL.cmd`, lim inn kommandoen i Python FELLES og trykk Enter.
3. Lukk Python FELLES og kjør `SOLIDE_START.cmd`; lim inn startkommandoen.
4. Velg godkjent arbeidsmappe i Innstillinger.

Skriptmønsteret er tilpasset MolStat. Ivanti app-ID 15694 er hentet derfra og
må bekreftes på jobb-PC. Python >=3.11 kreves; Python FELLES 3.14 er ikke prøvd
her. Installasjon skjer i brukerens site-packages uten administratorrettigheter.
Bootstraplogger: `%LOCALAPPDATA%\Solide\logs\bootstrap.log`.

## Arbeidsflyt

1. Last inn TSV eller Genexus XLSX og bekreft pasient/prøve-ID og hg19.
   Appen bruker ikke filnavnet som pasientidentitet. Samme fil/rad importeres
   bare én gang i økten; ulike eksportfiler beholdes som separate kilder.
2. Gjennomgå Kvalitet. Coverage <500 gjelder hver eksportert rad, og berørte
   gener flagges. QC inkluderer også rader uten valgt databaseoppslag.
3. Kryss av varianter i Variantutvalg. Genexus PRESENT-småvarianter forvelges;
   alle rader er tilgjengelige. Ion-rader uten PRESENT-status velges manuelt.
4. Velg databaser og vev under Databaseoppslag. Other er standard for MTBP.
5. Delins/complex og kjente FGFR1/MET-transkriptavvik må kontrolleres før
   ordinære databaseoppslag. Mutalyzer-køen viser normalisering og eventuelt
   forslag på måltranskript. Angi full kontrollert HGVS i variantens detaljpanel
   og kryss av at den er kontrollert. Rå eksport beholdes.
6. Lagre arbeidsøkten og start oppslag. Pause/stopp gjelder ved sikre stoppunkter;
   aktive HTTP-/nettleseroperasjoner kan måtte fullføre eller nå tidsgrensen.
   Resultater lagres til økten etter hver returnerte kilde. Foreløpige
   skjermbildefangster beholdes ved avbrudd og merkes ufullstendige.
7. Gjennomgå treff og feil. Dobbeltklikk et oppslag for kilde-URL.
8. Generer én Excel-rapport eller rapporter for alle pasienter. Lukk eksisterende
   målfil i Excel før regenerering. Kommentarer føres og bevares i appens økt;
   kommentarer redigert direkte i eksportert Excel importeres ikke tilbake.

## QC og nomenklatur

- Coverage <500: Feilet. Manglende småvariantcoverage: Ukjent.
- CNV Copy Number <1: Feilet. =1: Kontroll. Manglende: Ukjent.
- RNAExonTiles NO CALL: Feilet uttrykksubalanse.
- RNAExonVariant ABSENT: Rapporteres som status, ikke positivt funn.
- Intronoffset 1–100 bp: SpliceAI-kandidat. HGVS-offset og modellvindu er
  forskjellige: denne versjonen bruker distance=500 og mask=1 i SpliceAI.

Reglene gjelder de importerte radene; de bekrefter ikke hele geners dekning.
Pakkeavgrensning må foreløpig gjøres ved å importere riktig assay-eksport.

## Oppslag og begrensninger

ClinVar, Franklin, COSMIC, OncoKB og MTBP bruker en tilpasset, versjonslåst
Archer Edge/CDP-tjeneste. Edge remote debugging må være tillatt på jobb-PC.
COSMIC har ingen lymfoid vevsbegrensning i Solide. MTBP velger vevet eksakt.
Innlogging skjer direkte i synlig Edge; automatiske oppslag er minimert som standard.

Mutalyzer og SpliceAI har egne HTTP-adaptere. SpliceAI venter minst 30 sekunder
mellom oppslag og krever eksplisitt GRCh37, locus, REF og ALT. Genexus-XLSX
mangler REF/ALT og kan derfor ikke brukes direkte til slike genomiske oppslag.
MTBP, OncoKB og Franklin kan bruke gen/protein når transkript mangler; resultatet
merkes med dette søkegrunnlaget. ClinVar krever transkript eller genomiske alleler.
FGFR1/MET krever avklart transkript. Flere gener/
transkripter må avklares i detaljpanelet. HSMD føres manuelt i kommentar.

Kontrollert HGVS bruker ikke original REF/ALT som automatisk reserve. Angi
tilsvarende kontrollert hg19-variant som chr-pos-REF-ALT dersom det trengs
genomisk søk eller SpliceAI etter en rettelse.

Endring av vev eller variantidentitet gjør tidligere resultater utdaterte.
MTBP-fullrapport blir også utdatert når pasientens variantutvalg endres.
Ved MTBP-gjenopptak kjøres hele det valgte pasientutvalget hvis noe mangler,
slik at fullrapporten dekker samme utvalg. Gamle portalrapporter slettes ikke
automatisk; ved full kapasitet må brukeren rydde i MTBP. Bare den nye rapporten
kan fjernes automatisk etter at lokal fangst er fullført.
Oppslagsfeil, tidsavbrudd, identitetsavvik og delvise bilder vises separat fra
«ikke funnet». Regenerering bruker bare aktuelle bilder. Autentiserte profiler
ligger under `%USERPROFILE%\.solide\browser_profiles`; de skal ikke kopieres til Git.

Originalfiler, økter og rapporter lagres lokalt. Eksterne adaptere får bare
variantdata og pseudonyme oppslags-ID-er, ikke pasient-ID, kommentarer eller
originalfilnavn. Institusjonens kilde-/rapporttilgang må gjelde faktisk bruk.

Ingen pasientvarianter er sendt til eksterne tjenester under byggingen.
Live resultater, MTBP Other, kontoer og jobb-PC-miljø må prøves i en pilot.
Appen er vurderingsstøtte; rapporter må gjennomgås før klinisk bruk.

## Utvikling

```powershell
python -m pytest -q
python -m compileall -q src install_python_felles.py start_python_felles.py
```

Se `docs/ARCHER_REUSE.md` for kildeversjon og tilpasninger og
`docs/2026-09-30-solide-forundersokelse.md` for forundersøkelsen.
