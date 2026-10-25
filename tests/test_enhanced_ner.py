import unittest
from pathlib import Path
from unittest.mock import patch
from local_anonymizer.domain import AnonymizerError
from local_anonymizer.ner import EnhancedDetector, text_windows

class WindowTests(unittest.TestCase):
    def test_unicode_complete_coverage_and_overlap(self):
        text='😀 ' + 'Álvaro en Madrid. '*1000
        windows=list(text_windows(text, size=180, overlap=60))
        covered=set()
        for offset, value in windows:
            self.assertEqual(text[offset:offset+len(value)],value)
            self.assertLessEqual(len(value),180)
            covered.update(range(offset,offset+len(value)))
        self.assertEqual(covered,set(range(len(text))))
        self.assertGreater(len(windows),1)
    def test_invalid_window_config(self):
        with self.assertRaises(ValueError):list(text_windows('abc',size=3,overlap=3))

class EnhancedTests(unittest.TestCase):
    def test_missing_resource_sanitized_without_network(self):
        with patch('socket.socket',side_effect=AssertionError('NETWORK')):
            with self.assertRaisesRegex(AnonymizerError,'MODEL_UNAVAILABLE'):
                EnhancedDetector(Path('/SECRET_MISSING'))

class StructuredTests(unittest.TestCase):
    def test_structured_only_does_not_load_spacy_model(self):
        from local_anonymizer.detectors import LocalDetector
        with patch('spacy.load',side_effect=AssertionError('NO_MODEL')):
            detector=LocalDetector(None, structured_only=True)
        found=detector.analyze('Ana en Madrid: prueba@example.com','session')
        self.assertEqual([f.category.value for f in found],['CORREO'])

class AnalysisTests(unittest.TestCase):
    def detector(self, predictor):
        detector=object.__new__(EnhancedDetector)
        detector._predict=predictor
        detector._structured=type('Structured',(),{'analyze':lambda self,text,session:()})()
        return detector
    def test_offsets_dedup_and_conflicting_categories(self):
        def predict(text):
            start=text.find('Ana')
            return [] if start<0 else [{'start':start,'end':start+3,'label':label,'score':.8} for label in ('person','organization')]
        text='😀 '+ 'x '*140+'Ana'+' y '*140
        findings=self.detector(predict).analyze(text,'session')
        self.assertEqual({(f.start,f.end,f.category.value) for f in findings},{(text.index('Ana'),text.index('Ana')+3,c) for c in ('PERSONA','ORGANIZACION')})
        self.assertEqual(len(findings),2)
    def test_error_sanitized(self):
        def fail(text):raise RuntimeError('SECRET')
        with self.assertRaisesRegex(AnonymizerError,'ANALYSIS_FAILED') as caught:self.detector(fail).analyze('SECRET','session')
        self.assertIsNone(caught.exception.__cause__)
    def test_cancel_between_windows_discards_partial(self):
        calls=[]
        detector=self.detector(lambda text:calls.append(text) or [])
        with self.assertRaisesRegex(AnonymizerError,'CANCELLED'):detector.analyze_cancellable('a '*1000,'session',lambda:len(calls)>0)
        self.assertEqual(len(calls),1)
    def test_bad_model_offsets_fail_closed(self):
        detector=self.detector(lambda text:[{'start':0,'end':999,'label':'person','score':.8}])
        with self.assertRaisesRegex(AnonymizerError,'ANALYSIS_FAILED'):detector.analyze('Ana','session')

class ResourceTests(unittest.TestCase):
    def test_untrusted_manifest_rejected(self):
        from tempfile import TemporaryDirectory
        import json
        with TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'manifest.json').write_text(json.dumps({'resources':[]}))
            with patch('gliner.model.UniEncoderSpanGLiNER',side_effect=AssertionError('must reject before load')) as loader:
                with self.assertRaisesRegex(AnonymizerError,'MODEL_UNAVAILABLE'):EnhancedDetector(path)
                loader.assert_not_called()
    def test_manifest_pinned_digest(self):
        from local_anonymizer.ner import PINNED_MANIFEST_SHA256
        from hashlib import sha256
        self.assertEqual(PINNED_MANIFEST_SHA256,sha256(Path('docs/ner-resources.json').read_bytes()).hexdigest())

import os
@unittest.skipUnless(os.environ.get('RUN_ENHANCED_NER')=='1','explicit local model integration')
class RealEnhancedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.detector=EnhancedDetector(Path('.venv/models/gliner-multi-v2.1'))
    def test_real_offline_offsets_tail_and_identifiers(self):
        text='Texto de prueba sin nombres. '*35+'😀 Pedro Sánchez trabaja en Microsoft y vive en Madrid. contacto@example.com'
        with patch('socket.socket',side_effect=AssertionError('NETWORK')):
            findings=self.detector.analyze(text,'offline')
        for value,category in [('Pedro Sánchez','PERSONA'),('Microsoft','ORGANIZACION'),('Madrid','UBICACION'),('contacto@example.com','CORREO')]:
            self.assertIn((text.index(value),text.index(value)+len(value),category),[(f.start,f.end,f.category.value) for f in findings])
        self.assertTrue(self.detector.fingerprint.startswith('gliner-es:v1:'))
    def test_pre_cancel_does_not_infer(self):
        with patch.object(self.detector,'_predict',side_effect=AssertionError('INFERENCE')):
            with self.assertRaisesRegex(AnonymizerError,'CANCELLED'):self.detector.analyze_cancellable('Texto','cancel',lambda:True)

