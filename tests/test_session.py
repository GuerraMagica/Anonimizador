import unittest
from dataclasses import replace
from helpers import document, finding
from local_anonymizer.domain import AnonymizerError, Decision, Disposition
from local_anonymizer.session import Session

class EmptyDetector:
    fingerprint = 'test:1'
    def analyze(self, text, session_id): return ()

class SessionTests(unittest.TestCase):
    def ready(self):
        s=Session(); s.load(document('Ana')); s.set_findings((finding('a',0,3),))
        s.set_decisions((Decision('a',Disposition.ACCEPT),)); s.preview(); s.confirm()
        return s

    def test_change_revokes_confirmation_and_verification(self):
        s=self.ready(); self.assertTrue(s.verify(EmptyDetector()).ok); self.assertTrue(s.can_export)
        s.set_decisions((Decision('a',Disposition.REJECT),))
        self.assertFalse(s.can_export); self.assertFalse(s.review.confirmed)
        self.assertIsNone(s.current_preview); self.assertEqual(s.rejections,())

    def test_late_result_after_cancel_is_ignored_until_job_exits(self):
        s=Session();s.load(document('Ana'));token=s.begin_job()
        s.cancel(); self.assertTrue(s.busy);self.assertTrue(s.cancel_pending)
        with self.assertRaises(AnonymizerError):s.begin_job()
        self.assertFalse(s.accept_result(token,(finding('a',0,3),)))
        self.assertFalse(s.busy);self.assertFalse(s.can_export)

    def test_old_document_result_does_not_replace_new_document(self):
        s=Session();s.load(document('Ana'));token=s.begin_job()
        new=replace(document('Otro'),session_id='other');s.load(new)
        self.assertFalse(s.accept_result(token,(finding('a',0,3),)))
        self.assertEqual(s.review.document,new);self.assertEqual(s.review.findings,())

    def test_result_does_not_confirm(self):
        s=Session();s.load(document('Ana'));token=s.begin_job()
        self.assertTrue(s.accept_result(token,(finding('a',0,3),)))
        self.assertFalse(s.review.confirmed);self.assertTrue(s.review.coverage_complete)
        self.assertEqual(s.review.decisions[0].disposition,Disposition.PENDING)

    def test_unknown_token_does_not_finish_current_job(self):
        s=self.ready();token=s.begin_job()
        self.assertFalse(s.accept_result(replace(token,job_id='wrong'),()))
        self.assertTrue(s.busy);s.finish_job(token);self.assertFalse(s.busy)

    def test_decision_change_during_job_discards_result(self):
        s=self.ready();token=s.begin_job()
        s.set_decisions((Decision('a',Disposition.REJECT),))
        self.assertFalse(s.accept_result(token,()));self.assertEqual(len(s.review.findings),1)

    def test_close_discards_sensitive_state_and_keeps_pending_job(self):
        s=self.ready();token=s.begin_job();s.close()
        self.assertIsNone(s.review);self.assertIsNone(s.current_preview)
        self.assertTrue(s.busy);self.assertFalse(s.accept_result(token,()))
        self.assertFalse(s.busy);self.assertFalse(s.can_export)

    def test_confirmation_requires_preview(self):
        s=Session();s.load(document('text'));s.set_findings(())
        with self.assertRaises(AnonymizerError):s.confirm()
        s.preview();s.confirm();self.assertTrue(s.verify(EmptyDetector()).ok)

    def test_bad_findings_are_rejected_without_partial_state(self):
        s=self.ready();before=s.review
        with self.assertRaises(AnonymizerError):s.set_findings((finding('a',0,100),))
        self.assertEqual(s.review,before)

    def test_incomplete_job_failure_does_not_enable_export(self):
        s=Session();s.load(document('Ana'));token=s.begin_job();s.finish_job(token)
        self.assertFalse(s.can_export);self.assertFalse(s.review.coverage_complete)

    def test_busy_session_cannot_confirm(self):
        s=self.ready();token=s.begin_job()
        with self.assertRaises(AnonymizerError):s.confirm()
        s.finish_job(token)

class VerificationStateTests(unittest.TestCase):
    ready = SessionTests.ready
    def test_async_verification_stale_after_mutation(self):
        from local_anonymizer.verification import verify_preview
        s=self.ready();token=s.begin_job(verification=True)
        result=verify_preview(s.review,s.current_preview,EmptyDetector())
        s.set_decisions((Decision('a',Disposition.REJECT),))
        self.assertFalse(s.accept_verification(token,result));self.assertFalse(s.can_export)

    def test_residual_rejection_requires_exact_current_key(self):
        class LabelDetector(EmptyDetector):
            def analyze(self,text,session_id):
                return (finding('res',0,len(text),session_id=session_id),)
        s=self.ready();v=s.verify(LabelDetector());self.assertFalse(v.ok)
        s.reject_residuals((v.residuals[0].key,))
        self.assertTrue(s.verify(LabelDetector()).ok);self.assertTrue(s.can_export)
        s.set_decisions((Decision('a',Disposition.ACCEPT),))
        self.assertEqual(s.rejections,());self.assertFalse(s.can_export)

if __name__=='__main__':unittest.main()
