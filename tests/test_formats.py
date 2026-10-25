import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from local_anonymizer.domain import AnonymizerError
from local_anonymizer.formats import load_source,ocr_pdf

class FormatTests(unittest.TestCase):
    def test_text_source_and_cancel(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'test.txt';p.write_text('Hola')
            self.assertEqual(load_source(p).document.text,'Hola')
            with self.assertRaisesRegex(AnonymizerError,'CANCELLED'):load_source(p,cancelled=lambda:True)
    def test_reject_visual_symlink(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'test.pdf';p.symlink_to('/etc/hosts')
            with self.assertRaises(AnonymizerError):load_source(p)
    def test_invalid_pdf(self):
        with self.assertRaises(AnonymizerError):ocr_pdf(b'invalid')

from unittest.mock import patch
import hashlib
import pymupdf as fitz
from local_anonymizer.formats import _raster_pdf

class PdfTests(unittest.TestCase):
    def native(self,pages=1):
        with fitz.open() as pdf:
            for _ in range(pages):
                page=pdf.new_page(width=400,height=200)
                page.insert_text((30,70),'Maria Garcia confidential project',fontsize=22)
            pdf.set_metadata({'title':'SECRET METADATA'})
            return pdf.tobytes()
    def test_page_pixel_limits_and_cancel(self):
        with patch('local_anonymizer.formats.MAX_PAGES',1):
            with self.assertRaisesRegex(AnonymizerError,'INPUT_PAGE_LIMIT'):_raster_pdf(self.native(2),cancelled=lambda:False)
        with patch('local_anonymizer.formats.MAX_PAGE_PIXELS',10):
            with self.assertRaisesRegex(AnonymizerError,'INPUT_PIXEL_LIMIT'):_raster_pdf(self.native(),cancelled=lambda:False)
        with self.assertRaisesRegex(AnonymizerError,'CANCELLED'):_raster_pdf(self.native(),cancelled=lambda:True)
    def test_encryption(self):
        with fitz.open(stream=self.native(),filetype='pdf') as pdf:
            data=pdf.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='secret',user_pw='secret')
        with self.assertRaisesRegex(AnonymizerError,'INPUT_ENCRYPTED'):ocr_pdf(data)
    def test_missing_resource(self):
        with patch('local_anonymizer.formats._tessdata',side_effect=AnonymizerError('OCR_RESOURCE_UNAVAILABLE')):
            with self.assertRaisesRegex(AnonymizerError,'OCR_RESOURCE_UNAVAILABLE'):ocr_pdf(self.native())
    def test_real_native_scanned_image_and_boxes(self):
        from PIL import Image
        from io import BytesIO
        data=self.native()
        text,pages,boxes=ocr_pdf(data)
        self.assertIn('Maria',text)
        self.assertEqual(len(pages),1)
        self.assertTrue(boxes)
        self.assertTrue(all(text[b.start:b.end].strip() for b in boxes))
        with TemporaryDirectory() as d:
            p=Path(d)/'native.pdf';p.write_bytes(data)
            loaded=load_source(p)
            self.assertEqual(loaded.document.source_sha256,hashlib.sha256(data).hexdigest())
            self.assertEqual(p.read_bytes(),data)
            image=Path(d)/'image.png';image.write_bytes(pages[0].png)
            self.assertIn('Maria',load_source(image).document.text)
            with fitz.open() as pdf:
                page=pdf.new_page(width=400,height=200);page.insert_image(page.rect,stream=pages[0].png)
                scan=pdf.tobytes()
            self.assertIn('Maria',ocr_pdf(scan)[0])
    def test_pages_unicode_limits_offsets_and_attachment_notes(self):
        with fitz.open() as pdf:
            for line in ('Maria Garcia telefono Madrid','English confidential project London'):
                page=pdf.new_page(width=500,height=180);page.insert_text((25,70),line,fontsize=22)
            pdf.embfile_add('hidden.txt',b'synthetic hidden secret')
            data=pdf.tobytes()
        text,pages,boxes=ocr_pdf(data)
        self.assertEqual({b.page for b in boxes},{0,1})
        self.assertIn('English',text)
        self.assertEqual(sum(len(text[b.start:b.end]) for b in boxes),len(''.join(text.split())))
        with patch('local_anonymizer.formats.MAX_TEXT_CHARACTERS',10):
            with self.assertRaisesRegex(AnonymizerError,'INPUT_CHARACTER_LIMIT'):ocr_pdf(data)
        with TemporaryDirectory() as d:
            p=Path(d)/'attachment.pdf';p.write_bytes(data)
            self.assertIn('PDF_ATTACHMENTS_EXCLUDED',load_source(p).notes)
        counter=[0]
        def cancel():
            counter[0]+=1
            return counter[0]>3
        with self.assertRaisesRegex(AnonymizerError,'CANCELLED'):ocr_pdf(data,cancelled=cancel)
    def test_bounded_bytes_and_image_frames(self):
        from PIL import Image
        with TemporaryDirectory() as d:
            p=Path(d)/'native.pdf';p.write_bytes(self.native())
            with patch('local_anonymizer.formats.MAX_VISUAL_BYTES',10):
                with self.assertRaisesRegex(AnonymizerError,'INPUT_BYTE_LIMIT'):load_source(p)
            image=Path(d)/'pages.tiff'
            Image.new('RGB',(200,100),'white').save(image,save_all=True,append_images=[Image.new('RGB',(200,100),'white')])
            self.assertEqual(len(load_source(image).pages),2)
            with patch('local_anonymizer.formats.MAX_PAGE_PIXELS',100):
                with self.assertRaisesRegex(AnonymizerError,'INPUT_PIXEL_LIMIT'):load_source(image)
    def test_ocr_failure_is_sanitized(self):
        with patch('local_anonymizer.formats._ocr_pages_impl',side_effect=RuntimeError('sensitive path and content')):
            with self.assertRaisesRegex(AnonymizerError,'^OCR_FAILED$'):ocr_pdf(self.native())
    def test_no_python_network_or_onnx_import(self):
        import sys,socket
        with patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
            text,pages,boxes=ocr_pdf(self.native())
            with TemporaryDirectory() as d:
                p=Path(d)/'network.pdf';p.write_bytes(self.native())
                self.assertIn('Maria',load_source(p).document.text)
        self.assertIn('Maria',text)
        self.assertNotIn('onnxruntime',sys.modules)
