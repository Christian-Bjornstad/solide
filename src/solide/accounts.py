"""Local account names and Windows Credential Manager integration."""
from __future__ import annotations

ACCOUNT_PROVIDERS = ('Franklin', 'COSMIC', 'OncoKB', 'MTBP')
SERVICE = 'Solide'


def credential_backend():
    import keyring
    from keyring.backends.Windows import WinVaultKeyring
    backend = keyring.get_keyring()
    if not isinstance(backend, WinVaultKeyring):
        raise RuntimeError('Windows Credential Manager is unavailable. Sign in directly through Edge.')
    return backend


def read_password(provider, username, backend=None):
    if not username:
        return ''
    try:
        return (backend or credential_backend()).get_password(f'{SERVICE}/{provider}', username) or ''
    except Exception as exc:
        raise RuntimeError(f'Could not read the {provider} password from Windows Credential Manager. Use Edge sign-in or check the vault.') from exc


def write_password(provider, username, password, backend=None):
    if provider not in ACCOUNT_PROVIDERS or not username or not password:
        raise ValueError('Choose a provider and enter a username and password.')
    try:
        (backend or credential_backend()).set_password(f'{SERVICE}/{provider}', username, password)
    except Exception as exc:
        raise RuntimeError(f'Could not save the {provider} password in Windows Credential Manager.') from exc


def remove_password(provider, username, backend=None):
    if username and read_password(provider, username, backend):
        try:
            (backend or credential_backend()).delete_password(f'{SERVICE}/{provider}', username)
        except Exception as exc:
            raise RuntimeError(f'Could not remove the {provider} password from Windows Credential Manager.') from exc


def browser_credentials(accounts, backend=None):
    values = {}
    for provider in ACCOUNT_PROVIDERS:
        username = accounts.get(provider, '')
        if username:
            prefix = provider.lower()
            values[f'{prefix}_email'] = username
            values[f'{prefix}_password'] = read_password(provider, username, backend)
    return values
