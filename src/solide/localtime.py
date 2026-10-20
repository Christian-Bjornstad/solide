"""Oslo display time, independent of the workstation's configured timezone."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

OSLO = ZoneInfo('Europe/Oslo')
EXCEL_DATETIME_FORMAT = 'dd.mm.yyyy hh:mm:ss'


def oslo_now():
    return datetime.now(OSLO)


def oslo_datetime(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime):
        raise ValueError('Missing or invalid timestamp.')
    # Historical naive source timestamps were recorded as UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(OSLO)


def oslo_text(value):
    try:
        return oslo_datetime(value).strftime('%d.%m.%Y %H:%M:%S %Z')
    except (ValueError, TypeError, OverflowError):
        return ''
