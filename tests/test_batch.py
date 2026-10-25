import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from helpers import document
from local_anonymizer.batch import Batch, BatchEntry
from local_anonymizer.domain import AnonymizerError
from local_anonymizer.source import LoadedSource, SourceKind, VisualRegion

class BatchTests(unittest.TestCase):
    def test_sessions_and_regions_are_independent_and_edits_revoke(self):
        a=BatchEntry(Path('a'));b=BatchEntry(Path('b'))
        a.attach(LoadedSource(document('uno'),SourceKind.TEXT))
        b.attach(LoadedSource(document('dos'),SourceKind.TEXT))
        a.session.set_findings(());a.session.preview();a.session.confirm()
        self.assertTrue(a.session.review.confirmed)
        self.assertFalse(b.session.review.confirmed)
        before=a.session.review.revision
        a.invalidate_visual()
        self.assertGreater(a.session.review.revision,before)
        self.assertFalse(a.session.review.confirmed)
        self.assertIsNone(a.session.current_preview)
    def test_queue_limits_and_duplicate_paths(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.txt';p.write_text('uno')
            q=Batch((p,p));self.assertEqual(len(q.entries),1)
            with self.assertRaises(AnonymizerError):Batch(tuple(Path(tmp)/f'{i}.txt' for i in range(21)))
            with self.assertRaises(AnonymizerError):Batch((Path(tmp)/'missing.txt',))
    def test_aggregate_size_limit_without_reading_payload(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'large.txt'
            with p.open('wb') as stream:stream.truncate(201*1024*1024)
            with self.assertRaises(AnonymizerError):Batch((p,))

    def test_queue_growth_is_revalidated_before_load(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.txt';p.write_text('uno');q=Batch((p,))
            with p.open('wb') as stream:stream.truncate(201*1024*1024)
            with self.assertRaises(AnonymizerError):q.validate_limits()
