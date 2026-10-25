"""Explicit Spanish local recognizers; no AnalyzerEngine auto-loading or cloud.

Presidio recognizers run individually so conflicting spans survive. Spanish NER
comes directly from the approved spaCy model, including ORG (not default mapping).
"""
from hashlib import sha256
from importlib import metadata, util
import json
import logging
from pathlib import Path
import re
from uuid import uuid4

from .domain import AnonymizerError, Category, Confidentiality, Document, Finding
from .ingest import MAX_CHARACTERS

# At most one replacement per source character; counters cannot exceed the
# input character count plus labels already reserved in that same source.
MAX_LABEL_CHARACTERS = max(len(c.value) for c in Category) + 1 + max(3, len(str(2 * MAX_CHARACTERS)))
MAX_ANALYSIS_CHARACTERS = MAX_CHARACTERS * max(MAX_LABEL_CHARACTERS, len("[ELIMINADO]"))


NER_CATEGORIES = {'PER': Category.PERSONA, 'ORG': Category.ORGANIZACION,
                  'LOC': Category.UBICACION}


def default_model_path() -> Path:
    spec = util.find_spec('es_core_news_sm')
    if spec is None or spec.origin is None:
        raise AnonymizerError('MODEL_UNAVAILABLE')
    return Path(spec.origin).parent / 'es_core_news_sm-3.8.0'


def literal_findings(document: Document, terms: tuple[tuple[str, Category], ...]):
    if (not isinstance(terms, tuple) or len(terms) > 1000
            or any(not isinstance(term, str) or not 1 <= len(term) <= 1000
                   or not term.strip() or not isinstance(cat, Category) for term, cat in terms)):
        raise AnonymizerError('INVALID_TERMS')
    result = []
    seen = set()
    for term, category in terms:
        # Literal, case-sensitive. A word character at either end requires a
        # Unicode word boundary there; punctuation is literal too, never regex.
        pattern = (r'(?<!\w)' if re.match(r'\w', term[0]) else '')
        pattern += re.escape(term)
        pattern += r'(?!\w)' if re.match(r'\w', term[-1]) else ''
        for m in re.finditer(pattern, document.text):
            key = (m.start(), m.end(), category)
            if key not in seen:
                seen.add(key)
                result.append(Finding(uuid4().hex, document.session_id, *m.span(), category,
                                      Confidentiality.CUSTOM, ('literal:v1',)))
    return tuple(sorted(result, key=lambda f: (f.start, f.end, f.category)))


class _PrivateRecognizerLogs(logging.Filter):
    """A recognizer warning (including a swallowed timeout) fails coverage closed."""
    def filter(self, record):
        if record.levelno >= logging.WARNING:
            raise AnonymizerError('ANALYSIS_FAILED')
        return False


