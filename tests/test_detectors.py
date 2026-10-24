import unittest
from pathlib import Path
from unittest.mock import patch
from helpers import document
from local_anonymizer.domain import AnonymizerError, Category
from local_anonymizer.detectors import LocalDetector, default_model_path, literal_findings

class LiteralTests(unittest.TestCase):
    def test_exact_unicode_boundaries_case_and_overlaps(self):
        d=document('😀 Río Verde; Río; río; XRío; Río_2; Ríox; [A.*]')
        found=literal_findings(d,(('Río',Category.PROYECTO),('Río Verde',Category.PERSONAJE),('[A.*]',Category.CODIGO)))
        self.assertEqual([(f.start,f.end,f.category) for f in found],[(2,5,Category.PROYECTO),(2,11,Category.PERSONAJE),(13,16,Category.PROYECTO),(42,47,Category.CODIGO)])
        self.assertTrue(all('Río' not in repr(f) for f in found))

    def test_invalid_terms_are_sanitized(self):
        for terms in ((('',Category.PROYECTO),),(('a', 'SECRET'),)):
            with self.assertRaises(AnonymizerError):literal_findings(document('a'),terms)

class DetectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.detector=LocalDetector(default_model_path())

    def test_missing_model_has_no_network(self):
        with patch('socket.socket',side_effect=AssertionError('network')):
            with self.assertRaisesRegex(AnonymizerError,'MODEL_UNAVAILABLE'):
                LocalDetector(Path('/does-not-exist'))

    def test_real_identifiers_span_and_category(self):
        samples=[('Correo: prueba@example.com', 'prueba@example.com',Category.CORREO),
                 ('Teléfono: +34 612 345 678','+34 612 345 678',Category.TELEFONO),
                 ('DNI: 12345678Z','12345678Z',Category.DOCUMENTO),
                 ('NIE: X1234567L','X1234567L',Category.DOCUMENTO),
                 ('Pasaporte: ABC123456','ABC123456',Category.DOCUMENTO),
                 ('IBAN: ES91 2100 0418 4502 0005 1332','ES91 2100 0418 4502 0005 1332',Category.IBAN),
                 ('Fecha: 24/10/2026','24/10/2026',Category.FECHA)]
        for text,value,cat in samples:
            with self.subTest(cat=cat,value=value):
                f=self.detector.analyze(text,'test')
                self.assertIn((text.index(value),text.index(value)+len(value),cat),[(x.start,x.end,x.category) for x in f])

    def test_real_ner_exposes_per_org_loc(self):
        text='Pedro Sánchez trabaja en Microsoft y vive en Madrid.'
        f=self.detector.analyze(text,'test')
        self.assertTrue({Category.PERSONA,Category.ORGANIZACION,Category.UBICACION} <= {x.category for x in f})

    def test_no_network_even_on_first_email(self):
        with patch('socket.socket',side_effect=AssertionError('network')):
            self.assertTrue(self.detector.analyze('contacto@example.com','test'))

    def test_dependency_error_sanitized(self):
        with patch.object(self.detector,'_nlp',side_effect=RuntimeError('SECRET_987')):
            with self.assertRaises(AnonymizerError) as cm:self.detector.analyze('SECRET_987','test')
        self.assertNotIn('SECRET_987',repr(cm.exception));self.assertIsNone(cm.exception.__cause__)

    def test_invalid_checksum_and_foreign_phone_not_es(self):
        f=self.detector.analyze('DNI: 12345678A; NIE X1234567A; +1 202-555-0123','test')
        self.assertFalse(any(x.category in (Category.DOCUMENTO,Category.TELEFONO) for x in f))

    def test_real_model_accepts_label_expansion_beyond_input_limit(self):
        # Valid admitted input may expand to >100k during interval replacement.
        from helpers import reviewed, finding
        from local_anonymizer.transform import build_preview
        from local_anonymizer.verification import verify_preview
        source='Ana ' * 10000
        r=reviewed(source,tuple(finding(str(i),4*i,4*i+3) for i in range(10000)))
        preview=build_preview(r)
        self.assertEqual(len(preview.text),120000)
        result=verify_preview(r,preview,self.detector)
        self.assertNotIn('ANALYSIS_FAILED',result.issues)

if __name__=='__main__':unittest.main()
