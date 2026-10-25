import unittest
from local_anonymizer.layout import VisualPreview

class LayoutTests(unittest.TestCase):
    def test_sensitive_repr(self):
        self.assertNotIn('secret',repr(VisualPreview(0,'hash',(b'secret',),'hash')))

from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from dataclasses import replace
from PIL import Image
import pymupdf as fitz
from local_anonymizer.domain import *
from local_anonymizer.source import *
from local_anonymizer.transform import build_preview
from local_anonymizer.layout import build_visual_preview,publish_layout,_pdf_bytes

class RasterTests(unittest.TestCase):
    def evidence(self,source,review,preview,visual,**kwargs):
        with patch('local_anonymizer.formats.ocr_raster_details',return_value=('otros',())):
            return verify_visual(source,review,preview,visual,EmptyDetector(),human_confirmed=True,**kwargs)
    def fixture(self):
        image=Image.new('RGB',(400,200),'white')
        from PIL import ImageDraw
        ImageDraw.Draw(image).rectangle((40,40,160,80),fill='red')
        stream=BytesIO();image.save(stream,format='PNG')
        page=RasterPage(stream.getvalue(),192,96,400,200)
        doc=Document('session',0,Path('/tmp/synthetic-original.pdf'),FileIdentity(1,2),'Maria otros','digest')
        source=LoadedSource(doc,SourceKind.PDF,(page,),(TextBox(0,5,0,(.1,.2,.4,.4)),TextBox(6,11,0,(.5,.2,.8,.4))))
        f=Finding('id','session',1,3,Category.PERSONA,Confidentiality.PII,('manual',))
        review=Review(doc,(f,),(Decision('id',Disposition.ACCEPT,Action.REDACT),),coverage_complete=True,confirmed=True)
        preview=build_preview(review)
        verification=Verification('session',0,preview.sha256,'test',True,())
        return source,review,preview,verification
    def test_full_word_pixels_and_manual_region(self):
        source,review,preview,_=self.fixture()
        visual=build_visual_preview(source,review,preview,(VisualRegion(0,(.6,.6,.9,.9)),))
        image=Image.open(BytesIO(visual.pages[0].png))
        self.assertNotEqual(image.getpixel((40,40)),(255,0,0))
        self.assertEqual(image.getpixel((150,75)),(0,0,0))
        self.assertEqual(image.getpixel((280,150)),(0,0,0))
        self.assertEqual(image.getpixel((390,190)),(255,255,255))
        self.assertNotEqual(visual.pages,source.pages)
    def test_publication_graph_and_exact_pixels(self):
        source,review,preview,verification=self.fixture()
        visual=build_visual_preview(source,review,preview)
        with TemporaryDirectory() as d:
            dest=Path(d)/'safe.pdf'
            evidence=self.evidence(source,review,preview,visual)
            receipt=publish_layout(source,review,preview,verification,visual,dest,visual_verification=evidence)
            with fitz.open(dest) as doc:
                self.assertEqual(doc[0].get_text(),'')
                self.assertEqual(doc.embfile_count(),0)
                self.assertEqual(len(doc[0].get_images()),1)
            with self.assertRaisesRegex(AnonymizerError,'EXPORT_EXISTS'):
                publish_layout(source,review,preview,verification,visual,dest,visual_verification=evidence)
    def test_stale_and_unconfirmed_blocked(self):
        source,review,preview,verification=self.fixture();visual=build_visual_preview(source,review,preview)
        with self.assertRaisesRegex(AnonymizerError,'EXPORT_NOT_VERIFIED'):
            publish_layout(source,replace(review,confirmed=False),preview,verification,visual,Path('/tmp/no.pdf'))
        with self.assertRaisesRegex(AnonymizerError,'VISUAL_STATE_MISMATCH'):
            publish_layout(source,review,preview,verification,visual,Path('/tmp/no.pdf'),(VisualRegion(0,(.6,.6,.9,.9)),))
    def test_wrong_source_region_and_preview(self):
        source,review,preview,_=self.fixture()
        with self.assertRaises(AnonymizerError):build_visual_preview(source,review,preview,(VisualRegion(1,(.1,.1,.2,.2)),))
        with self.assertRaises(AnonymizerError):build_visual_preview(source,review,replace(preview,text='bad'))
    def test_tampered_visual_and_verification_blocked(self):
        source,review,preview,verification=self.fixture();visual=build_visual_preview(source,review,preview)
        with self.assertRaisesRegex(AnonymizerError,'VISUAL_STATE_MISMATCH'):
            publish_layout(source,review,preview,verification,replace(visual,sha256='tampered'),Path('/tmp/no.pdf'))
        with self.assertRaisesRegex(AnonymizerError,'EXPORT_NOT_VERIFIED'):
            publish_layout(source,review,preview,replace(verification,preview_sha256='stale'),visual,Path('/tmp/no.pdf'))
    def test_label_that_does_not_fit_is_opaque(self):
        source,review,preview,_=self.fixture()
        source=replace(source,boxes=(TextBox(0,5,0,(.1,.2,.12,.25)),))
        visual=build_visual_preview(source,review,preview)
        image=Image.open(BytesIO(visual.pages[0].png))
        self.assertEqual(image.getpixel((44,45)),(0,0,0))
    def test_png_metadata_removed(self):
        source,review,preview,_=self.fixture()
        image=Image.open(BytesIO(source.pages[0].png))
        exif=Image.Exif();exif[270]='PRIVATE ORIGINAL METADATA'
        stream=BytesIO();image.save(stream,format='PNG',exif=exif)
        source=replace(source,pages=(replace(source.pages[0],png=stream.getvalue()),))
        visual=build_visual_preview(source,review,preview)
        self.assertNotIn(b'PRIVATE',visual.pages[0].png)
        self.assertFalse(Image.open(BytesIO(visual.pages[0].png)).getexif())

