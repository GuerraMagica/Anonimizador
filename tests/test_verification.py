from dataclasses import replace
import unittest

from helpers import finding, reviewed
from local_anonymizer.domain import (
    Action, Category, Decision, Disposition, ResidualDecision,
)
from local_anonymizer.transform import build_preview
from local_anonymizer.verification import verify_preview


class SpanDetector:
    """Deterministic protocol fixture, not a PII detector or NER benchmark."""
    fingerprint = 'synthetic-v1'

    def __init__(self, spans=()):
        self.spans = spans

    def analyze(self, text, session_id):
        return tuple(finding(f'residual-{i}', start, end, category,
                             session_id=session_id, provenance=('test',))
                     for i, (start, end, category) in enumerate(self.spans))


class VerificationTests(unittest.TestCase):
    def verify(self, review, detector=None, rejections=()):
        return verify_preview(review, build_preview(review),
                              detector or SpanDetector(), rejections)

    def test_reviewed_transformation_passes_and_binds_digest_and_revision(self):
        r = reviewed('Ana', (finding('a', 0, 3),), revision=7)
        p = build_preview(r)
        result = verify_preview(r, p, SpanDetector())
        self.assertTrue(result.ok)
        self.assertEqual(result.preview_sha256, p.sha256)
        self.assertEqual(result.review_revision, 7)

    def test_selected_value_elsewhere_blocks_export(self):
        result = self.verify(reviewed('Ana y Ana', (finding('a', 0, 3),)))
        self.assertFalse(result.ok)
        self.assertIn('SELECTED_VALUE_REMAINS', result.issues)

    def test_joined_segments_cannot_recreate_another_selected_value(self):
        fs = (finding('a', 1, 2, Category.CONFIDENCIAL), finding('b', 5, 8))
        ds = tuple(Decision(f.id, Disposition.ACCEPT, Action.REDACT) for f in fs)
        r = reviewed('A[na Ana', fs, ds)
        self.assertEqual(build_preview(r).text, 'Ana ')
        self.assertIn('SELECTED_VALUE_REMAINS', self.verify(r).issues)

    def test_human_confirmation_is_required_even_without_detections(self):
        result = self.verify(reviewed('texto', confirmed=False))
        self.assertFalse(result.ok)
        self.assertIn('HUMAN_REVIEW_REQUIRED', result.issues)

    def test_preview_text_or_provenance_tampering_is_blocked(self):
        r = reviewed('Ana', (finding('a', 0, 3),))
        p = build_preview(r)
        for tampered in (replace(p, text='Ana'), replace(p, selected_values=()),
                         replace(p, segments=()), replace(p, review_revision=1)):
            with self.subTest(preview=tampered):
                result = verify_preview(r, tampered, SpanDetector())
                self.assertFalse(result.ok)
                self.assertIn('PREVIEW_MISMATCH', result.issues)

    def test_new_residual_requires_explicit_rejection(self):
        r = reviewed('Texto')
        detector = SpanDetector(((0, 5, Category.PROYECTO),))
        pending = self.verify(r, detector)
        self.assertFalse(pending.ok)
        self.assertEqual(len(pending.residuals), 1)
        decision = ResidualDecision(pending.residuals[0].key)
        self.assertTrue(self.verify(r, detector, (decision,)).ok)

    def test_false_positive_inside_generated_label_can_be_rejected(self):
        r = reviewed('Ana', (finding('a', 0, 3),))
        detector = SpanDetector(((0, 11, Category.PERSONA),))
        pending = self.verify(r, detector)
        rejection = ResidualDecision(pending.residuals[0].key)
        self.assertTrue(self.verify(r, detector, (rejection,)).ok)

    def test_old_residual_rejection_expires_when_any_key_field_changes(self):
        r = reviewed('Texto')
        detector = SpanDetector(((0, 5, Category.PROYECTO),))
        key = self.verify(r, detector).residuals[0].key
        for changed in (replace(key, session_id='old'), replace(key, review_revision=1),
                        replace(key, preview_sha256='0' * 64),
                        replace(key, detector_fingerprint='old'), replace(key, end=4),
                        replace(key, category=Category.PERSONA),
                        replace(key, provenance=('other',))):
            with self.subTest(key=changed):
                self.assertFalse(self.verify(r, detector, (ResidualDecision(changed),)).ok)

    def test_review_revision_change_invalidates_rejection_even_if_output_same(self):
        r = reviewed('Texto')
        detector = SpanDetector(((0, 5, Category.PROYECTO),))
        decision = ResidualDecision(self.verify(r, detector).residuals[0].key)
        self.assertFalse(self.verify(replace(r, revision=1), detector, (decision,)).ok)

    def test_rejected_original_is_inherited_only_at_exact_preserved_position(self):
        f = finding('a', 0, 3, provenance=('test',))
        r = reviewed('Ana Ana', (f,), (Decision('a', Disposition.REJECT),))
        detector = SpanDetector(((0, 3, Category.PERSONA), (4, 7, Category.PERSONA)))
        result = self.verify(r, detector)
        self.assertFalse(result.ok)
        self.assertEqual([c.finding.start for c in result.residuals], [4])

    def test_rejected_original_can_move_after_a_label_but_needs_same_provenance(self):
        fs = (finding('a', 0, 3), finding('b', 6, 9, provenance=('test',)))
        ds = (Decision('a', Disposition.ACCEPT), Decision('b', Disposition.REJECT))
        r = reviewed('Ana y Sol', fs, ds)
        self.assertTrue(self.verify(r, SpanDetector(((14, 17, Category.PERSONA),))).ok)
        r2 = replace(r, findings=(fs[0], replace(fs[1], provenance=('other',))))
        self.assertFalse(self.verify(r2, SpanDetector(((14, 17, Category.PERSONA),))).ok)

    def test_rejection_crossing_deleted_text_is_not_inherited(self):
        fs = (finding('whole', 0, 5, provenance=('test',)),
              finding('bracket', 2, 3, Category.CONFIDENCIAL))
        ds = (Decision('whole', Disposition.REJECT),
              Decision('bracket', Disposition.ACCEPT, Action.REDACT))
        r = reviewed('Jo[se', fs, ds)
        self.assertEqual(build_preview(r).text, 'Jose')
        self.assertFalse(self.verify(r, SpanDetector(((0, 4, Category.PERSONA),))).ok)

    def test_rejection_crossing_generated_and_preserved_text_is_not_inherited(self):
        r = reviewed('x Ana z', (finding('a', 2, 5),))
        result = self.verify(r, SpanDetector(((1, 14, Category.PERSONA),)))
        self.assertFalse(result.ok)
        self.assertEqual(len(result.residuals), 1)

    def test_detector_error_is_sanitized_and_blocks(self):
        class Broken(SpanDetector):
            def analyze(self, text, session_id):
                raise RuntimeError('SENTINEL secret@synthetic.invalid')
        result = self.verify(reviewed('SENTINEL'), Broken())
        self.assertFalse(result.ok)
        self.assertEqual(result.issues, ('ANALYSIS_FAILED',))
        self.assertNotIn('SENTINEL', repr(result))

    def test_detector_change_during_analysis_blocks(self):
        class Changing(SpanDetector):
            def analyze(self, text, session_id):
                self.fingerprint = 'synthetic-v2'
                return ()
        result = self.verify(reviewed('Texto'), Changing())
        self.assertFalse(result.ok)
        self.assertIn('DETECTOR_CHANGED', result.issues)

    def test_malformed_detector_result_blocks(self):
        class Wrong(SpanDetector):
            def analyze(self, text, session_id):
                return (finding('bad', 0, 100, session_id=session_id),)
        self.assertIn('ANALYSIS_FAILED', self.verify(reviewed('Texto'), Wrong()).issues)


if __name__ == '__main__':
    unittest.main()
