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

class GuiTests(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
