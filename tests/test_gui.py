import unittest
from dataclasses import replace
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from helpers import document, finding
from local_anonymizer.domain import Category, Decision, Disposition
from local_anonymizer.gui import MainWindow, python_to_qt, qt_to_python, ConfiguredDetector

class EmptyDetector:
    fingerprint='test:1'
    def analyze(self,text,session_id):return ()

class BaseGuiCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):self.w=MainWindow(detector=EmptyDetector());self.w.show();self.app.processEvents()
    def tearDown(self):
        if self.w.session.busy:
            self.w.cancel_work();self.wait_idle()
        self.w.close();self.app.processEvents()
    def wait_idle(self):
        for _ in range(300):
            self.app.processEvents()
            if self.w._thread is None:return
            QTest.qWait(10)
        self.fail('worker did not finish')
    def loaded(self,text='Ana'):
        self.w.set_document(document(text));self.w.start_analysis();self.wait_idle()

class GuiTests(BaseGuiCase):
    def test_plain_text_never_html(self):
        self.loaded('<b>literal</b> 😀\r\nfinal')
        self.assertIn('<b>literal</b>',self.w.source.toPlainText())
        self.assertTrue(self.w.source.isReadOnly());self.assertTrue(self.w.output.isReadOnly())
    def test_qt_unicode_and_crlf_positions(self):
        text='😀 e\u0301\r\nAna';self.loaded(text)
        pos=text.index('Ana');cursor=self.w.source.textCursor()
        cursor.setPosition(python_to_qt(text,pos));cursor.setPosition(python_to_qt(text,pos+3),QTextCursor.KeepAnchor)
        self.w.source.setTextCursor(cursor);self.assertEqual(cursor.selectedText(),'Ana')
        self.assertEqual(qt_to_python(text,cursor.selectionStart()),pos)
        self.w.add_selection();f=self.w.session.review.findings[-1]
        self.assertEqual(text[f.start:f.end],'Ana')
    def test_human_confirmation_and_change_revokes(self):
        self.loaded();self.w.session.set_findings((finding('a',0,3),))
        self.w.session.set_decisions((Decision('a',Disposition.ACCEPT),));self.w.render_review()
        self.w.make_preview();self.assertFalse(self.w.session.review.confirmed)
        self.w.attestation.setChecked(True);self.w.confirm_review();self.wait_idle()
        self.assertTrue(self.w.session.can_export);self.assertTrue(self.w.export_button.isEnabled())
        self.w.table.cellWidget(0,4).setCurrentIndex(2)
        self.assertFalse(self.w.session.can_export);self.assertFalse(self.w.attestation.isChecked())
        self.assertFalse(self.w.export_button.isEnabled())
    def test_cancel_pending_and_only_one_job(self):
        import threading
        entered=threading.Event();release=threading.Event()
        class Slow(EmptyDetector):
            def analyze(self,text,session_id):entered.set();release.wait(3);return ()
        self.w._detector=Slow();self.w.set_document(document('test'));self.w.start_analysis()
        for _ in range(100):
            if entered.is_set():break
            QTest.qWait(5)
        self.w.cancel_work();self.assertTrue(self.w.session.cancel_pending)
        self.assertFalse(self.w.analyze_button.isEnabled())
        release.set();self.wait_idle();self.assertFalse(self.w.session.can_export)
        self.assertFalse(self.w.session.review.coverage_complete)
    def test_errors_never_include_dependency_text(self):
        class Bad(EmptyDetector):
            def analyze(self,text,session_id):raise RuntimeError('SECRET_GUI')
        self.w._detector=Bad();self.loaded('SECRET_GUI')
        self.assertNotIn('SECRET_GUI',self.w.status.text());self.assertFalse(self.w.session.can_export)
    def test_terms_participate_in_residual_detection_and_fingerprint(self):
        a=ConfiguredDetector(EmptyDetector(),(('Filme',Category.PROYECTO),))
        b=ConfiguredDetector(EmptyDetector(),())
        self.assertNotEqual(a.fingerprint,b.fingerprint)
        self.assertEqual(len(a.analyze('Filme y Filmer','s')),1)
        self.assertNotIn('Filme',a.fingerprint)

    def test_unchecking_attestation_revokes_export(self):
        self.loaded('Texto');self.w.make_preview();self.w.attestation.setChecked(True)
        self.w.confirm_review();self.wait_idle();self.assertTrue(self.w.session.can_export)
        self.w.attestation.setChecked(False)
        self.assertFalse(self.w.session.can_export)
        self.assertFalse(self.w.session.review.confirmed)

    def test_real_file_workflow_preserves_source_and_writes_plain_output(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from local_anonymizer.ingest import load_document
        with TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.md';raw='😀 Ana\r\n<b>fin</b>'.encode();source.write_bytes(raw)
            self.w.set_document(load_document(source));self.w.start_analysis();self.wait_idle()
            r=self.w.session.review;f=replace(finding('a',2,5),session_id=r.document.session_id)
            self.w.session.set_findings((f,));self.w.session.set_decisions((Decision('a',Disposition.ACCEPT),))
            self.w.render_review();self.w.make_preview();self.w.attestation.setChecked(True)
            self.w.confirm_review();self.wait_idle();self.assertTrue(self.w.session.can_export)
            dest=Path(tmp)/'new.txt';self.w.export_to(dest)
            self.assertEqual(dest.read_bytes(),'😀 PERSONA_001\r\n<b>fin</b>'.encode())
            self.assertEqual(source.read_bytes(),raw);self.assertTrue(self.w.report_button.isEnabled())

    def test_report_preparation_failure_does_not_hide_successful_txt(self):
        from unittest.mock import patch
        from tempfile import TemporaryDirectory
        from pathlib import Path
        self.loaded('Texto');self.w.make_preview();self.w.attestation.setChecked(True)
        self.w.confirm_review();self.wait_idle()
        with TemporaryDirectory() as tmp, patch('local_anonymizer.gui.build_report',side_effect=ValueError('SECRET')):
            dest=Path(tmp)/'new.txt';receipt=self.w.export_to(dest)
            self.assertEqual(dest.read_text(),'Texto');self.assertEqual(receipt.destination,dest)
            self.assertIn('TXT verificado; informe no',self.w.status.text())
            self.assertNotIn('SECRET',self.w.status.text());self.assertFalse(self.w.report_button.isEnabled())

class PaginationTests(BaseGuiCase):
    def dense(self,count=250,*,decided=False):
        text=''.join(f'item{i:05d} ' for i in range(count))
        self.w.set_document(document(text))
        fs=tuple(finding(str(i),10*i,10*i+9) for i in range(count))
        self.w.session.set_findings(fs)
        if decided:self.w.session.set_decisions(tuple(Decision(f.id,Disposition.REJECT) for f in fs))
        self.w.render_review()

    def test_many_findings_keep_only_one_page_of_widgets(self):
        self.dense(3000)
        self.assertLessEqual(self.w.table.rowCount(),100)
        self.assertEqual(len(self.w.session.review.findings),3000)
        self.assertIn('3000',self.w.page_label.text())
        self.assertTrue(self.w.next_button.isEnabled());self.assertFalse(self.w.previous_button.isEnabled())

    def test_offpage_edit_preserves_other_decisions_and_correct_index(self):
        self.dense();self.w.table.cellWidget(0,4).setCurrentIndex(2)
        self.w.change_page(1);self.w.table.cellWidget(0,4).setCurrentIndex(1)
        ds=self.w.session.review.decisions
        self.assertEqual(ds[0].disposition,Disposition.REJECT)
        self.assertEqual(ds[100].disposition,Disposition.ACCEPT)
        self.assertEqual(ds[101].disposition,Disposition.PENDING)
        self.w.change_page(-1);self.assertEqual(self.w.table.cellWidget(0,4).currentIndex(),2)
        self.w.change_page(1);self.assertEqual(self.w.table.cellWidget(0,4).currentIndex(),1)

    def test_editing_later_page_matches_decisions_by_id_not_tuple_order(self):
        self.dense(decided=True)
        r=self.w.session.review;self.w.session.set_decisions(tuple(reversed(r.decisions)))
        self.w.render_review();self.w.change_page(1)
        self.w.table.cellWidget(0,4).setCurrentIndex(1)
        ds={d.finding_id:d.disposition for d in self.w.session.review.decisions}
        self.assertEqual(ds['100'],Disposition.ACCEPT)
        self.assertTrue(all(v==Disposition.REJECT for k,v in ds.items() if k!='100'))

    def test_pending_candidates_on_other_pages_block_preview(self):
        from local_anonymizer.domain import AnonymizerError
        self.dense(101,decided=True)
        r=self.w.session.review;ds=list(r.decisions);ds[-1]=Decision(ds[-1].finding_id,Disposition.PENDING)
        self.w.session.set_decisions(tuple(ds));self.w.render_review()
        with self.assertRaises(AnonymizerError):self.w.session.preview()
        self.assertFalse(self.w.session.can_export)

    def test_navigation_keeps_confirmation_editing_on_later_page_revokes(self):
        self.dense(decided=True);self.w.make_preview();self.w.attestation.setChecked(True)
        self.w.confirm_review();self.wait_idle();self.assertTrue(self.w.session.can_export)
        before=self.w.session.review;preview=self.w.output.toPlainText()
        self.w.change_page(1)
        self.assertEqual(self.w.session.review,before)
        self.assertTrue(self.w.session.can_export);self.assertTrue(self.w.attestation.isChecked())
        self.assertEqual(self.w.output.toPlainText(),preview)
        self.w.table.cellWidget(0,4).setCurrentIndex(1)
        self.assertFalse(self.w.session.can_export);self.assertFalse(self.w.attestation.isChecked())

    def test_locate_and_correct_on_second_page_use_original_coordinates(self):
        self.dense();self.w.change_page(1);self.w.table.selectRow(0)
        self.app.processEvents()
        self.assertEqual(self.w.source.textCursor().selectedText(),'item00100')
        self.w.select_original(1010,1019);self.w.correct_selection()
        self.assertEqual(self.w.session.review.findings[100].start,1010)
        self.assertEqual(self.w.session.review.findings[0].start,0)

    def test_last_partial_page_and_new_document_reset(self):
        self.dense(201);self.w.change_page(1);self.w.change_page(1)
        self.assertEqual(self.w.table.rowCount(),1);self.assertFalse(self.w.next_button.isEnabled())
        self.w.set_document(document('nuevo'));self.w.start_analysis();self.wait_idle()
        self.assertFalse(self.w.previous_button.isEnabled());self.assertEqual(self.w.table.rowCount(),0)

if __name__=='__main__':unittest.main()
