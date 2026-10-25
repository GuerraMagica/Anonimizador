"""Immutable canonical text and visual source coordinates, never original repr."""
from dataclasses import dataclass,field
from enum import StrEnum
import math
import re
from .domain import AnonymizerError,Document

MAX_VISUAL_BYTES=50*1024*1024
MAX_PAGES=50
MAX_PAGE_PIXELS=20_000_000
MAX_RASTER_BYTES=300*1024*1024
MAX_TEXT_CHARACTERS=100_000
MAX_BATCH_FILES=20
MAX_BATCH_BYTES=200*1024*1024


class SourceKind(StrEnum):
    TEXT='text'
    MARKDOWN='markdown'
    PDF='pdf'
    DOCX='docx'
    IMAGE='image'


def validate_rect(rect):
    if (not isinstance(rect,tuple) or len(rect)!=4
            or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in rect)
            or rect[0]>=rect[2] or rect[1]>=rect[3]):
        raise AnonymizerError('INVALID_VISUAL_RECT')


@dataclass(frozen=True,slots=True)
class RasterPage:
    png: bytes=field(repr=False)
    width_points: float
    height_points: float
    pixel_width: int
    pixel_height: int

    def __post_init__(self):
        if (not isinstance(self.png,bytes) or not self.png or len(self.png)>MAX_RASTER_BYTES
                or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=14400
                       for v in (self.width_points,self.height_points))
                or any(type(v) is not int or v<=0 for v in (self.pixel_width,self.pixel_height))
                or self.pixel_width*self.pixel_height>MAX_PAGE_PIXELS):
            raise AnonymizerError('INVALID_RASTER_PAGE')


@dataclass(frozen=True,slots=True)
class TextBox:
    start: int
    end: int
    page: int
    rect: tuple[float,float,float,float]

    def __post_init__(self):
        validate_rect(self.rect)
        if (type(self.start) is not int or type(self.end) is not int or type(self.page) is not int
                or self.start<0 or self.end<=self.start or self.page<0):
            raise AnonymizerError('INVALID_TEXT_BOX')


@dataclass(frozen=True,slots=True)
class VisualRegion:
    page: int
    rect: tuple[float,float,float,float]

    def __post_init__(self):
        validate_rect(self.rect)
        if type(self.page) is not int or self.page<0:raise AnonymizerError('INVALID_VISUAL_REGION')


@dataclass(frozen=True,slots=True)
class LoadedSource:
    document: Document
    kind: SourceKind
    pages: tuple[RasterPage,...]=()
    boxes: tuple[TextBox,...]=()
    notes: tuple[str,...]=()
    input_bytes: int=0

    def __post_init__(self):
        if (not isinstance(self.document,Document) or not isinstance(self.kind,SourceKind)
                or type(self.input_bytes) is not int or not 0<=self.input_bytes<=MAX_VISUAL_BYTES
                or len(self.document.text)>MAX_TEXT_CHARACTERS
                or not isinstance(self.pages,tuple) or len(self.pages)>MAX_PAGES
                or not isinstance(self.boxes,tuple) or not isinstance(self.notes,tuple)
                or any(not isinstance(p,RasterPage) for p in self.pages)
                or sum(len(p.png) for p in self.pages)>MAX_RASTER_BYTES
                or any(not isinstance(b,TextBox) or b.end>len(self.document.text)
                       or b.page>=len(self.pages) for b in self.boxes)
                or any(not isinstance(n,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}',n) for n in self.notes)):
            raise AnonymizerError('INVALID_LOADED_SOURCE')
        if self.kind in (SourceKind.PDF,SourceKind.DOCX,SourceKind.IMAGE) and not self.pages:
            raise AnonymizerError('VISUAL_PAGES_REQUIRED')
