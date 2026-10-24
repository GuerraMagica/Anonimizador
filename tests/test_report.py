import json
from pathlib import Path
import tempfile
import unittest

from local_anonymizer.domain import AnonymizerError, FileIdentity, Receipt
from local_anonymizer.report import build_report, save_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.receipt = Receipt(Path('/SENTINEL/original-name.txt'), FileIdentity(1, 2), 'a' * 64)

    def test_report_excludes_path_identity_text_and_original_values(self):
        report = build_report(self.receipt, {'PERSONA': 2, 'ACCEPT': 2},
                              {'application': '0.1.0.dev0', 'python': '3.12.14'})
        payload = json.dumps(report)
        self.assertNotIn('SENTINEL', payload)
        self.assertNotIn('original-name', payload)
        self.assertEqual(report['output_sha256'], 'a' * 64)
        self.assertTrue(report['verification']['contextual_risk_review_required'])

    def test_arbitrary_sensitive_counter_and_version_keys_or_values_are_rejected(self):
        for counts, versions in (({'SENTINEL': 1}, {}), ({'PERSONA': -1}, {}),
                                 ({'PENDING': 1}, {}), ({'PERSONA': True}, {}),
                                 ({}, {'model_path': '/SENTINEL'}),
                                 ({}, {'application': 'secret@synthetic.invalid'})):
            with self.subTest(counts=counts, versions=versions):
                with self.assertRaises(AnonymizerError):
                    build_report(self.receipt, counts, versions)

    def test_report_save_is_exclusive_and_revalidated(self):
        report = build_report(self.receipt, {}, {'application': '0.1.0.dev0'})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'informe.json'
            save_report(report, path)
            self.assertEqual(json.loads(path.read_text()), report)
            original = path.read_bytes()
            with self.assertRaises(AnonymizerError): save_report(report, path)
            self.assertEqual(path.read_bytes(), original)
            tampered = dict(report, text='SENTINEL')
            with self.assertRaises(AnonymizerError):
                save_report(tampered, Path(folder) / 'otro.json')
            self.assertFalse((Path(folder) / 'otro.json').exists())


if __name__ == '__main__': unittest.main()
