import json
import os
import tempfile
from pathlib import Path
from .models import Session, Variant


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
    atomic_write(path, json.dumps(session.to_dict(), ensure_ascii=False, indent=2, default=str))


def load_session(path: Path) -> Session:
    data = json.loads(Path(path).read_text(encoding='utf8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('variants'), list):
        raise ValueError('Ukjent eller ugyldig Solide-økt.')
    data['variants'] = [Variant(**v) for v in data['variants']]
    session = Session(**data)
    if len({v.id for v in session.variants}) != len(session.variants):
        raise ValueError('Økten inneholder dupliserte rad-ID-er.')
    return session
