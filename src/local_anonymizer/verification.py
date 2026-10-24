"""Post-transformation checks; these do not certify contextual anonymity."""

import re
from typing import Protocol

from .domain import (
    AnonymizerError, Disposition, Finding, Preview, ResidualCandidate,
    ResidualDecision, ResidualKey, Review, Verification,
)
from .transform import build_preview, map_output_span


class Detector(Protocol):
    @property
    def fingerprint(self) -> str: ...

    def analyze(self, text: str, session_id: str) -> tuple[Finding, ...]: ...


def _original_rejected(review: Review, preview: Preview, candidate: Finding) -> bool:
    segments = map_output_span(preview, candidate.start, candidate.end)
    if not segments or any(s.finding_id is not None for s in segments):
        return False
    output_position = candidate.start
    source_start = None
    source_position = None
    for s in segments:
        start = max(candidate.start, s.output_start)
        end = min(candidate.end, s.output_end)
        source_piece_start = s.source_start + start - s.output_start
        if start != output_position or (source_position is not None
                                        and source_piece_start != source_position):
            return False
        if source_start is None:
            source_start = source_piece_start
        source_position = source_piece_start + end - start
        output_position = end
    if output_position != candidate.end:
        return False
    rejected = {d.finding_id for d in review.decisions if d.disposition == Disposition.REJECT}
    return any(f.id in rejected and f.start == source_start and f.end == source_position
               and f.category == candidate.category and f.provenance == candidate.provenance
               for f in review.findings)


def verify_preview(review: Review, preview: Preview, detector: Detector,
                   rejections: tuple[ResidualDecision, ...] = ()) -> Verification:
    fingerprint = 'unavailable'

    def result(issues: tuple[str, ...], residuals=()) -> Verification:
        return Verification(review.document.session_id, review.revision, preview.sha256,
                            fingerprint, not issues, issues, tuple(residuals))

    if review.confirmed is not True:
        return result(('HUMAN_REVIEW_REQUIRED',))
    try:
        expected = build_preview(review)
    except AnonymizerError as error:
        return result((error.code,))
    if preview != expected:
        return result(('PREVIEW_MISMATCH',))
    issues = []
    if any(value in preview.text for value in preview.selected_values):
        issues.append('SELECTED_VALUE_REMAINS')
    try:
        fingerprint = detector.fingerprint
        if not isinstance(fingerprint, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', fingerprint):
            fingerprint = 'unavailable'
            return result(tuple(issues + ['ANALYSIS_FAILED']))
        candidates = detector.analyze(preview.text, review.document.session_id)
        if not isinstance(candidates, tuple) or any(
                not isinstance(c, Finding) or c.end > len(preview.text)
                or c.session_id != review.document.session_id for c in candidates):
            return result(tuple(issues + ['ANALYSIS_FAILED']))
        if detector.fingerprint != fingerprint:
            return result(tuple(issues + ['DETECTOR_CHANGED']))
    except Exception:
        return result(tuple(issues + ['ANALYSIS_FAILED']))
    pending = []
    rejected_keys = {d.key for d in rejections}
    for candidate in candidates:
        key = ResidualKey(review.document.session_id, review.revision, preview.sha256,
                          fingerprint, candidate.start, candidate.end,
                          candidate.category, candidate.provenance)
        if key in rejected_keys or _original_rejected(review, preview, candidate):
            continue
        pending.append(ResidualCandidate(candidate, key))
    if pending:
        issues.append('RESIDUAL_REVIEW_REQUIRED')
    return result(tuple(issues), pending)
