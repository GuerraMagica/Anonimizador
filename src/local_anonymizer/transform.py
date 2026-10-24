"""Reviewed interval transformations and exact source provenance."""

import hashlib

from .domain import (
    Action, AnonymizerError, Decision, Disposition, Finding, Preview, Review, Segment,
)


def _selected(review: Review) -> list[tuple[Finding, Decision, str]]:
    if review.coverage_complete is not True:
        raise AnonymizerError('COVERAGE_INCOMPLETE')
    if (not isinstance(review.findings, tuple) or not isinstance(review.decisions, tuple)
            or review.revision < 0):
        raise AnonymizerError('INVALID_REVIEW')
    findings = {f.id: f for f in review.findings}
    decisions = {d.finding_id: d for d in review.decisions}
    if len(findings) != len(review.findings):
        raise AnonymizerError('INVALID_FINDING')
    if (len(decisions) != len(review.decisions) or findings.keys() != decisions.keys()
            or any(not isinstance(d.disposition, Disposition)
                   or not isinstance(d.action, Action)
                   or d.disposition == Disposition.PENDING for d in review.decisions)):
        raise AnonymizerError('REVIEW_INCOMPLETE')
    selected = []
    for f in sorted(review.findings, key=lambda f: (f.start, f.end, f.category, f.id)):
        if f.session_id != review.document.session_id or f.end > len(review.document.text):
            raise AnonymizerError('INVALID_FINDING')
        d = decisions[f.id]
        if d.disposition == Disposition.REJECT:
            continue
        explicit_group = d.group_id if d.group_id is not None else f.group_id
        value = review.document.text[f.start:f.end]
        group = (f'explicit:{f.category}:{explicit_group}' if explicit_group is not None
                 else f'auto:{f.category}:{value}')
        if selected and f.start < selected[-1][0].end:
            prev, prev_decision, prev_group = selected[-1]
            if ((f.start, f.end, f.category, d.action, group)
                    == (prev.start, prev.end, prev.category, prev_decision.action, prev_group)):
                # Both original records and their provenance remain in Review.
                continue
            raise AnonymizerError('REVIEW_CONFLICT')
        selected.append((f, d, group))
    return selected


def build_preview(review: Review) -> Preview:
    selected = _selected(review)
    source = review.document.text
    values = tuple(dict.fromkeys(source[f.start:f.end] for f, _, _ in selected))
    marker = '' if any(value in '[ELIMINADO]' for value in values) else '[ELIMINADO]'
    labels: dict[str, str] = {}
    counters: dict[str, int] = {}
    parts: list[str] = []
    segments: list[Segment] = []
    source_position = 0
    output_position = 0

    def append(text: str, start: int, end: int, finding_id: str | None = None):
        nonlocal output_position
        parts.append(text)
        segments.append(Segment(output_position, output_position + len(text),
                                start, end, finding_id))
        output_position += len(text)

    for f, decision, group in selected:
        if f.start > source_position:
            append(source[source_position:f.start], source_position, f.start)
        if decision.action == Action.REDACT:
            replacement = marker
        else:
            if group not in labels:
                counter = counters.get(f.category, 0) + 1
                label = f'{f.category}_{counter:03d}'
                while label in source:
                    counter += 1
                    label = f'{f.category}_{counter:03d}'
                counters[f.category] = counter
                labels[group] = label
            replacement = labels[group]
        append(replacement, f.start, f.end, f.id)
        source_position = f.end
    if source_position < len(source):
        append(source[source_position:], source_position, len(source))
    text = ''.join(parts)
    return Preview(text, tuple(segments), values, tuple(labels.items()), review.revision,
                   hashlib.sha256(text.encode('utf-8')).hexdigest())


def map_output_span(preview: Preview, start: int, end: int) -> tuple[Segment, ...]:
    if not 0 <= start < end <= len(preview.text):
        raise AnonymizerError('INVALID_OUTPUT_SPAN')
    return tuple(s for s in preview.segments
                 if (s.output_start < end and s.output_end > start)
                 or (s.output_start == s.output_end and start < s.output_start < end))
