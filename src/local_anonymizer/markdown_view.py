"""Inert Markdown view; only explicit, validated resource requests leave it."""
from dataclasses import dataclass, field
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from PySide6.QtCore import QByteArray, QUrl, Signal
from PySide6.QtWidgets import QTextBrowser
from .domain import AnonymizerError

_EXTENSIONS = {'.pdf', '.txt', '.md', '.markdown', '.docx', '.xlsx', '.pptx',
               '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.gif', '.webp',
               '.wav', '.aif', '.aiff', '.mp3', '.mp4', '.mov'}


@dataclass(frozen=True, slots=True)
class LinkTarget:
    kind: str
    destination: str = field(repr=False)


def resolve_resource(href, root):
    try:
        value = str(href)
        for _ in range(4):
            decoded = unquote(value)
            if decoded == value: break
            value = decoded
        if (not value or '%' in value or '\\' in value
                or any(ord(c) < 32 or ord(c) == 127 or '\u202a' <= c <= '\u202e'
                       or '\u2066' <= c <= '\u2069' for c in value)):
            raise ValueError()
        parts = urlsplit(value)
        if parts.scheme.lower() in ('https', 'http'):
            if not parts.hostname or parts.username or parts.password: raise ValueError()
            # QUrl performs canonical URL encoding after validation.
            return LinkTarget('web', QUrl(value).toString(QUrl.FullyEncoded))
        if parts.scheme or parts.netloc or parts.query: raise ValueError()
        base = Path(root).resolve(strict=True)
        path = (base / parts.path).resolve(strict=True)
        if (not path.is_relative_to(base) or not path.is_file()
                or path.suffix.lower() not in _EXTENSIONS or path.stat().st_mode & 0o111):
            raise ValueError()
        return LinkTarget('local', str(path))
    except (ValueError, OSError, RuntimeError):
        raise AnonymizerError('LINK_BLOCKED') from None


class SafeMarkdownBrowser(QTextBrowser):
    resourceRequested = Signal(object)
    linkBlocked = Signal(str)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self.request_resource)

    def loadResource(self, resource_type, url):
        # Includes local images/styles: rendering never reads referenced files.
        return QByteArray()

    def render_markdown(self, text):
        self.setMarkdown(text)

    def request_resource(self, url):
        value = url.toString(QUrl.FullyEncoded)
        if value.startswith('#'):
            self.scrollToAnchor(url.fragment())
            return
        try: target = resolve_resource(value, self.root)
        except AnonymizerError:
            self.linkBlocked.emit('LINK_BLOCKED')
        else:
            self.resourceRequested.emit(target)
