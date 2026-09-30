"""Bounded local activity log. Secrets never belong in activity messages."""
from datetime import datetime
from logging.handlers import RotatingFileHandler
import logging
import os
from pathlib import Path
import re
from collections import deque


class ActivityLog:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local'))/'Solide'/'logs'/'activity.log'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handler = RotatingFileHandler(self.path, maxBytes=2_000_000, backupCount=3, encoding='utf8')
        self.logger = logging.Logger(f'solide.activity.{id(self)}', logging.INFO)
        self.logger.addHandler(self.handler)
        self.secrets = set()

    def redact(self, message):
        text = str(message)
        for secret in sorted(self.secrets, key=len, reverse=True):
            if secret:
                text = text.replace(secret, '[redacted]')
        return re.sub(r'(?i)((?:password|access_token|api_key|token|authorization)\s*[=:]\s*)[^\s&;]+', r'\1[redacted]', text)

    def write(self, message):
        entry = f'{datetime.now().astimezone().isoformat(timespec="seconds")}  {self.redact(message)}'
        self.logger.info(entry)
        return entry

    def tail(self, limit=200):
        try:
            with self.path.open(encoding='utf8') as file:
                return '\n'.join(self.redact(line.rstrip()) for line in deque(file,maxlen=limit))
        except OSError:return ''

    def close(self):
        self.handler.close()
