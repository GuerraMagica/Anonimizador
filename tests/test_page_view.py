import unittest
from io import BytesIO
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from local_anonymizer.page_view import PageViewer
from local_anonymizer.source import RasterPage

class PageViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_drag_is_normalized_and_bound_to_displayed_page(self):
        buf=BytesIO();Image.new('RGB',(200,100),'white').save(buf,format='PNG')
        p=RasterPage(buf.getvalue(),200,100,200,100)
        v=PageViewer(editable=True);v.set_pages((p,p));v.show();self.addCleanup(v.close)
        v.scale.setCurrentText('100%');self.app.processEvents();v.show_page(1)
        regions=[];v.regionAdded.connect(regions.append)
        QTest.mousePress(v.image,Qt.LeftButton,pos=QPoint(20,10))
        QTest.mouseRelease(v.image,Qt.LeftButton,pos=QPoint(100,50))
        self.assertEqual(len(regions),1);self.assertEqual(regions[0].page,1)
        self.assertEqual(regions[0].rect,(.1,.1,.5,.5))
        self.assertEqual(v.visited,{0,1})
    def test_replacing_pages_resets_visited_and_cannot_add_in_readonly(self):
        v=PageViewer(editable=False);self.addCleanup(v.close)
        v.set_pages(());self.assertEqual(v.visited,set())

    def test_navigation_during_drag_discards_region_instead_of_retargeting(self):
        buf=BytesIO();Image.new('RGB',(200,100),'white').save(buf,format='PNG')
        p=RasterPage(buf.getvalue(),200,100,200,100)
        v=PageViewer(editable=True);v.set_pages((p,p));v.show();self.addCleanup(v.close)
        v.scale.setCurrentText('100%');self.app.processEvents();regions=[];v.regionAdded.connect(regions.append)
        QTest.mousePress(v.image,Qt.LeftButton,pos=QPoint(20,10));v.show_page(1)
        QTest.mouseRelease(v.image,Qt.LeftButton,pos=QPoint(100,50))
        self.assertEqual(regions,[])
