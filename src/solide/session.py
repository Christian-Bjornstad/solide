import json
import os
import tempfile
from pathlib import Path
from .models import Analysis, Session, Variant
from .analyses import ensure_analyses, validate_analyses


def atomic_write(path: Path, payload: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.solide-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save_session(session: Session, path: Path) -> None:
    ensure_analyses(session)
    atomic_write(path, json.dumps(session.to_dict(), ensure_ascii=False, indent=2, default=str))


def load_session(path: Path) -> Session:
    data = json.loads(Path(path).read_text(encoding='utf8'))
    if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
            or data['schema_version'] not in {1, 2} or not isinstance(data.get('variants'), list)
            or not isinstance(data.get('analyses', []), list)):
        raise ValueError('Unknown or invalid Solide session.')
    legacy = data['schema_version'] == 1
    try:
        data['variants'] = [Variant(**v) for v in data['variants']]
        data['analyses'] = [Analysis(**analysis) for analysis in data.get('analyses', [])]
        session = Session(**data)
    except (TypeError, ValueError):
        raise ValueError('Unknown or invalid Solide session.') from None
    for variant in data['variants']:
        if variant.assembly == 'Ukjent':
            variant.assembly = 'Unknown'
    if legacy:
        ensure_analyses(session)
    else:
        validate_analyses(session)
    return session
