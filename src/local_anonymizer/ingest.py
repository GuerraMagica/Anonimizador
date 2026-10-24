"""Bounded, read-only ingestion of supported UTF-8 text files."""

import errno
import hashlib
import os
from pathlib import Path
import stat
from uuid import uuid4

from .domain import AnonymizerError, Document, FileIdentity

MAX_BYTES = 1_048_576
MAX_CHARACTERS = 100_000
_BIDI = frozenset('\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e'
                  '\u2066\u2067\u2068\u2069')
_INVISIBLE = frozenset('\u200b\u2060\ufeff')
_SIGNATURES = (b'%PDF-', b'PK\x03\x04', b'\x89PNG', b'\xff\xd8\xff')


def _snapshot(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def load_document(path: Path) -> Document:
    path = Path(path)
    if path.suffix.lower() not in {'.txt', '.md', '.markdown'}:
        raise AnonymizerError('INPUT_FORMAT')
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise AnonymizerError('INPUT_NOT_REGULAR')
        if before.st_size > MAX_BYTES:
            raise AnonymizerError('INPUT_BYTE_LIMIT')
        chunks = []
        total = 0
        while total <= MAX_BYTES:
            chunk = os.read(fd, min(65_536, MAX_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > MAX_BYTES:
            raise AnonymizerError('INPUT_BYTE_LIMIT')
        if _snapshot(before) != _snapshot(os.fstat(fd)):
            raise AnonymizerError('INPUT_CHANGED')
        data = b''.join(chunks)
    except OSError as error:
        code = 'INPUT_NOT_REGULAR' if error.errno == errno.ELOOP else 'INPUT_READ'
        raise AnonymizerError(code) from None
    finally:
        if fd is not None:
            os.close(fd)
    payload = data.removeprefix(b'\xef\xbb\xbf')
    if payload.startswith(_SIGNATURES):
        raise AnonymizerError('INPUT_FORMAT')
    try:
        text = payload.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        raise AnonymizerError('INPUT_ENCODING') from None
    if len(text) > MAX_CHARACTERS:
        raise AnonymizerError('INPUT_CHARACTER_LIMIT')
    if any((ord(c) < 32 and c not in '\t\r\n') or 0x7f <= ord(c) <= 0x9f
           or c in _BIDI or c in _INVISIBLE for c in text):
        raise AnonymizerError('INPUT_CONTROL')
    return Document(str(uuid4()), 0, path.absolute(),
                    FileIdentity(before.st_dev, before.st_ino), text,
                    hashlib.sha256(data).hexdigest())
