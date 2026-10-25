"""Bounded DOCX validation and isolated, local visual conversion.

The returned PDF is an intermediate: only the downstream raster pipeline strips
metadata and hidden structures. No source names or document text enter errors.
"""
import io
import os
from pathlib import Path, PurePosixPath
import re
import posixpath
from urllib.parse import unquote
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

from defusedxml import ElementTree as XML
from .domain import AnonymizerError

MAX_INPUT_BYTES = 50 * 1024 * 1024
MAX_ENTRIES = 2000
MAX_EXPANDED_BYTES = 200 * 1024 * 1024
MAX_OUTPUT_BYTES = 100 * 1024 * 1024
CONVERSION_TIMEOUT = 120
SANDBOX = '/usr/bin/sandbox-exec'


def _check_cancelled(cancelled):
    if cancelled():
        raise AnonymizerError('CANCELLED')


def _validate(payload, cancelled):
    if not isinstance(payload, bytes) or len(payload) > MAX_INPUT_BYTES:
        raise AnonymizerError('DOCX_LIMIT')
    inventory = {'metadata': 0, 'comments': 0, 'custom_xml': 0, 'hidden_text': 0,
                 'revisions': 0, 'notes': 0, 'signatures': 0, 'forms': 0}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES or sum(i.file_size for i in entries) > MAX_EXPANDED_BYTES:
                raise AnonymizerError('DOCX_LIMIT')
            seen = set()
            for info in entries:
                _check_cancelled(cancelled)
                name = info.filename
                path = PurePosixPath(name)
                mode = info.external_attr >> 16
                if (name in seen or name.casefold() in seen or '\\' in name or '\x00' in name
                        or path.is_absolute() or '..' in path.parts or ':' in name
                        or any(part in ('', '.') for part in name.rstrip('/').split('/'))
                        or stat.S_ISLNK(mode) or info.flag_bits & 1):
                    raise AnonymizerError('DOCX_UNSAFE_PACKAGE')
                seen.update((name, name.casefold()))
                lower = name.lower()
                if any(part in lower for part in ('vbaproject', 'activex', 'embeddings/', 'customui/', 'vbasignature')):
                    raise AnonymizerError('DOCX_UNSAFE_PACKAGE')
                data = archive.read(info)
                if lower.endswith(('.xml', '.rels')):
                    try:
                        root = XML.fromstring(data)
                    except Exception:
                        raise AnonymizerError('DOCX_UNSAFE_PACKAGE') from None
                    instructions = ''.join(''.join(n.itertext()) for n in root.iter() if n.tag.rsplit('}', 1)[-1] == 'instrText')
                    if re.search(r'\b(DDE[A-Z]*|INCLUDE[A-Z]*|LINK|DATABASE)\b', instructions, re.I):
                        raise AnonymizerError('DOCX_ACTIVE_CONTENT')
                    for node in root.iter():
                        tag = node.tag.rsplit('}', 1)[-1]
                        if tag == 'Relationship':
                            target = node.get('Target', '')
                            relation = node.get('Type', '').lower()
                            if node.get('TargetMode', '').lower() == 'external' or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith(('//', '\\')):
                                raise AnonymizerError('DOCX_EXTERNAL_RELATIONSHIP')
                            # Resolve relationship paths relative to their owning part.
                            owner_dir = posixpath.dirname(posixpath.dirname(name)) if '/_rels/' in name else ''
                            decoded = unquote(target).replace('\\', '/')
                            resolved = posixpath.normpath(posixpath.join(owner_dir, decoded))
                            if decoded.startswith('/') or resolved == '..' or resolved.startswith('../') or ':' in decoded:
                                raise AnonymizerError('DOCX_UNSAFE_PACKAGE')
                            if relation.rsplit('/', 1)[-1] in ('oleobject', 'attachedtemplate', 'afchunk', 'control', 'package'):
                                raise AnonymizerError('DOCX_ACTIVE_CONTENT')
                        if tag in ('object', 'OLEObject', 'altChunk', 'control'):
                            raise AnonymizerError('DOCX_ACTIVE_CONTENT')
                        if tag in ('instrText', 'fldSimple'):
                            instruction = ''.join(node.itertext()) + ' ' + ' '.join(node.attrib.values())
                            if re.search(r'\b(DDE[A-Z]*|INCLUDE[A-Z]*|LINK|DATABASE)\b', instruction, re.I):
                                raise AnonymizerError('DOCX_ACTIVE_CONTENT')
                        if tag in ('sdt', 'ffData'):
                            inventory['forms'] += 1
                        if tag in ('vanish', 'webHidden'):
                            inventory['hidden_text'] += 1
                        if tag in ('ins', 'del', 'moveFrom', 'moveTo'):
                            inventory['revisions'] += 1
                        if tag in ('Override', 'Default') and any(x in node.get('ContentType', '').lower() for x in ('macroenabled', 'vbaproject', 'oleobject', 'activex')):
                            raise AnonymizerError('DOCX_UNSAFE_PACKAGE')
                if lower.startswith('_xmlsignatures/'):
                    inventory['signatures'] += 1
                if lower.startswith('docprops/'):
                    inventory['metadata'] += 1
                if 'comments' in lower:
                    inventory['comments'] += 1
                if lower.startswith('customxml/'):
                    inventory['custom_xml'] += 1
                if lower in ('word/footnotes.xml', 'word/endnotes.xml'):
                    inventory['notes'] += 1
            if 'word/document.xml' not in seen or '[content_types].xml' not in seen:
                raise AnonymizerError('DOCX_INVALID')
    except AnonymizerError:
        raise
    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, NotImplementedError):
        raise AnonymizerError('DOCX_INVALID') from None
    notes = ('DOCX: representación visual de LibreOffice; no garantiza equivalencia tipográfica con Word.',
             'DOCX: solo las páginas visibles pasan a raster/OCR; las partes no visibles quedan excluidas de la salida raster, sin inspección OCR de esas partes.',
             'DOCX: relaciones externas y contenido activo rechazados; enlaces no actualizados.',
             'DOCX: la salida raster no conserva firmas digitales ni formularios interactivos.')
    return notes + tuple(f'DOCX inventario {key}: {value}.' for key, value in inventory.items() if value)


