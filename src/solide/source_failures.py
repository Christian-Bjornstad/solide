"""Distinguish service access and connectivity failures from invalid variants."""
import requests
from ._vendor.archer.services.edge_cdp import EdgeCdpPolicyError,EdgeCdpProfileInUse


def source_failure(source,error):
    outer_type=type(error).__name__;seen=set()
    known=(EdgeCdpPolicyError,EdgeCdpProfileInUse,requests.RequestException,TimeoutError,ValueError)
    while error.__cause__ is not None and id(error) not in seen and not isinstance(error,known):
        seen.add(id(error));error=error.__cause__
    status_code=getattr(getattr(error,'response',None),'status_code',None)
    status='error';message=str(error)
    if isinstance(error,EdgeCdpPolicyError):
        status='network_error';message='Edge-automatisering er blokkert av maskinens policy. Kontakt IT om lokal DevTools-tilgang.'
    elif isinstance(error,EdgeCdpProfileInUse):
        status='network_error';message='Kildens Edge-profil er allerede i bruk. Lukk innloggingsvinduet og prøv igjen.'
    elif isinstance(error,requests.exceptions.ProxyError):
        status='network_error';message='Proxy-tilkoblingen mislyktes. Kontroller jobb-PC-ens nettverk og proxy med IT.'
    elif isinstance(error,requests.exceptions.SSLError):
        status='network_error';message='Sertifikatet kunne ikke bekreftes. Kontroller Windows-sertifikater og nettverk med IT.'
    elif isinstance(error,(requests.Timeout,TimeoutError)):
        status='timeout';message='Tidsavbrudd hos kilden. Prøv igjen.'
    elif status_code==429 or ('rate limit' in str(error).lower()):
        status='rate_limited';message='For mange forespørsler hos kilden. Vent litt og prøv igjen.'
    elif status_code in (401,403):
        status='unauthorized';message='Kilden avviste tilgangen. Kontroller innlogging, lisens eller nettverkstilgang.'
    elif isinstance(error,requests.ConnectionError):
        status='network_error';message='Nettverkstilkoblingen til kilden mislyktes. Kontroller tilgang på jobb-PC-en.'
    elif isinstance(error,requests.HTTPError):
        status='network_error';message=f'Kilden svarte med HTTP {status_code}. Prøv igjen senere.'
    elif isinstance(error,requests.exceptions.JSONDecodeError):
        status='network_error';message='Kilden returnerte ikke forventede data. Kontroller nettverkstilgang eller prøv igjen senere.'
    elif isinstance(error,ValueError):status='needs_review'
    return {'status':status,'summary':source+': '+message,
            'raw':{'failure':{'source':source,'type':type(error).__name__,'outer_type':outer_type,'http_status':status_code}}}
