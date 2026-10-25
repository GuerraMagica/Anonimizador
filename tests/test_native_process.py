"""Native PDF work stays on a fresh child main thread, never a Qt worker thread."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from local_anonymizer.domain import AnonymizerError
from local_anonymizer.native_process import _run_native_call


def identity(*,cancelled):
    return os.getpid(),threading.current_thread() is threading.main_thread()


def die(*,cancelled):
    os._exit(71)


def private_failure(*,cancelled):
    raise RuntimeError('private document and path must not leave child')


def cooperative(*,cancelled):
    while not cancelled():time.sleep(.01)
    return 'late result discarded'


def unresponsive(*,cancelled):
    time.sleep(10)


class NativeProcessTests(unittest.TestCase):
    def test_result_from_fresh_child_main_thread(self):
        pid,main=_run_native_call(identity)
        self.assertNotEqual(pid,os.getpid());self.assertTrue(main)
    def test_child_death_cannot_crash_caller(self):
        with self.assertRaisesRegex(AnonymizerError,'^NATIVE_PROCESS_FAILED$'):_run_native_call(die)
        self.assertTrue(_run_native_call(identity)[1])
    def test_child_exception_is_sanitized(self):
        with self.assertRaisesRegex(AnonymizerError,'^NATIVE_PROCESS_FAILED$'):_run_native_call(private_failure)
    def test_cancel_cooperatively_discards_even_successful_late_result(self):
        event=threading.Event();timer=threading.Timer(.3,event.set);timer.start()
        try:
            with self.assertRaisesRegex(AnonymizerError,'^CANCELLED$'):
                _run_native_call(cooperative,cancelled=event.is_set)
        finally:timer.join()
    def test_native_timeout_is_bounded(self):
        start=time.monotonic()
        with self.assertRaisesRegex(AnonymizerError,'^NATIVE_TIMEOUT$'):
            _run_native_call(unresponsive,timeout=.2)
        self.assertLess(time.monotonic()-start,5)
    def test_cancel_unresponsive_native_child_is_bounded(self):
        event=threading.Event();timer=threading.Timer(.3,event.set);timer.start()
        try:
            with self.assertRaisesRegex(AnonymizerError,'^CANCELLED$'):
                _run_native_call(unresponsive,cancelled=event.is_set,cancel_grace=.2)
        finally:timer.join()
    def test_cancellation_before_start_does_not_spawn(self):
        with self.assertRaisesRegex(AnonymizerError,'^CANCELLED$'):_run_native_call(identity,cancelled=lambda:True)


class QtNativeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def invoke(self,operation):
        from PySide6.QtCore import QObject,QThread,Signal,Slot
        class Worker(QObject):
            finished=Signal()
            def __init__(self):super().__init__();self.result=None;self.error=None
            @Slot()
            def run(self):
                try:self.result=operation()
                except Exception as error:self.error=error
                finally:self.finished.emit()
        thread=QThread();worker=Worker();worker.moveToThread(thread)
        thread.started.connect(worker.run);worker.finished.connect(thread.quit);worker.finished.connect(worker.deleteLater)
        thread.start();deadline=time.monotonic()+20
        while thread.isRunning() and time.monotonic()<deadline:
            self.app.processEvents();time.sleep(.01)
        self.assertFalse(thread.isRunning(),'native Qt job did not finish')
        thread.wait()
        if worker.error:raise worker.error
        return worker.result
    def test_successive_qthreads_load_ocr_and_build_pdf(self):
        from PIL import Image,ImageDraw
        from local_anonymizer.formats import load_source,ocr_raster_details
        from local_anonymizer.layout import _pdf_bytes
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.png';image=Image.new('RGB',(400,200),'white')
            ImageDraw.Draw(image).text((30,50),'Maria Garcia',fill='black',font_size=30)
            image.save(path)
            source=self.invoke(lambda:load_source(path))
            self.assertIn('Maria',source.document.text)
            self.assertEqual(source.input_bytes,path.stat().st_size)
            text,boxes=self.invoke(lambda:ocr_raster_details(source.pages))
            self.assertIn('Maria',text);self.assertTrue(boxes)
            payload=self.invoke(lambda:_pdf_bytes(source.pages))
            self.assertTrue(payload.startswith(b'%PDF-'))

    def test_docx_converter_stays_in_calling_process_before_native_ocr(self):
        from unittest.mock import patch
        import pymupdf
        from local_anonymizer.formats import load_source
        with pymupdf.open() as pdf:
            page=pdf.new_page(width=400,height=200)
            page.insert_text((30,70),'Maria Garcia',fontsize=25)
            payload=pdf.tobytes()
        observed=[]
        def converter(data,*,cancelled):
            observed.append((os.getpid(),threading.current_thread() is threading.main_thread()))
            return payload,('DOCX_LAYOUT_RENDERED',)
        with TemporaryDirectory() as tmp,patch('local_anonymizer.office.convert_docx',side_effect=converter):
            path=Path(tmp)/'synthetic.docx';path.write_bytes(b'mocked safe conversion')
            source=self.invoke(lambda:load_source(path))
            self.assertIn('Maria',source.document.text)
            self.assertEqual(source.input_bytes,path.stat().st_size)
        self.assertEqual(observed,[(os.getpid(),False)])
