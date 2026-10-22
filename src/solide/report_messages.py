"""Short Norwegian operational results, separate from unchanged source assertions."""

STATUS_MESSAGES = {
    'login_required': 'Innlogging kreves',
    'authentication_failed': 'Innlogging mislyktes',
    'verification_required': 'Bekreftelse mangler – åpne kilden',
    'timeout': 'Tidsavbrudd – prøv igjen',
    'network_error': 'Nettverkstilkobling mislyktes',
    'unauthorized': 'Tilgang avvist – kontroller innlogging/lisens',
    'token_required': 'API-nøkkel mangler',
    'rate_limited': 'For mange forespørsler – vent og prøv igjen',
    'quota_exhausted': 'Kvoten er brukt opp',
    'invalid_query': 'Ugyldig søkegrunnlag',
    'unsupported_query': 'Søketypen støttes ikke',
    'layout_changed': 'Nettsiden er endret – resultatet kunne ikke leses',
    'ambiguous': 'Flere mulige treff – ingen valgt',
    'ambiguous_result': 'Flere mulige treff – ingen valgt',
    'identity_mismatch': 'Feil variant – treff utelatt',
    'partial_capture': 'Ufullstendig bilde – prøv igjen',
    'capture_failed': 'Skjermbildet kunne ikke tas – prøv igjen',
    'manual_required': 'Manuelt søk kreves',
    'manual_review': 'Treffet kunne ikke bekreftes',
    'submission_unknown': 'Innsending ikke bekreftet – sjekk eksisterende rapport',
    'deferred': 'Søket er utsatt',
    'transient': 'Kilden svarte ikke ferdig – prøv igjen',
    'needs_review': 'Variantgrunnlaget må avklares før søk',
    'error': 'Søket mislyktes',
}


def result_issue(item,assessment):
    """Never collapse sign-in, identity, transport and capture failures into one label."""
    if assessment=='Outdated':return 'Utdatert'
    raw=item.get('raw',{});failure=raw.get('failure') or {}
    status=item.get('status','unknown');summary=item.get('summary','')
    kind=failure.get('type','')
    if kind=='EdgeCdpProfileInUse':return 'Edge-profil i bruk – lukk innloggingsvinduet'
    if kind=='EdgeCdpPolicyError':return 'Edge blokkert av IT-policy'
    if kind=='ProxyError':return 'Proxy-tilkobling mislyktes'
    if kind=='SSLError':return 'Sertifikatet kunne ikke bekreftes'
    if failure.get('http_status')==429:return STATUS_MESSAGES['rate_limited']
    if failure.get('http_status') in {401,403}:return STATUS_MESSAGES['unauthorized']
    if failure.get('http_status'):return f"Kilden svarte med HTTP {failure['http_status']}"
    if raw.get('nomenclature_assessment',{}).get('status')=='Conflict':
        return 'Variantnavn og kildealleler avviker'
    if (item.get('database')=='Mutalyzer' and raw.get('nomenclature_assessment')
            and not raw['nomenclature_assessment'].get('identity_confirmed')):
        return 'Variantnavnet kunne ikke bekreftes'
    if raw.get('blocked_by_annotations'):return 'Annotasjon uavklart – søket er ikke kjørt'
    if status=='manual_review' and raw.get('failure_kind')=='identity_mismatch':
        if 'transcript' in summary.lower():return 'Transkript avviker – genomisk treff ikke bekreftet'
        return 'Variantidentitet ikke bekreftet – treff utelatt'
    if assessment=='Identity mismatch':return STATUS_MESSAGES['identity_mismatch']
    if assessment=='Missing capture':return 'Bilde mangler'
    if assessment=='Recheck required':return 'Nytt søk kreves – variantgrunnlaget må avklares'
    if status in {'error','transient'} and raw.get('failure_stage') in {'result_rendering','canonical_link_resolution'}:
        return 'Resultatsiden ble ikke ferdig – prøv igjen'
    if status=='needs_review':
        # These are app validation messages, not provider assertions.
        for text,message in [
            ('Confirm GRCh37','Referansegenom må bekreftes som GRCh37'),
            ('Multiple genes','Flere gener/transkripter – velg annotasjon'),
            ('Approve corrected HGVS','Endret variantnavn må godkjennes'),
            ('Review the normalized Mutalyzer','Endret variantnavn må godkjennes'),
            ('Mutalyzer found a conflict','Variantnavn og kildealleler avviker'),
            ('MTBP-gruppen','Valgt variant uavklart – MTBP er ikke kjørt'),
        ]:
            if text in summary:return message
    if item.get('database')=='SpliceAI' and assessment=='Review required':
        return 'SpliceAI-svaret samsvarer ikke med varianten/innstillingene'
    if status in {'found','verified'}:return 'Treff ikke bekreftet – kildegrunnlaget må avklares'
    return STATUS_MESSAGES.get(status,f'Ukjent kildestatus: {status}')
