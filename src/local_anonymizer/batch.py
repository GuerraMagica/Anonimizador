"""A bounded queue with independent review ownership and explicit publication."""
from dataclasses import dataclass, field
from pathlib import Path
import stat
from .domain import AnonymizerError
from .session import Session
from .source import LoadedSource, MAX_BATCH_BYTES, MAX_BATCH_FILES


@dataclass(slots=True)
class BatchEntry:
    path: Path = field(repr=False)
    session: Session = field(default_factory=Session, repr=False)
    source: LoadedSource | None = field(default=None, repr=False)
    terms: tuple = field(default=(), repr=False)
    regions: tuple = ()
    visual: object = field(default=None, repr=False)
    visual_verification: object = field(default=None, repr=False)
    visual_rejections: tuple = field(default=(), repr=False)
    report: object = field(default=None, repr=False)
    receipt: object = field(default=None, repr=False)
    error: str | None = None

    def attach(self, source):
        if self.session.busy: raise AnonymizerError('JOB_ACTIVE')
        self.source = source
        self.session.load(source.document)
        self.regions = ();self.visual = self.visual_verification = None
        self.visual_rejections = ();self.terms = ();self.report = None
        self.receipt = None;self.error = None

    def invalidate_visual(self):
        self.session.invalidate_context()
        self.visual = self.visual_verification = None
        self.visual_rejections = ();self.report = None


class Batch:
    def __init__(self, paths=()):
        # Check count before stat/read; no payload is loaded until selected.
        if len(paths) > MAX_BATCH_FILES: raise AnonymizerError('BATCH_FILE_LIMIT')
        entries=[];seen=set();total=0
        try:
            for raw in paths:
                path=Path(raw).absolute()
                info=path.lstat()
                if not stat.S_ISREG(info.st_mode): raise AnonymizerError('INPUT_NOT_REGULAR')
                identity=(info.st_dev, info.st_ino)
                if identity in seen: continue
                seen.add(identity);total+=info.st_size
                if total > MAX_BATCH_BYTES: raise AnonymizerError('BATCH_BYTE_LIMIT')
                entries.append(BatchEntry(path))
        except OSError:
            raise AnonymizerError('INPUT_READ') from None
        self.entries=entries

    def validate_limits(self, pending_source=None, pending_entry=None):
        """Reserve actual retained bytes plus current sizes of unopened files."""
        total=0
        try:
            for entry in self.entries:
                source=pending_source if entry is pending_entry else entry.source
                if source is not None:
                    total+=source.input_bytes
                else:
                    info=entry.path.lstat()
                    if not stat.S_ISREG(info.st_mode):raise AnonymizerError('INPUT_NOT_REGULAR')
                    total+=info.st_size
                if total>MAX_BATCH_BYTES:raise AnonymizerError('BATCH_BYTE_LIMIT')
        except OSError:
            raise AnonymizerError('INPUT_READ') from None
