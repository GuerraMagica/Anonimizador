"""UI-independent owner of one review and one cooperative asynchronous job.

All mutations run on the owning UI thread. Workers receive immutable snapshots;
they never mutate Session. Cancellation keeps the job occupied until it exits.
"""
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from .domain import (AnonymizerError, Decision, Disposition, Document, Finding,
                     ResidualDecision, Review, Verification)
from .ingest import load_document
from .transform import build_preview
from .verification import verify_preview


@dataclass(frozen=True, slots=True)
class JobToken:
    session_id: str
    revision: int
    job_id: str


class Session:
    def __init__(self):
        self.review = None
        self.current_preview = None
        self.verification = None
        self.rejections = ()
        self._active = None
        self.cancel_pending = False

    @property
    def busy(self):
        return self._active is not None

    @property
    def can_export(self):
        r, p, v = self.review, self.current_preview, self.verification
        return bool(not self.busy and r and p and v and r.confirmed and v.ok
                    and not v.issues and not v.residuals
                    and v.session_id == r.document.session_id
                    and v.review_revision == r.revision
                    and v.preview_sha256 == p.sha256)

    def _require_review(self):
        if self.review is None:
            raise AnonymizerError('NO_DOCUMENT')
        return self.review

    def _invalidate(self):
        self.current_preview = None
        self.verification = None
        self.rejections = ()

    def _replace_review(self, **changes):
        r = self._require_review()
        self.review = replace(r, revision=r.revision + 1, confirmed=False, **changes)
        self._invalidate()

    def load(self, source: Document | Path):
        doc = source if isinstance(source, Document) else load_document(source)
        if self.busy:
            self.cancel_pending = True
        self.review = Review(doc, (), ())
        self._invalidate()

    def set_findings(self, findings: tuple[Finding, ...], *, coverage_complete=True):
        r = self._require_review()
        if (not isinstance(findings, tuple) or len({f.id for f in findings}) != len(findings)
                or any(f.session_id != r.document.session_id
                       or f.end > len(r.document.text) for f in findings)):
            raise AnonymizerError('INVALID_FINDINGS')
        self._replace_review(findings=findings,
                             decisions=tuple(Decision(f.id, Disposition.PENDING) for f in findings),
                             coverage_complete=coverage_complete is True)

    def set_decisions(self, decisions: tuple[Decision, ...]):
        r = self._require_review()
        if (not isinstance(decisions, tuple)
                or len(decisions) != len(r.findings)
                or {d.finding_id for d in decisions} != {f.id for f in r.findings}
                or any(not isinstance(d.disposition, Disposition) for d in decisions)):
            raise AnonymizerError('INVALID_DECISIONS')
        self._replace_review(decisions=decisions)

    def preview(self):
        if self.busy:
            raise AnonymizerError('JOB_ACTIVE')
        self.current_preview = build_preview(self._require_review())
        self.verification = None
        return self.current_preview

    def confirm(self):
        if self.busy:
            raise AnonymizerError('JOB_ACTIVE')
        r = self._require_review()
        if self.current_preview is None or build_preview(r) != self.current_preview:
            raise AnonymizerError('PREVIEW_REQUIRED')
        self.review = replace(r, confirmed=True)
        self.verification = None

    def begin_job(self, *, verification=False):
        if self.busy:
            raise AnonymizerError('JOB_ACTIVE')
        r = self._require_review()
        if verification:
            if not r.confirmed or self.current_preview is None:
                raise AnonymizerError('CONFIRMATION_REQUIRED')
            self.verification = None
        else:
            self._replace_review(coverage_complete=False)
            r = self.review
        token = JobToken(r.document.session_id, r.revision, uuid4().hex)
        self._active = token
        self.cancel_pending = False
        return token

    def finish_job(self, token):
        if token != self._active:
            return False
        valid = bool(not self.cancel_pending and self.review
                     and token.session_id == self.review.document.session_id
                     and token.revision == self.review.revision)
        self._active = None
        self.cancel_pending = False
        return valid

    def accept_result(self, token, findings):
        if not self.finish_job(token):
            return False
        self.set_findings(findings)
        return True

    def accept_verification(self, token, result: Verification):
        if not self.finish_job(token):
            return False
        r, p = self.review, self.current_preview
        if (p is None or not r.confirmed or result.session_id != r.document.session_id
                or result.review_revision != r.revision or result.preview_sha256 != p.sha256):
            return False
        self.verification = result
        return True

    def verify(self, detector):
        token = self.begin_job(verification=True)
        try:
            result = verify_preview(self.review, self.current_preview, detector, self.rejections)
        except Exception:
            self.finish_job(token)
            raise AnonymizerError('ANALYSIS_FAILED') from None
        if not self.accept_verification(token, result):
            raise AnonymizerError('STALE_RESULT')
        return result

    def reject_residuals(self, keys):
        if self.busy or self.verification is None:
            raise AnonymizerError('VERIFICATION_REQUIRED')
        valid = {c.key for c in self.verification.residuals}
        if not set(keys) <= valid:
            raise AnonymizerError('INVALID_RESIDUAL_DECISION')
        self.rejections += tuple(ResidualDecision(k) for k in keys)
        self.verification = None

    def cancel(self):
        if self.busy:
            self.cancel_pending = True
        if self.review:
            self._replace_review()
        else:
            self._invalidate()

    def close(self):
        if self.busy:
            self.cancel_pending = True
        self.review = None
        self._invalidate()
