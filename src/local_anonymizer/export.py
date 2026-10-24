"""Exclusive publication of a checked copy; never replace an existing path."""

import errno
import hashlib
import os
from pathlib import Path
import stat

from .domain import AnonymizerError, FileIdentity, Preview, Receipt, Review, Verification
from .transform import build_preview


def _identity(info: os.stat_result) -> FileIdentity:
    return FileIdentity(info.st_dev, info.st_ino)


def _matches(dir_fd: int, name: str, identity: FileIdentity) -> bool:
    try:
        return _identity(os.stat(name, dir_fd=dir_fd, follow_symlinks=False)) == identity
    except OSError:
        return False


def _check_file(dir_fd: int, name: str, identity: FileIdentity, payload: bytes):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or _identity(info) != identity
                or info.st_size != len(payload)):
            raise AnonymizerError('EXPORT_MISMATCH')
        chunks = []
        total = 0
        while total <= len(payload):
            chunk = os.read(fd, min(65_536, len(payload) + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if b''.join(chunks) != payload or not _matches(dir_fd, name, identity):
            raise AnonymizerError('EXPORT_MISMATCH')
    finally:
        os.close(fd)


def _publish_bytes(payload: bytes, destination: Path) -> Receipt:
    """Create the final name exclusively and never remove any pathname.

    POSIX has no conditional unlink by inode. Even a stat/unlink pair on a
    random staging name can delete someone else's replacement. A failed write
    therefore leaves its candidate for explicit inspection. The final name is
    visible during writing; success is issued only after two reopened checks.
    """
    destination = Path(destination).absolute()
    parent, name = destination.parent, destination.name
    dir_fd = None
    created = False
    try:
        dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        directory_identity = _identity(os.fstat(dir_fd))
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=dir_fd)
        created = True
        try:
            identity = _identity(os.fstat(fd))
            remaining = memoryview(payload)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    raise AnonymizerError('EXPORT_WRITE')
                remaining = remaining[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        _check_file(dir_fd, name, identity, payload)
        if _identity(os.stat(parent)) != directory_identity:
            raise AnonymizerError('DESTINATION_CHANGED')
        # Candidate and final destination share the exclusively created name.
        # Reopen again before the logical publication/success notification.
        _check_file(dir_fd, name, identity, payload)
        os.fsync(dir_fd)
        if _identity(os.stat(parent)) != directory_identity:
            raise AnonymizerError('DESTINATION_CHANGED')
        return Receipt(destination, identity, hashlib.sha256(payload).hexdigest())
    except (OSError, AnonymizerError) as error:
        if isinstance(error, AnonymizerError):
            code = error.code
        elif error.errno in (errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV):
            code = 'EXPORT_UNSUPPORTED'
        elif error.errno == errno.EEXIST:
            code = 'EXPORT_EXISTS'
        else:
            code = 'EXPORT_FAILED'
        # Always report the requested location after creation, including a
        # replacement by a third party. It is an inspection hint, not proof
        # that the name or its parent still designates our inode.
        pending = (destination,) if created else ()
        raise AnonymizerError(code, cleanup_paths=pending) from None
    finally:
        if dir_fd is not None:
            os.close(dir_fd)


def publish_text(review: Review, preview: Preview, verification: Verification,
                 destination: Path) -> Receipt:
    if (review.confirmed is not True or not verification.ok or verification.issues
            or verification.residuals or verification.detector_fingerprint == 'unavailable'
            or verification.session_id != review.document.session_id
            or verification.review_revision != review.revision
            or verification.preview_sha256 != preview.sha256
            or preview != build_preview(review)):
        raise AnonymizerError('EXPORT_NOT_VERIFIED')
    if Path(destination).absolute() == review.document.source_path:
        raise AnonymizerError('EXPORT_ORIGINAL')
    return _publish_bytes(preview.text.encode('utf-8'), destination)
