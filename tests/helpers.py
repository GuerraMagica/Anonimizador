"""Synthetic fixtures shared by core tests; no production data."""

from local_anonymizer.domain import (
    Action, Category, Confidentiality, Decision, Disposition, Document,
    FileIdentity, Finding, Review,
)
from pathlib import Path


def document(text):
    return Document('synthetic-session', 0, Path('/synthetic/document.txt'),
                    FileIdentity(0, 0), text, '0' * 64)


def finding(id, start, end, category=Category.PERSONA, *, session_id='synthetic-session',
            provenance=('manual',), group_id=None):
    return Finding(id, session_id, start, end, category, Confidentiality.PII,
                   provenance, group_id=group_id)


def reviewed(text, findings=(), decisions=None, *, confirmed=True, revision=0,
             coverage_complete=True):
    if decisions is None:
        decisions = tuple(Decision(f.id, Disposition.ACCEPT, Action.LABEL)
                          for f in findings)
    return Review(document(text), tuple(findings), tuple(decisions), revision,
                  coverage_complete, confirmed)