class VerifiedSelectionTests(unittest.TestCase):
    def fixture(self, root):
        import json
        from hashlib import sha256
        model=root/'gliner-multi-v2.1';model.mkdir()
        backbone=root/'mdeberta-v3-base';backbone.mkdir()
        (model/'gliner_config.json').write_text(json.dumps({'model_name':'microsoft/mdeberta-v3-base'}))
        (model/'model.safetensors').write_bytes(b'tiny fixture, not loaded')
        (backbone/'config.json').write_text('{}')
        (backbone/'tokenizer_config.json').write_text('{}')
        (backbone/'spm.model').write_bytes(b'tiny fixture')
        resources=[]
        for directory in (model,backbone):
            for file in directory.iterdir():
                resources.append({'path':file.relative_to(root).as_posix(),'bytes':file.stat().st_size,'sha256':sha256(file.read_bytes()).hexdigest()})
        raw=json.dumps({'resources':resources}).encode()
        (model/'manifest.json').write_bytes(raw)
        return model,backbone,sha256(raw).hexdigest()

    def test_manifest_cannot_authorize_different_consumed_directory(self):
        from tempfile import TemporaryDirectory
        import shutil
        with TemporaryDirectory() as directory:
            root=Path(directory);model,backbone,digest=self.fixture(root)
            other=root/'other';other.mkdir()
            shutil.copyfile(model/'manifest.json',other/'manifest.json')
            shutil.copyfile(model/'gliner_config.json',other/'gliner_config.json')
            (other/'model.safetensors').write_bytes(b'alternative unverified weights')
            with patch('local_anonymizer.ner.PINNED_MANIFEST_SHA256',digest),patch('transformers.AutoTokenizer.from_pretrained',side_effect=RuntimeError('loader reached')) as loader:
                with self.assertRaisesRegex(AnonymizerError,'MODEL_UNAVAILABLE'):EnhancedDetector(other)
                loader.assert_not_called()

    def test_unpinned_tokenizer_selection_rejected_before_loading(self):
        from tempfile import TemporaryDirectory
        for name in ('tokenizer.json','added_tokens.json','special_tokens_map.json','tokenizer.model'):
            with self.subTest(name=name),TemporaryDirectory() as directory:
                root=Path(directory);model,backbone,digest=self.fixture(root)
                (backbone/name).write_text('{"unpinned":true}')
                with patch('local_anonymizer.ner.PINNED_MANIFEST_SHA256',digest),patch('transformers.AutoTokenizer.from_pretrained',side_effect=RuntimeError('loader reached')) as loader:
                    with self.assertRaisesRegex(AnonymizerError,'MODEL_UNAVAILABLE'):EnhancedDetector(model)
                    loader.assert_not_called()

    def test_symlinked_verified_resource_rejected_before_loading(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root=Path(directory);model,backbone,digest=self.fixture(root)
            original=backbone/'spm.model';alternative=root/'same-content.model'
            original.rename(alternative);original.symlink_to(alternative)
            with patch('local_anonymizer.ner.PINNED_MANIFEST_SHA256',digest),patch('transformers.AutoTokenizer.from_pretrained',side_effect=RuntimeError('loader reached')) as loader:
                with self.assertRaisesRegex(AnonymizerError,'MODEL_UNAVAILABLE'):EnhancedDetector(model)
                loader.assert_not_called()

    def test_symlinked_consumed_directory_rejected_before_loading(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root=Path(directory);model,backbone,digest=self.fixture(root)
            alternative=root/'other-backbone';backbone.rename(alternative);backbone.symlink_to(alternative,target_is_directory=True)
            with patch('local_anonymizer.ner.PINNED_MANIFEST_SHA256',digest),patch('transformers.AutoTokenizer.from_pretrained',side_effect=RuntimeError('loader reached')) as loader:
                with self.assertRaisesRegex(AnonymizerError,'MODEL_UNAVAILABLE'):EnhancedDetector(model)
                loader.assert_not_called()

    def test_verified_paths_are_the_consumed_paths(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root=Path(directory);model,backbone,digest=self.fixture(root)
            with patch('local_anonymizer.ner.PINNED_MANIFEST_SHA256',digest),patch('transformers.AutoTokenizer.from_pretrained',side_effect=RuntimeError('stop before fixture weights')) as loader:
                with self.assertRaisesRegex(AnonymizerError,'MODEL_UNAVAILABLE'):EnhancedDetector(model)
                loader.assert_called_once_with(str(backbone.resolve()),local_files_only=True,trust_remote_code=False,fix_mistral_regex=False)