from unittest.mock import patch
from local_anonymizer.layout import verify_visual

class EmptyDetector:
    fingerprint='test'
    def analyze(self,text,session_id):return ()

class VisualGateTests(RasterTests):
    def evidence(self,source,review,preview,visual,**kwargs):
        with patch('local_anonymizer.formats.ocr_raster_details',return_value=('otros',())):
            return verify_visual(source,review,preview,visual,EmptyDetector(),human_confirmed=True,**kwargs)
    def test_missing_visual_evidence_and_human_confirmation_block_publication(self):
        source,review,preview,verification=self.fixture();visual=build_visual_preview(source,review,preview)
        with self.assertRaisesRegex(AnonymizerError,'VISUAL_VERIFICATION_REQUIRED'):
            publish_layout(source,review,preview,verification,visual,Path('/tmp/no.pdf'))
        with patch('local_anonymizer.formats.ocr_raster_details',return_value=('otros',())):
            evidence=verify_visual(source,review,preview,visual,EmptyDetector())
        self.assertFalse(evidence.ok);self.assertIn('VISUAL_HUMAN_REVIEW_REQUIRED',evidence.issues)
        with self.assertRaisesRegex(AnonymizerError,'VISUAL_VERIFICATION_REQUIRED'):
            publish_layout(source,review,preview,verification,visual,Path('/tmp/no.pdf'),visual_verification=evidence)
    def test_current_evidence_publishes_but_stale_bindings_block(self):
        source,review,preview,verification=self.fixture();visual=build_visual_preview(source,review,preview)
        evidence=self.evidence(source,review,preview,visual)
        self.assertTrue(evidence.ok)
        with TemporaryDirectory() as d:
            publish_layout(source,review,preview,verification,visual,Path(d)/'safe.pdf',visual_verification=evidence)
        for changes in ({'review_revision':1},{'visual_sha256':'stale'},{'text_sha256':'stale'},
                        {'session_id':'other'},{'detector_fingerprint':'other'},
                        {'ocr_sha256':'stale'},{'human_confirmed':False}):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(AnonymizerError,'VISUAL_VERIFICATION_REQUIRED'):
                    publish_layout(source,review,preview,verification,visual,Path('/tmp/no.pdf'),visual_verification=replace(evidence,**changes))
    def test_second_ocr_selected_values_cannot_be_overridden(self):
        source,review,preview,_=self.fixture();visual=build_visual_preview(source,review,preview)
        with patch('local_anonymizer.formats.ocr_raster_details',return_value=('ar',())):
            evidence=verify_visual(source,review,preview,visual,EmptyDetector(),human_confirmed=True)
        self.assertFalse(evidence.ok);self.assertIn('SELECTED_VALUE_REMAINS',evidence.issues)
    def test_residual_rejection_bound_to_pixels_revision_and_ocr(self):
        source,review,preview,_=self.fixture();visual=build_visual_preview(source,review,preview)
        class Detector(EmptyDetector):
            def analyze(self,text,session_id):
                return (Finding('residual',session_id,0,5,Category.PERSONA,Confidentiality.PII,('test',)),)
        with patch('local_anonymizer.formats.ocr_raster_details',return_value=('otros',())):
            first=verify_visual(source,review,preview,visual,Detector(),human_confirmed=True)
            self.assertEqual(len(first.residuals),1)
            rejections=(ResidualDecision(first.residuals[0].key),)
            accepted=verify_visual(source,review,preview,visual,Detector(),human_confirmed=True,rejections=rejections)
            self.assertTrue(accepted.ok)
            regions=(VisualRegion(0,(.8,.8,.9,.9)),)
            changed=build_visual_preview(source,review,preview,regions)
            expired=verify_visual(source,review,preview,changed,Detector(),regions=regions,human_confirmed=True,rejections=rejections)
            self.assertEqual(len(expired.residuals),1)
        with patch('local_anonymizer.formats.ocr_raster_details',return_value=('otros mas',())):
            expired=verify_visual(source,review,preview,visual,Detector(),human_confirmed=True,rejections=rejections)
            self.assertEqual(len(expired.residuals),1)
        self.assertNotIn('otros',repr(first))
    def test_changed_detector_invalid_candidates_cancel_and_ocr_failure(self):
        source,review,preview,_=self.fixture();visual=build_visual_preview(source,review,preview)
        with self.assertRaisesRegex(AnonymizerError,'CANCELLED'):
            verify_visual(source,review,preview,visual,EmptyDetector(),human_confirmed=True,cancelled=lambda:True)
        with patch('local_anonymizer.formats.ocr_raster_details',side_effect=AnonymizerError('OCR_FAILED')):
            evidence=verify_visual(source,review,preview,visual,EmptyDetector(),human_confirmed=True)
            self.assertFalse(evidence.ok);self.assertIn('OCR_FAILED',evidence.issues)
        class Changing(EmptyDetector):
            def analyze(self,text,session_id):self.fingerprint='different';return ()
        with patch('local_anonymizer.formats.ocr_raster_details',return_value=('otros',())):
            evidence=verify_visual(source,review,preview,visual,Changing(),human_confirmed=True)
            self.assertIn('DETECTOR_CHANGED',evidence.issues)
