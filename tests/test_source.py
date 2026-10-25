import unittest
from dataclasses import replace
from helpers import document
from local_anonymizer.domain import AnonymizerError
from local_anonymizer.source import SourceKind,RasterPage,TextBox,VisualRegion,LoadedSource

class SourceContractTests(unittest.TestCase):
    def page(self):return RasterPage(b'PRIVATE_PNG',595,842,1240,1754)
    def test_sensitive_payloads_not_in_repr(self):
        source=LoadedSource(document('PRIVATE_TEXT'),SourceKind.PDF,(self.page(),),(TextBox(0,7,0,(.1,.2,.3,.4)),),())
        self.assertNotIn('PRIVATE_PNG',repr(source));self.assertNotIn('PRIVATE_TEXT',repr(source))
    def test_regions_require_positive_normalized_finite_rects(self):
        for rect in ((0,0,2,1),(0,0,0,1),(float('nan'),0,.5,1),(-.1,0,.5,1)):
            with self.subTest(rect=rect):
                with self.assertRaises(AnonymizerError):VisualRegion(0,rect)
        with self.assertRaises(AnonymizerError):VisualRegion(-1,(0,0,1,1))
    def test_source_checks_boxes_against_text_and_pages(self):
        with self.assertRaises(AnonymizerError):LoadedSource(document('abc'),SourceKind.PDF,(self.page(),),(TextBox(0,9,0,(0,0,1,1)),),())
        with self.assertRaises(AnonymizerError):LoadedSource(document('abc'),SourceKind.PDF,(self.page(),),(TextBox(0,2,1,(0,0,1,1)),),())
    def test_invalid_pixel_dimensions_rejected(self):
        for value in (0,-1,100000):
            with self.assertRaises(AnonymizerError):replace(self.page(),pixel_width=value)

if __name__=='__main__':unittest.main()
