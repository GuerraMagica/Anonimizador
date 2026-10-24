"""Optional output audit with a closed schema and no original content."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .domain import AnonymizerError, Category, Disposition, Receipt
from .export import _publish_bytes

_VERSION_KEYS = {'application', 'python', 'spacy', 'presidio_analyzer', 'pyside6', 'model'}
_COUNT_KEYS = {c.value for c in Category} | {d.value for d in Disposition}
_CHECKS = {'status': 'technical_checks_passed', 'scope': 'text_only',
           'contextual_risk_review_required': True}


def _validate(report: dict):
    if (not isinstance(report, dict) or set(report) != {
            'schema_version', 'generated_at', 'output_sha256', 'counts', 'versions', 'verification'}
            or report['schema_version'] != 1 or report['verification'] != _CHECKS
            or not isinstance(report['output_sha256'], str)
            or not re.fullmatch(r'[a-f0-9]{64}', report['output_sha256'])):
        raise AnonymizerError('REPORT_INVALID')
    try:
        date = datetime.fromisoformat(report['generated_at'])
        if date.tzinfo is None or len(report['generated_at']) > 40:
            raise ValueError
        counts, versions = report['counts'], report['versions']
        if (not isinstance(counts, dict) or not isinstance(versions, dict)
                or set(counts) - _COUNT_KEYS or set(versions) - _VERSION_KEYS
                or any(type(v) is not int or not 0 <= v <= 1_000_000 for v in counts.values())
                or counts.get('PENDING', 0) != 0
                or any(not isinstance(v, str) or len(v) > 64
                       or not re.fullmatch(r'\d+(?:\.\d+)+(?:[a-zA-Z0-9.+-]*)', v)
                       for v in versions.values())):
            raise ValueError
    except (ValueError, TypeError):
        raise AnonymizerError('REPORT_INVALID') from None


def build_report(receipt: Receipt, counts: dict[str, int], versions: dict[str, str]) -> dict:
    result = {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
              'output_sha256': receipt.sha256, 'counts': dict(counts),
              'versions': dict(versions), 'verification': dict(_CHECKS)}
    _validate(result)
    return result


def save_report(report: dict, destination: Path) -> Receipt:
    _validate(report)
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    return _publish_bytes(payload, destination)
