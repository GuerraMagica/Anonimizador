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
            receipt=publish_layout(source,review,preview,verification,visual,dest)
            with fitz.open(dest) as doc:
                self.assertEqual(doc[0].get_text(),'')
                self.assertEqual(doc.embfile_count(),0)
                self.assertEqual(len(doc[0].get_images()),1)
            with self.assertRaisesRegex(AnonymizerError,'EXPORT_EXISTS'):
                publish_layout(source,review,preview,verification,visual,dest)
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
