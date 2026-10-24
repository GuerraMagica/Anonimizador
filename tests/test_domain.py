from pathlib import Path
import tempfile
import unittest

from local_anonymizer.domain import (
    Action, AnonymizerError, Category, Confidentiality, Finding,
)
from local_anonymizer.ingest import load_document


class DomainTests(unittest.TestCase):
    def test_document_repr_does_not_leak_content_path_or_source_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'SENTINEL_FILENAME.txt'
            path.write_text('SENTINEL_CONTENT')
            document = load_document(path)
            representation = repr(document)
            for secret in ('SENTINEL_FILENAME', 'SENTINEL_CONTENT', folder,
                           document.source_sha256):
                self.assertNotIn(secret, representation)

    def test_finding_rejects_invalid_intervals_and_scores(self):
        for start, end, score in ((-1, 1, None), (1, 1, None),
                                  (2, 1, None), (0, 1, float('nan')),
                                  (0, 1, 1.1)):
            with self.subTest(start=start, end=end, score=score):
                with self.assertRaises(AnonymizerError):
                    Finding('f1', 'session', start, end, Category.PERSONA,
                            Confidentiality.PII, ('manual',), score)

    def test_error_does_not_accept_arbitrary_sensitive_message(self):
        error = AnonymizerError('SENTINEL email@synthetic.invalid')
        self.assertEqual(str(error), 'INTERNAL_ERROR')
        self.assertNotIn('SENTINEL', repr(error))


if __name__ == '__main__':
    unittest.main()