def _find_engine():
    found = shutil.which('soffice')
    if found:
        return found
    standard = Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')
    if standard.is_file():
        return str(standard)
    config = Path(__file__).resolve().parents[2] / '.venv/resources/soffice-path'
    try:
        candidate = Path(config.read_text().strip())
        if candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    except OSError:
        pass
    return None


def _terminate(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        except ProcessLookupError:
            pass


def _convert_docx(payload: bytes, *, cancelled) -> tuple[bytes, tuple[str, ...]]:
    _check_cancelled(cancelled)
    notes = _validate(payload, cancelled)
    engine = _find_engine()
    if not engine:
        raise AnonymizerError('DOCX_ENGINE_UNAVAILABLE')
    if sys.platform != 'darwin' or not Path(SANDBOX).is_file():
        raise AnonymizerError('DOCX_CONTAINMENT_UNAVAILABLE')
    with tempfile.TemporaryDirectory(prefix='anonymizer-office-') as directory:
        root = Path(directory).resolve()
        profile = root / 'profile'
        (profile / 'user').mkdir(parents=True)
        (profile / 'user/registrymodifications.xcu').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop><prop oor:name="DisableActiveContent" oor:op="fuse"><value>true</value></prop></item><item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item></oor:items>''')
        source = root / 'input.docx'
        source.write_bytes(payload)
        # Deny network and all filesystem writes except this disposable tree.
        escaped = str(root).replace('\\', '\\\\').replace('"', '\\"')
        sandbox = root / 'sandbox.sb'
        sandbox.write_text(f'(version 1) (allow default) (deny network*) (deny file-write*) (allow file-write* (subpath "{escaped}") (literal "/dev/null"))')
        try:
            probe = subprocess.run([SANDBOX, '-f', str(sandbox), '/usr/bin/true'], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            raise AnonymizerError('DOCX_CONTAINMENT_FAILED') from None
        if probe.returncode:
            raise AnonymizerError('DOCX_CONTAINMENT_FAILED')
        _check_cancelled(cancelled)
        command = [SANDBOX, '-f', str(sandbox), engine, f'-env:UserInstallation={profile.as_uri()}', '--headless', '--nologo', '--nodefault', '--norestore', '--nofirststartwizard', '--convert-to', 'pdf:writer_pdf_Export', '--outdir', str(root), str(source)]
        # Resource limits apply only to this child, without preexec_fn in a GUI thread.
        launcher = 'import os,resource,sys; resource.setrlimit(resource.RLIMIT_CPU,(120,120)); resource.setrlimit(resource.RLIMIT_FSIZE,(104857600,104857600)); resource.setrlimit(resource.RLIMIT_NOFILE,(256,256)); os.execv(sys.argv[1],sys.argv[1:])'
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT')}
        env.update(HOME=str(root), TMPDIR=str(root), SAL_USE_VCLPLUGIN='svp')
        with (root / 'stdout').open('wb') as stdout, (root / 'stderr').open('wb') as stderr:
            try:
                process = subprocess.Popen([sys.executable, '-c', launcher, *command], cwd=root, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            except OSError:
                raise AnonymizerError('DOCX_CONVERSION_FAILED') from None
            started = time.monotonic()
            try:
                while process.poll() is None:
                    _check_cancelled(cancelled)
                    if time.monotonic() - started > CONVERSION_TIMEOUT:
                        raise AnonymizerError('DOCX_TIMEOUT')
                    time.sleep(.05)
                _check_cancelled(cancelled)
                if process.returncode:
                    raise AnonymizerError('DOCX_CONVERSION_FAILED')
            finally:
                _terminate(process)
        output = root / 'input.pdf'
        try:
            if not output.is_file() or output.stat().st_size > MAX_OUTPUT_BYTES:
                raise AnonymizerError('DOCX_CONVERSION_FAILED')
            result = output.read_bytes()
        except OSError:
            raise AnonymizerError('DOCX_CONVERSION_FAILED') from None
        if not result.startswith(b'%PDF-'):
            raise AnonymizerError('DOCX_CONVERSION_FAILED')
        return result, notes


def convert_docx(payload: bytes, *, cancelled=lambda: False) -> tuple[bytes, tuple[str, ...]]:
    """Convert a bounded private copy; reject unsupported or unsafe content."""
    try:
        return _convert_docx(payload, cancelled=cancelled)
    except AnonymizerError:
        raise
    except (OSError, subprocess.SubprocessError, ValueError):
        raise AnonymizerError('DOCX_CONVERSION_FAILED') from None
