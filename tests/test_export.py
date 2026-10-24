from dataclasses import replace
import errno
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from helpers import finding
from local_anonymizer.domain import AnonymizerError, Decision, Disposition, Review
from local_anonymizer.ingest import load_document
from local_anonymizer.transform import build_preview
from local_anonymizer.verification import verify_preview
from local_anonymizer.export import publish_text


class EmptyDetector:
    fingerprint = 'test-v1'

    def analyze(self, text, session_id):
        return ()


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'original.txt'
        self.original = b'Ana\r\n'
        self.source.write_bytes(self.original)
        doc = load_document(self.source)
        f = finding('a', 0, 3, session_id=doc.session_id)
        self.review = Review(doc, (f,), (Decision('a', Disposition.ACCEPT),),
                             coverage_complete=True, confirmed=True)
        self.preview = build_preview(self.review)
        self.verification = verify_preview(self.review, self.preview, EmptyDetector())
        self.destination = self.root / 'saneado.txt'

    def publish(self):
        return publish_text(self.review, self.preview, self.verification, self.destination)

    def test_new_copy_has_expected_bytes_digest_and_private_permissions(self):
        receipt = self.publish()
        expected = b'PERSONA_001\r\n'
        self.assertEqual(self.destination.read_bytes(), expected)
        self.assertEqual(receipt.sha256, hashlib.sha256(expected).hexdigest())
        self.assertEqual(receipt.identity.inode, self.destination.stat().st_ino)
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o600)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         ['original.txt', 'saneado.txt'])

    def test_existing_destination_is_never_overwritten(self):
        self.destination.write_bytes(b'preexistente')
        with self.assertRaises(AnonymizerError):
            self.publish()
        self.assertEqual(self.destination.read_bytes(), b'preexistente')
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_original_aliases_and_symlink_to_missing_file_are_rejected(self):
        for mode in ('same', 'symlink', 'hardlink', 'broken'):
            with self.subTest(mode=mode):
                self.destination = self.root / ('out-' + mode + '.txt')
                if mode == 'same': self.destination = self.source
                elif mode == 'symlink': self.destination.symlink_to(self.source)
                elif mode == 'hardlink': os.link(self.source, self.destination)
                else: self.destination.symlink_to(self.root / 'missing.txt')
                with self.assertRaises(AnonymizerError): self.publish()
                self.assertEqual(self.source.read_bytes(), self.original)
                if mode == 'broken': self.assertTrue(self.destination.is_symlink())

    def test_concurrent_destination_is_never_overwritten(self):
        real_open=os.open
        def race(name,flags,*args,**kwargs):
            if name==self.destination.name and flags & os.O_CREAT:
                self.destination.write_bytes(b'competidor')
            return real_open(name,flags,*args,**kwargs)
        with patch('local_anonymizer.export.os.open',side_effect=race):
            with self.assertRaises(AnonymizerError):self.publish()
        self.assertEqual(self.destination.read_bytes(),b'competidor')
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_disk_full_reports_partial_destination_without_deleting_it(self):
        with patch('local_anonymizer.export.os.write',side_effect=OSError(errno.ENOSPC,'SENTINEL')):
            with self.assertRaises(AnonymizerError) as caught:self.publish()
        self.assertEqual(caught.exception.cleanup_paths,(self.destination,))
        self.assertTrue(self.destination.exists())
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertNotIn('SENTINEL',str(caught.exception))

    def test_unsupported_exclusive_creation_has_no_overwriting_fallback(self):
        real_open=os.open
        def unsupported(name,flags,*args,**kwargs):
            if flags & os.O_CREAT:raise OSError(errno.ENOTSUP,'unsupported')
            return real_open(name,flags,*args,**kwargs)
        with patch('local_anonymizer.export.os.open',side_effect=unsupported):
            with self.assertRaises(AnonymizerError) as caught:self.publish()
        self.assertEqual(caught.exception.code,'EXPORT_UNSUPPORTED')
        self.assertFalse(self.destination.exists())

    def test_destination_replaced_during_write_is_not_deleted_or_modified(self):
        real_write=os.write
        def replace_after_write(fd,data):
            written=real_write(fd,data)
            if self.destination.exists():self.destination.rename(self.root/'own-copy.txt')
            self.destination.write_bytes(b'archivo ajeno')
            return written
        with patch('local_anonymizer.export.os.write',side_effect=replace_after_write):
            with self.assertRaises(AnonymizerError) as caught:self.publish()
        self.assertEqual(self.destination.read_bytes(),b'archivo ajeno')
        self.assertEqual(caught.exception.cleanup_paths,(self.destination,))
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_read_error_reports_existing_candidate_without_success(self):
        with patch('local_anonymizer.export.os.read',side_effect=OSError('SENTINEL')):
            with self.assertRaises(AnonymizerError) as caught:self.publish()
        self.assertTrue(self.destination.exists())
        self.assertEqual(caught.exception.cleanup_paths,(self.destination,))
        self.assertNotIn('SENTINEL',str(caught.exception))
        self.assertNotIn(self.tmp.name,repr(caught.exception))

    def test_publication_never_unlinks_any_path_on_success_or_failure(self):
        with patch('local_anonymizer.export.os.unlink',side_effect=AssertionError('unsafe unlink')) as unlink:
            self.publish();unlink.assert_not_called()
            self.destination=self.root/'failed.txt'
            with patch('local_anonymizer.export.os.write',side_effect=OSError(errno.ENOSPC,'full')):
                with self.assertRaises(AnonymizerError):self.publish()
            unlink.assert_not_called()

    def test_tampered_or_stale_verification_and_missing_confirmation_are_rejected(self):
        for verification in (replace(self.verification, ok=False),
                             replace(self.verification, review_revision=1),
                             replace(self.verification, session_id='other'),
                             replace(self.verification, preview_sha256='0' * 64)):
            with self.subTest(verification=verification):
                with self.assertRaises(AnonymizerError):
                    publish_text(self.review, self.preview, verification, self.destination)
                self.assertFalse(self.destination.exists())
        with self.assertRaises(AnonymizerError):
            publish_text(replace(self.review, confirmed=False), self.preview,
                         self.verification, self.destination)

    def test_parent_path_changed_during_write_cannot_return_wrong_receipt(self):
        parent=self.root/'chosen';parent.mkdir();moved=self.root/'moved';other=self.root/'other';other.mkdir()
        self.destination=parent/'out.txt';real_write=os.write
        def redirect_parent(fd,data):
            count=real_write(fd,data);parent.rename(moved);parent.symlink_to(other,target_is_directory=True);return count
        with patch('local_anonymizer.export.os.write',side_effect=redirect_parent):
            with self.assertRaises(AnonymizerError):self.publish()
        self.assertFalse((other/'out.txt').exists());self.assertTrue((moved/'out.txt').exists())
        self.assertEqual(self.source.read_bytes(),self.original)


if __name__ == '__main__': unittest.main()
