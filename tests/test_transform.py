from dataclasses import replace
import hashlib
import unittest

from helpers import finding, reviewed
from local_anonymizer.domain import (
    Action, AnonymizerError, Category, Decision, Disposition,
)
from local_anonymizer.transform import build_preview, map_output_span


class TransformTests(unittest.TestCase):
    def assert_blocked(self, review, code):
        with self.assertRaises(AnonymizerError) as caught:
            build_preview(review)
        self.assertEqual(caught.exception.code, code)

    def test_same_group_has_same_label(self):
        review = reviewed('Ana y Ana', (finding('a', 0, 3), finding('b', 6, 9)))
        result = build_preview(review)
        self.assertEqual(result.text, 'PERSONA_001 y PERSONA_001')
        self.assertEqual(review.document.text, 'Ana y Ana')
        self.assertEqual(result.sha256, hashlib.sha256(result.text.encode()).hexdigest())

    def test_explicit_distinct_groups_separate_equal_names(self):
        fs = (finding('a', 0, 3), finding('b', 6, 9))
        ds = (Decision('a', Disposition.ACCEPT, group_id='actor-a'),
              Decision('b', Disposition.ACCEPT, group_id='actor-b'))
        self.assertEqual(build_preview(reviewed('Ana y Ana', fs, ds)).text,
                         'PERSONA_001 y PERSONA_002')

    def test_explicit_aliases_share_label_and_order_is_source_order(self):
        fs = (finding('b', 6, 11), finding('a', 0, 3))
        ds = (Decision('a', Disposition.ACCEPT, group_id='same'),
              Decision('b', Disposition.ACCEPT, group_id='same'))
        self.assertEqual(build_preview(reviewed('Ana y Anita', fs, ds)).text,
                         'PERSONA_001 y PERSONA_001')

    def test_categories_do_not_share_counters_or_groups(self):
        fs = (finding('a', 0, 3), finding('b', 6, 9, Category.PROYECTO))
        self.assertEqual(build_preview(reviewed('Ana y Ana', fs)).text,
                         'PERSONA_001 y PROYECTO_001')

    def test_existing_source_labels_are_reserved(self):
        fs = (finding('a', 12, 15),)
        self.assertEqual(build_preview(reviewed('PERSONA_001 Ana', fs)).text,
                         'PERSONA_001 PERSONA_002')

    def test_redaction_uses_marker(self):
        f = finding('a', 0, 3)
        ds = (Decision('a', Disposition.ACCEPT, Action.REDACT),)
        self.assertEqual(build_preview(reviewed('Ana', (f,), ds)).text, '[ELIMINADO]')

    def test_redaction_is_empty_if_marker_reintroduces_selected_value(self):
        f = finding('a', 1, 2)
        ds = (Decision('a', Disposition.ACCEPT, Action.REDACT),)
        result = build_preview(reviewed('xEy', (f,), ds))
        self.assertEqual(result.text, 'xy')
        self.assertEqual(result.selected_values, ('E',))
        self.assertEqual(result.segments[1].output_start, result.segments[1].output_end)

    def test_unselected_occurrence_is_not_globally_replaced(self):
        result = build_preview(reviewed('Ana y Ana', (finding('a', 0, 3),)))
        self.assertEqual(result.text, 'PERSONA_001 y Ana')

    def test_rejected_finding_is_preserved_and_not_selected_for_removal(self):
        f = finding('a', 0, 3)
        ds = (Decision('a', Disposition.REJECT),)
        result = build_preview(reviewed('Ana', (f,), ds))
        self.assertEqual(result.text, 'Ana')
        self.assertEqual(result.selected_values, ())

    def test_accepted_duplicates_with_same_decisions_are_not_applied_twice(self):
        fs = (finding('a', 0, 3, provenance=('ner',)),
              finding('b', 0, 3, provenance=('manual',)))
        review = reviewed('Ana', fs)
        self.assertEqual(build_preview(review).text, 'PERSONA_001')
        self.assertEqual(review.findings[1].provenance, ('manual',))

    def test_overlapping_accepted_findings_are_blocked(self):
        fs = (finding('a', 0, 3), finding('b', 1, 3, Category.PROYECTO))
        self.assert_blocked(reviewed('Ana', fs), 'REVIEW_CONFLICT')

    def test_duplicate_intervals_with_conflicting_actions_are_blocked(self):
        fs = (finding('a', 0, 3), finding('b', 0, 3))
        ds = (Decision('a', Disposition.ACCEPT),
              Decision('b', Disposition.ACCEPT, Action.REDACT))
        self.assert_blocked(reviewed('Ana', fs, ds), 'REVIEW_CONFLICT')

    def test_pending_missing_and_extra_decisions_are_blocked(self):
        f = finding('a', 0, 3)
        for ds in ((), (Decision('a', Disposition.PENDING),),
                   (Decision('a', Disposition.ACCEPT), Decision('other', Disposition.REJECT))):
            with self.subTest(decisions=ds):
                self.assert_blocked(reviewed('Ana', (f,), ds), 'REVIEW_INCOMPLETE')

    def test_incomplete_coverage_is_blocked(self):
        self.assert_blocked(reviewed('Ana', coverage_complete=False), 'COVERAGE_INCOMPLETE')

    def test_wrong_session_out_of_bounds_and_duplicate_ids_are_blocked(self):
        for fs in ((finding('a', 0, 3, session_id='old'),),
                   (finding('a', 0, 4),),
                   (finding('a', 0, 1), finding('a', 1, 2))):
            with self.subTest(findings=fs):
                with self.assertRaises(AnonymizerError):
                    build_preview(reviewed('Ana', fs))

    def test_preview_does_not_require_human_confirmation_yet(self):
        result = build_preview(reviewed('Ana', (finding('a', 0, 3),), confirmed=False))
        self.assertEqual(result.text, 'PERSONA_001')

    def test_provenance_preserves_unicode_and_crlf_positions(self):
        text = '😀 Jose\u0301\r\nAna!'
        result = build_preview(reviewed(text, (finding('a', 9, 12),)))
        self.assertEqual(result.text, '😀 Jose\u0301\r\nPERSONA_001!')
        conserved = [s for s in result.segments if s.finding_id is None]
        for s in conserved:
            self.assertEqual(result.text[s.output_start:s.output_end],
                             text[s.source_start:s.source_end])
        span = map_output_span(result, 9, 20)
        self.assertEqual(len(span), 1)
        self.assertEqual((span[0].source_start, span[0].source_end), (9, 12))

    def test_map_crossing_a_label_returns_all_provenances(self):
        result = build_preview(reviewed('x Ana z', (finding('a', 2, 5),)))
        self.assertEqual([s.finding_id for s in map_output_span(result, 1, 14)],
                         [None, 'a', None])

    def test_preview_repr_does_not_leak_selected_original_values(self):
        result = build_preview(reviewed('SENTINEL', (finding('a', 0, 8),)))
        self.assertNotIn('SENTINEL', repr(result))


if __name__ == '__main__':
    unittest.main()
