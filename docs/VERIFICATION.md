# Verifikasjon – Solide v0.1.0

Dato: 30. september 2026.

## Utført

- `python -m pytest -q`: 46 tester bestått.
- `python -m compileall -q src install_python_felles.py start_python_felles.py`: bestått.
- Virkelige lokale kildefiler kontrollert med 8 Ion-rader, 2 Genexus TSV-rader
  og 3204 Genexus XLSX-datarader. QC gjengir 4 CNV-feil, 5 NO CALL tiles og
  4 RNAExonVariant ABSENT.
- Native GUI-test: importert øktmodell, QC-visning, søk, avkrysning og øktlagring.
- Excel: pasientskille, alle-rad-QC, prosentverdier, formelbeskyttelse, genomversjon,
  utdatert evidens, bilder og full MTBP-rapport i arbeidsboken.
- Queue: pseudonyme eksterne records, separate pasientbatcher, manglende
  provider-respons som feil, foreløpig fangst ved avbrudd og komplett valgt
  MTBP-batch ved gjenopptak.
- Nomenklatur: kontrollert HGVS blandes ikke med gamle alleler; kontrollert
  intronoffset styrer SpliceAI; flergene-/MANE-/delins-avvik sperres for oppslag.
- Kopierte Edge/genomiske runtime-regresjoner passerer under Solides namespace.
- `scripts/verify_capture_locally.py`: ekte lokal Edge, syntetiske HTML-sider,
  screenshot-klipping ved zoom 1/1.25/0.8, nested scroll, riktig MTBP-variantrad
  og Franklin-genheader. Alle sjekker bestått.
- Native UI-skjermbilde laget og visuelt kontrollert med syntetiske demodata.
- Appen startet med normal Windows-plattform via start_python_felles.py;
  prosessvinduet har tittelen «Solide | Variantgjennomgang».
- Uavhengig kodegjennomgang: funn om kontrollert HGVS, MTBP-batchferskhet,
  SpliceAI-utvalg og genomversjon i rapport er rettet med regresjonstester.

## Ikke verifisert

- Ingen pasientvarianter er sendt til databaseleverandørene.
- Live kontoer, tilgang, leverandørsider og MTBP Other er ikke prøvd i en
  autentisert ende-til-ende-kjøring.
- Python FELLES, Ivanti app-ID 15694, proxy og Edge-policy må prøves på jobb-PC.
- MANE-omregning er implementert som forslag fra Mutalyzer med manuell
  godkjenning; laboratoriets transkriptvalg og nomenklatur må faglig valideres.
- QC gjelder eksporterte rader, ikke heldekkende gen-QC. Pakke-/genliste og
  endelig håndtering av CNV =1 må fortsatt defineres av laboratoriet.
- Kommentarer fra en manuelt endret eksportert Excel-fil importeres ikke tilbake;
  varige kommentarer føres i appens arbeidsøkt.

## Pilot

Start appen, velg godkjent arbeidsmappe, importer én kjent prøve og bekreft
identitet/hg19. Sammenlign QC og variantutvalg med arbeidsskjemaet. Logg inn
i aktuelle databaser via Edge, kjør et lite utvalg, kontroller identitet og bilder,
og sammenlign generert Excel med manuell rapport. Prøv også stopp/gjenopptak
og regenerering etter endret utvalg. Ingen klinisk godkjenning hevdes her.
