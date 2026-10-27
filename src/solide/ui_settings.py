"""Read optional UI preferences without trusting saved JSON value types."""
import json
from .accounts import ACCOUNT_PROVIDERS


def read_ui_settings(path):
    try:settings=json.loads(path.read_text(encoding='utf8'))
    except (OSError,ValueError):return {}
    if not isinstance(settings,dict):return {}
    if not isinstance(settings.get('background',True),bool):settings.pop('background',None)
    distance=settings.get('igv_distance_bp')
    if type(distance) is not int or not 0<=distance<=1000000:settings.pop('igv_distance_bp',None)
    if 'sources' in settings:
        if not isinstance(settings['sources'],list):settings.pop('sources')
        else:settings['sources']=[s for s in settings['sources'] if isinstance(s,str)]
    accounts=settings.get('accounts',{})
    settings['accounts']={s:u for s,u in accounts.items() if s in ACCOUNT_PROVIDERS and isinstance(u,str)} if isinstance(accounts,dict) else {}
    checks=settings.get('login_checks',{})
    settings['login_checks']={}
    if isinstance(checks,dict):
        for source,value in checks.items():
            if source not in ACCOUNT_PROVIDERS or not isinstance(value,dict):continue
            settings['login_checks'][source]={key:value[key] for key in ('state','time') if isinstance(value.get(key),str)}
    return settings
