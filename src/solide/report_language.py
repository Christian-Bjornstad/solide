"""Translate app-owned report labels; never translate provider assertions or raw data."""
import re

TEXT={
    'Gene':'Gen','Variant':'Variant','Source':'Kilde','Match assessment':'Treffstatus',
    'Source assertion':'Kildevurdering','Captured (Oslo)':'Hentet (Oslo)','Evidence':'Kildedata',
    'Source URL':'Kildelenke','Summary':'Sammendrag','Row ID':'Rad-ID','Accession':'Kilde-ID',
    'JSON response':'JSON-svar','Source row':'Kilderad','Source file':'Kildefil',
    'Analysis ID':'Analyse-ID','Source SHA256':'Filhash (SHA256)','Source evidence':'Kildedata',
    'Solide Row ID':'Solide-rad-ID','Selected':'Valgt','Source sheet':'Kildeark','Assembly':'Referansegenom',
    'Full source assertion':'Full kildevurdering','Full summary':'Fullt sammendrag',
    'Analysis':'Analyse','Source metadata':'Kildemetadata','Open attachment':'Åpne vedlegg',
    'Open local capture':'Åpne bilde','Open source':'Åpne kilde','Review source':'Kontroller kilde',
    'No database searches have been recorded.':'Ingen databasesøk.',
    'Original rows: right-click a worksheet tab and choose Unhide → Raw data.':'Originaldata finnes i Rådata.',
    'Source assertions are separate from laboratory assessments. Full responses and provenance are retained in hidden columns.':'Kildesvar er bevart i skjulte kolonner.',
    'Verified match':'Bekreftet treff','Review match':'Treff må kontrolleres','No match':'Ingen treff',
    'Not applicable':'Ikke aktuelt','Outdated':'Utdatert','Missing capture':'Bilde mangler',
    'Pending':'Ikke kjørt','Review required':'Må vurderes','Recheck required':'Nytt søk kreves',
    'Identity mismatch':'Feil variant','Partial capture':'Ufullstendig bilde','Sign-in required':'Innlogging kreves',
    'Timeout':'Tidsavbrudd','Failed':'Feil','Layout changed':'Nettsiden er endret','Ambiguous match':'Uklart treff',
    'Access required':'Tilgang kreves','Quota reached':'Kvoten er brukt opp','Rate limited':'For mange søk',
    'Review query':'Kontroller søket','Submission uncertain':'Uavklart innsending','Deferred':'Utsatt',
    'Provider evidence':'Kildebilde','Classification summary':'Klassifikasjon',
    'Classification evidence':'Klassifikasjon','Variant overview and mutation effect':'Variant og mutasjonseffekt',
    'Franklin classification and ACMG evidence':'Franklin-klassifikasjon og ACMG-evidens',
    'Full ACMG classification page':'ACMG-klassifikasjon','ACMG classification overview':'ACMG-oversikt',
    'Oncogenic classification overview':'Onkogen klassifikasjon',
    'Predictions':'Prediksjoner','Population frequencies':'Populasjonsfrekvenser',
    'Clinical evidence':'Klinisk evidens',
    'COSMIC overview':'COSMIC-oversikt','COSMIC tissue distribution':'COSMIC-vevsfordeling',
    'COSMIC samples (all tissues)':'COSMIC-prøver (alle vev)',
    'Alteration-centric functional evidence':'Funksjonell evidens',
    'Mutalyzer · input and normalized name':'Mutalyzer · opprinnelig og normalisert navn',
    'SpliceAI query · hg19 · ±500 bp · masked · REF/ALT':'SpliceAI-spørring · hg19 · ±500 bp · maskert · REF/ALT',
    'SpliceAI transcript scores · all basic transcripts':'SpliceAI-skårer · alle basic-transkripter',
    'BRCA Exchange · variant identity and ENIGMA classification':'BRCA Exchange · variant og ENIGMA-klassifikasjon',
}


def report_text(value):
    return TEXT.get(value,value)


def capture_caption(value):
    segmented=re.fullmatch(r'(.*) \((\d+) of (\d+)\)',value)
    if segmented:return f'{capture_caption(segmented[1])} ({segmented[2]} av {segmented[3]})'
    for prefix,translated in [('ACMG evidence: ','ACMG-evidens: '),('Oncogenic evidence: ','Onkogen evidens: ')]:
        if value.startswith(prefix):return translated+value[len(prefix):]
    return report_text(value)
