import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_anonymizer.domain import AnonymizerError
from local_anonymizer.ingest import load_document


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'documento.txt'

    def assert_rejected(self, data, code):
        self.path.write_bytes(data)
        with self.assertRaises(AnonymizerError) as caught:
            load_document(self.path)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.path.read_bytes(), data)

    def test_preserves_crlf_combining_characters_and_non_bmp(self):
        original = b'\xef\xbb\xbf' + 'Hola 😀 y Jose\u0301\r\n'.encode()
        self.path.write_bytes(original)
        document = load_document(self.path)
        self.assertEqual(document.text, 'Hola 😀 y Jose\u0301\r\n')
        self.assertEqual(document.source_sha256, hashlib.sha256(original).hexdigest())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(document.identity.inode, self.path.stat().st_ino)

    def test_empty_file_is_valid(self):
        self.path.write_bytes(b'')
        self.assertEqual(load_document(self.path).text, '')

    def test_sessions_are_distinct(self):
        self.path.write_text('Texto sintético')
        self.assertNotEqual(load_document(self.path).session_id,
                            load_document(self.path).session_id)

    def test_character_limit_is_inclusive(self):
        self.path.write_text('a' * 100_000)
        self.assertEqual(len(load_document(self.path).text), 100_000)
        self.assert_rejected(b'a' * 100_001, 'INPUT_CHARACTER_LIMIT')

    def test_byte_limit_is_checked_before_character_limit(self):
        self.assert_rejected(b'a' * 1_048_576, 'INPUT_CHARACTER_LIMIT')
        self.assert_rejected(b'a' * 1_048_577, 'INPUT_BYTE_LIMIT')

    def test_invalid_utf8_is_not_replaced(self):
        self.assert_rejected(b'abc\xff', 'INPUT_ENCODING')

    def test_interior_bom_and_unsupported_controls_are_blocked(self):
        for character in ('\0', '\x0b', '\x7f', '\x85', '\u061c',
                          '\u200e', '\u202e', '\u2066', '\u200b',
                          '\u2060', '\ufeff'):
            with self.subTest(character=ascii(character)):
                self.assert_rejected(('antes' + character + 'después').encode(),
                                     'INPUT_CONTROL')

    def test_tab_lf_and_emoji_joiner_are_preserved(self):
        text = 'a\tb\nc 👩\u200d💻'
        self.path.write_text(text)
        self.assertEqual(load_document(self.path).text, text)

    def test_markdown_is_read_as_uninterpreted_source(self):
        for suffix in ('.md', '.markdown', '.TXT'):
            self.path = self.path.with_suffix(suffix)
            text = '---\nauthor: Sintético\n---\n<!-- secreto -->\n<script>x</script>'
            self.path.write_text(text)
            self.assertEqual(load_document(self.path).text, text)

    def test_unsupported_extension_is_rejected(self):
        self.path = self.path.with_suffix('.pdf')
        self.path.write_bytes(b'texto')
        with self.assertRaises(AnonymizerError) as caught:
            load_document(self.path)
        self.assertEqual(caught.exception.code, 'INPUT_FORMAT')

    def test_disguised_pdf_and_zip_are_rejected(self):
        for data in (b'%PDF-1.7', b'PK\x03\x04abc'):
            with self.subTest(data=data):
                self.assert_rejected(data, 'INPUT_FORMAT')

    def test_non_regular_file_is_rejected(self):
        self.path.mkdir()
        with self.assertRaises(AnonymizerError) as caught:
            load_document(self.path)
        self.assertEqual(caught.exception.code, 'INPUT_NOT_REGULAR')

    def test_fifo_does_not_block(self):
        os.mkfifo(self.path)
        with self.assertRaises(AnonymizerError) as caught:
            load_document(self.path)
        self.assertEqual(caught.exception.code, 'INPUT_NOT_REGULAR')

    def test_input_symlink_is_rejected_without_touching_target(self):
        target = Path(self.tmp.name) / 'target.txt'
        target.write_bytes(b'original')
        self.path.symlink_to(target)
        with self.assertRaises(AnonymizerError) as caught:
            load_document(self.path)
        self.assertEqual(caught.exception.code, 'INPUT_NOT_REGULAR')
        self.assertEqual(target.read_bytes(), b'original')

    def test_changed_file_during_read_is_rejected(self):
        self.path.write_bytes(b'original')
        real_read = os.read
        changed = False

        def concurrent_change(fd, count):
            nonlocal changed
            data = real_read(fd, count)
            if not changed:
                changed = True
                self.path.write_bytes(b'cambiado externamente')
            return data

        with patch('local_anonymizer.ingest.os.read', side_effect=concurrent_change):
            with self.assertRaises(AnonymizerError) as caught:
                load_document(self.path)
        self.assertEqual(caught.exception.code, 'INPUT_CHANGED')

    def test_missing_file_error_does_not_expose_path(self):
        self.path = self.path.with_name('SENTINEL_PERSONAL.txt')
        with self.assertRaises(AnonymizerError) as caught:
            load_document(self.path)
        self.assertEqual(caught.exception.code, 'INPUT_READ')
        self.assertNotIn('SENTINEL_PERSONAL', str(caught.exception))
        self.assertNotIn(self.tmp.name, repr(caught.exception))


if __name__ == '__main__':
    unittest.main()
