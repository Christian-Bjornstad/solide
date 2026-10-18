"""OUM input used by the import and sample-details dialogs."""
import re


def normalize_oum(value):
    return str(value).strip().upper()


def valid_oum(value):
    return bool(re.fullmatch(r'\d{2}OUM\d+',normalize_oum(value)))