class LocalDetector:
    def __init__(self, model_path: Path | None, *, structured_only=False):
        model_path = Path(model_path) if model_path is not None else None
        if not structured_only and not (model_path and model_path.is_dir() and (model_path / 'config.cfg').is_file()):
            raise AnonymizerError('MODEL_UNAVAILABLE')
        try:
            import spacy
            import tldextract
            import regex
            from presidio_analyzer import Pattern
            from presidio_analyzer.predefined_recognizers import (
                EmailRecognizer, PhoneRecognizer, EsNifRecognizer, EsNieRecognizer,
                EsPassportRecognizer, IbanRecognizer, DateRecognizer)

            # No DNS, HTTP, user cache or first-use suffix download.
            offline_tlds = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None,
                                                fallback_to_snapshot=True)
            class OfflineEmail(EmailRecognizer):
                def validate_result(self, pattern_text):
                    return offline_tlds(pattern_text).fqdn != ''

            self._recognizers = (
                (OfflineEmail(supported_language='es'), Category.CORREO, 'presidio:email'),
                (PhoneRecognizer(supported_language='es', supported_regions=('ES',)),
                 Category.TELEFONO, 'presidio:phone:ES'),
                (EsNifRecognizer(patterns=[Pattern('NIF8',r'\b[0-9]{8}-?[A-Z]\b',0.5)]),
                 Category.DOCUMENTO, 'presidio:nif:ES'),
                (EsNieRecognizer(patterns=[Pattern('NIE7',r'\b[X-Z][0-9]{7}-?[A-Z]\b',0.5)]),
                 Category.DOCUMENTO, 'presidio:nie:ES'),
                (EsPassportRecognizer(), Category.DOCUMENTO, 'presidio:passport:ES'),
                (IbanRecognizer(supported_language='es', regex_flags=regex.IGNORECASE),
                 Category.IBAN, 'presidio:iban:ES'),
                (DateRecognizer(supported_language='es',patterns=[
                    Pattern('DMY',r'\b(?:0?[1-9]|[12][0-9]|3[01])[/.-](?:0?[1-9]|1[0-2])[/.-](?:[0-9]{4}|[0-9]{2})\b',0.6),
                    Pattern('ISO',r'\b[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])\b',0.6),
                    Pattern('Spanish',r'\b(?:0?[1-9]|[12][0-9]|3[01]) de (?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre) de [0-9]{4}\b',0.6),
                ]), Category.FECHA, 'presidio:date:es'),
            )
            self._nlp = None
            if not structured_only:
                self._nlp = spacy.load(model_path, exclude=['parser', 'senter', 'morphologizer',
                                                           'attribute_ruler', 'lemmatizer'])
                if (self._nlp.meta.get('lang') != 'es' or self._nlp.meta.get('version') != '3.8.0'
                        or not set(NER_CATEGORIES) <= set(self._nlp.get_pipe('ner').labels)):
                    raise ValueError('model')
                self._nlp.max_length = MAX_ANALYSIS_CHARACTERS
            versions = {p: metadata.version(p) for p in ('spacy','presidio-analyzer','phonenumbers','tldextract')}
            digest = sha256(json.dumps({'versions':versions, 'analysis_limit':MAX_ANALYSIS_CHARACTERS, 'adapter':'v2', 'structured_only': structured_only, 'rules_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}, sort_keys=True).encode())
            for path in (sorted(model_path.rglob('*')) if not structured_only else ()):
                if path.is_file() and '__pycache__' not in path.parts:
                    digest.update(path.relative_to(model_path).as_posix().encode())
                    with path.open('rb') as f:
                        for block in iter(lambda: f.read(65536), b''):digest.update(block)
            self._fingerprint = 'local-es:v2:' + digest.hexdigest()
        except Exception:
            raise AnonymizerError('MODEL_UNAVAILABLE') from None

    @property
    def fingerprint(self):
        return self._fingerprint

    def analyze(self, text: str, session_id: str) -> tuple[Finding, ...]:
        if not isinstance(text, str) or len(text) > MAX_ANALYSIS_CHARACTERS:
            raise AnonymizerError('ANALYSIS_LIMIT')
        logger = logging.getLogger('presidio-analyzer')
        privacy_filter = _PrivateRecognizerLogs()
        logger.addFilter(privacy_filter)
        try:
            import phonenumbers
            findings = []
            for recognizer, category, provenance in self._recognizers:
                for result in recognizer.analyze(text, recognizer.supported_entities):
                    value = text[result.start:result.end]
                    if category == Category.TELEFONO:
                        number = phonenumbers.parse(value, 'ES')
                        if phonenumbers.region_code_for_number(number) != 'ES':continue
                    if category == Category.IBAN and not re.fullmatch(r'ES[0-9]{2}(?:[ -]?[0-9]{4}){5}', value, re.I):
                        continue
                    findings.append(Finding(uuid4().hex, session_id, result.start,result.end,
                                            category,Confidentiality.PII,(provenance,),result.score))
            for ent in (self._nlp(text).ents if self._nlp is not None else ()):
                if ent.label_ in NER_CATEGORIES:
                    findings.append(Finding(uuid4().hex, session_id, ent.start_char,ent.end_char,
                                            NER_CATEGORIES[ent.label_],Confidentiality.PII,
                                            ('spacy:es_core_news_sm:3.8.0:' + ent.label_,)))
            return tuple(sorted(findings,key=lambda f:(f.start,f.end,f.category,f.provenance)))
        except Exception:
            raise AnonymizerError('ANALYSIS_FAILED') from None
        finally:
            logger.removeFilter(privacy_filter)
