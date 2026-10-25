import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PySide6.QtCore import QUrl,QByteArray
from PySide6.QtWidgets import QApplication
from local_anonymizer.domain import AnonymizerError
from local_anonymizer.markdown_view import SafeMarkdownBrowser,resolve_resource

class MarkdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.file=self.root/'referencia.pdf';self.file.write_bytes(b'synthetic')
    def test_render_never_opens_or_fetches_resources(self):
        view=SafeMarkdownBrowser(self.root);self.addCleanup(view.close)
        with patch('PySide6.QtGui.QDesktopServices.openUrl',side_effect=AssertionError('autoopen')):
            view.render_markdown('# Cabecera\n**negrita** ![x](https://example.com/image.png)\n<script>alert(1)</script>')
            self.app.processEvents()
        self.assertIn('Cabecera',view.toPlainText());self.assertIn('negrita',view.toPlainText())
        self.assertFalse(view.openLinks());self.assertFalse(view.openExternalLinks())
        self.assertIsInstance(view.loadResource(2,QUrl('https://example.com/image.png')),QByteArray)
    def test_local_allowed_and_escape_or_scripts_blocked(self):
        target=resolve_resource('referencia.pdf',self.root)
        self.assertEqual(target.kind,'local');self.assertEqual(Path(target.destination),self.file.resolve())
        for value in ('../outside.pdf','javascript:alert(1)','data:text/html,hello','file://host/share/a.pdf','run.command','%252e%252e/outside.pdf'):
            with self.subTest(value=value):
                with self.assertRaises(AnonymizerError):resolve_resource(value,self.root)
        script=self.root/'run.command';script.write_text('echo should-not-run')
        with self.assertRaises(AnonymizerError):resolve_resource('run.command',self.root)
    def test_symlink_escape_and_credentials_rejected(self):
        outside=self.root.parent/'outside.pdf'
        link=self.root/'escape.pdf';link.symlink_to(outside)
        with self.assertRaises(AnonymizerError):resolve_resource('escape.pdf',self.root)
        with self.assertRaises(AnonymizerError):resolve_resource('https://user:secret@example.com/path',self.root)
    def test_links_emit_explicit_request_without_opening(self):
        view=SafeMarkdownBrowser(self.root);self.addCleanup(view.close);requests=[];errors=[]
        view.resourceRequested.connect(requests.append);view.linkBlocked.connect(errors.append)
        with patch('PySide6.QtGui.QDesktopServices.openUrl',side_effect=AssertionError('autoopen')):
            view.request_resource(QUrl('https://example.com/reference'))
            view.request_resource(QUrl('javascript:alert(1)'))
        self.assertEqual(len(requests),1);self.assertEqual(requests[0].kind,'web')
        self.assertEqual(errors,['LINK_BLOCKED'])
    def test_internal_anchor_does_not_open_browser(self):
        view=SafeMarkdownBrowser(self.root);self.addCleanup(view.close);requests=[]
        view.resourceRequested.connect(requests.append);view.request_resource(QUrl('#seccion'))
        self.assertEqual(requests,[])

if __name__=='__main__':unittest.main()
