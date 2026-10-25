"""Scrollable raster pages with optional manual area redactions."""
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QScrollArea
from .source import VisualRegion


class _Page(QLabel):
    regionAdded = Signal(object)

    def __init__(self, owner):
        super().__init__();self.owner=owner;self.origin=None;self.point=None
        self.setAccessibleName('Página visual; arrastra para redactar una zona')

    def mousePressEvent(self, event):
        if self.owner.editable and self.owner.pages and event.button()==Qt.LeftButton:
            self.origin=event.position().toPoint();self.point=self.origin

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.point=event.position().toPoint();self.update()

    def mouseReleaseEvent(self, event):
        if self.origin is None:return
        end=event.position().toPoint();start=self.origin;self.origin=self.point=None
        x0,x1=sorted((max(0,min(1,start.x()/self.width())),max(0,min(1,end.x()/self.width()))))
        y0,y1=sorted((max(0,min(1,start.y()/self.height())),max(0,min(1,end.y()/self.height()))))
        if x1-x0>=.002 and y1-y0>=.002:
            self.owner.regionAdded.emit(VisualRegion(self.owner.index,(x0,y0,x1,y1)))
        self.update()

    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self);painter.setPen(QColor('red'))
        for region in self.owner.regions:
            if region.page==self.owner.index:
                x0,y0,x1,y1=region.rect
                painter.drawRect(QRect(int(x0*self.width()),int(y0*self.height()),
                                       int((x1-x0)*self.width()),int((y1-y0)*self.height())))
        if self.origin is not None and self.point is not None:
            painter.drawRect(QRect(self.origin,self.point).normalized())
        painter.end()


class PageViewer(QWidget):
    regionAdded=Signal(object)
    pageViewed=Signal(int)

    def __init__(self, *, editable=False):
        super().__init__();self.editable=editable;self.pages=();self.regions=();self.index=0;self.visited=set()
        layout=QVBoxLayout(self);bar=QHBoxLayout();layout.addLayout(bar)
        self.previous=QPushButton('Página anterior');bar.addWidget(self.previous)
        self.caption=QLabel();bar.addWidget(self.caption)
        self.next=QPushButton('Página siguiente');bar.addWidget(self.next)
        self.scale=QComboBox();self.scale.addItems(('50%','75%','100%','150%'));bar.addWidget(self.scale)
        self.image=_Page(self);scroll=QScrollArea();scroll.setWidget(self.image);layout.addWidget(scroll)
        self.previous.clicked.connect(lambda:self.show_page(self.index-1))
        self.next.clicked.connect(lambda:self.show_page(self.index+1))
        self.scale.currentIndexChanged.connect(lambda:self.show_page(self.index))
        self.set_pages(())

    def set_pages(self,pages,regions=()):
        self.pages=tuple(pages);self.regions=tuple(regions);self.visited=set();self.index=0
        self.show_page(0)

    def show_page(self,index):
        self.image.origin=self.image.point=None
        self.index=max(0,min(index,len(self.pages)-1))
        self.previous.setEnabled(bool(self.pages) and self.index>0)
        self.next.setEnabled(bool(self.pages) and self.index+1<len(self.pages))
        self.caption.setText(f'{self.index+1} / {len(self.pages)}' if self.pages else 'Sin páginas')
        if not self.pages:
            self.image.clear();self.image.resize(1,1);return
        pix=QPixmap();pix.loadFromData(self.pages[self.index].png)
        factor=int(self.scale.currentText().rstrip('%'))/100
        pix=pix.scaled(max(1,int(pix.width()*factor)),max(1,int(pix.height()*factor)),Qt.KeepAspectRatio,Qt.SmoothTransformation)
        self.image.setPixmap(pix);self.image.setFixedSize(pix.size())
        # Only mark pages exposed in the visible viewer; hidden tabs do not count.
        if self.isVisible():
            self.visited.add(self.index);self.pageViewed.emit(self.index)

    def showEvent(self,event):
        super().showEvent(event);self.show_page(self.index)
