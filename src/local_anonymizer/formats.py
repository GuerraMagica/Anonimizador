"""Bounded local raster ingestion. OCR never downloads language resources."""
import hashlib
import math
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

from .domain import AnonymizerError, Document, FileIdentity
from .ingest import load_document, _snapshot
from .source import (LoadedSource, SourceKind, RasterPage, TextBox, MAX_VISUAL_BYTES,
                     MAX_PAGES, MAX_PAGE_PIXELS, MAX_RASTER_BYTES, MAX_TEXT_CHARACTERS)


def _check(cancelled):
    if cancelled(): raise AnonymizerError('CANCELLED')


def _libraries():
    try:
        import pymupdf
        from PIL import Image
        return pymupdf, Image
    except ImportError:
        raise AnonymizerError('VISUAL_DEPENDENCY_UNAVAILABLE') from None


def _tessdata():
    path=Path(sys.prefix)/'models'/'tessdata'
    if not all((path/(lang+'.traineddata')).is_file() for lang in ('spa','eng')):
        raise AnonymizerError('OCR_RESOURCE_UNAVAILABLE')
    return str(path)


def _read(path,cancelled):
    fd=None
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):raise AnonymizerError('INPUT_NOT_REGULAR')
        if before.st_size>MAX_VISUAL_BYTES:raise AnonymizerError('INPUT_BYTE_LIMIT')
        chunks=[];total=0
        while total<=MAX_VISUAL_BYTES:
            _check(cancelled)
            chunk=os.read(fd,min(65536,MAX_VISUAL_BYTES+1-total))
            if not chunk:break
            chunks.append(chunk);total+=len(chunk)
        if total>MAX_VISUAL_BYTES:raise AnonymizerError('INPUT_BYTE_LIMIT')
        if _snapshot(before)!=_snapshot(os.fstat(fd)):raise AnonymizerError('INPUT_CHANGED')
        return b''.join(chunks),FileIdentity(before.st_dev,before.st_ino)
    except OSError:raise AnonymizerError('INPUT_READ') from None
    finally:
        if fd is not None:os.close(fd)


def _ocr_pages_impl(pages,*,cancelled):
    fitz,_=_libraries();tessdata=_tessdata()
    parts=[];boxes=[];offset=0
    for index,page in enumerate(pages):
        _check(cancelled)
        pix=fitz.Pixmap(page.png)
        pdf=pix.pdfocr_tobytes(language='spa+eng',tessdata=tessdata)
        _check(cancelled)
        with fitz.open(stream=pdf,filetype='pdf') as doc:
            words=doc[0].get_text('words',sort=True)
            previous=None
            for x0,y0,x1,y1,word,block,line,*_ in words:
                separator='' if previous is None and offset==0 else ('\n' if previous is None or previous!=(block,line) else ' ')
                parts.append(separator);offset+=len(separator)
                start=offset;parts.append(word);offset+=len(word)
                if offset>MAX_TEXT_CHARACTERS:raise AnonymizerError('INPUT_CHARACTER_LIMIT')
                r=doc[0].rect
                rect=(max(0,x0/r.width),max(0,y0/r.height),min(1,x1/r.width),min(1,y1/r.height))
                boxes.append(TextBox(start,offset,index,rect));previous=(block,line)
    return ''.join(parts),tuple(boxes)


def _ocr_pages(pages,*,cancelled):
    try:
        return _ocr_pages_impl(pages,cancelled=cancelled)
    except AnonymizerError:
        raise
    except Exception:
        raise AnonymizerError('OCR_FAILED') from None


def _raster_pdf(payload,*,cancelled):
    fitz,_=_libraries();pages=[];size=0
    try:
        with fitz.open(stream=payload,filetype='pdf') as doc:
            if doc.needs_pass:raise AnonymizerError('INPUT_ENCRYPTED')
            if not 0<len(doc)<=MAX_PAGES:raise AnonymizerError('INPUT_PAGE_LIMIT')
            notes={'VISUAL_REVIEW_REQUIRED','OCR_CAN_MISS_CONTENT','NONVISIBLE_CONTENT_NOT_INSPECTED'}
            if doc.embfile_count():notes.add('PDF_ATTACHMENTS_EXCLUDED')
            if doc.is_form_pdf:notes.add('PDF_FORMS_FLATTENED')
            if doc.get_sigflags():notes.add('PDF_SIGNATURES_NOT_PRESERVED')
            for page in doc:
                _check(cancelled)
                width,height=page.rect.width,page.rect.height
                if math.ceil(width*150/72)*math.ceil(height*150/72)>MAX_PAGE_PIXELS:
                    raise AnonymizerError('INPUT_PIXEL_LIMIT')
                pix=page.get_pixmap(dpi=150,colorspace=fitz.csRGB,alpha=False,annots=True)
                png=pix.tobytes('png');size+=len(png)
                if size>MAX_RASTER_BYTES:raise AnonymizerError('INPUT_RASTER_LIMIT')
                pages.append(RasterPage(png,width,height,pix.width,pix.height))
            return tuple(pages),tuple(sorted(notes))
    except AnonymizerError:raise
    except Exception:raise AnonymizerError('INPUT_PDF_INVALID') from None


def ocr_pdf(payload:bytes,*,cancelled=lambda:False):
    _check(cancelled)
    pages,_=_raster_pdf(payload,cancelled=cancelled)
    text,boxes=_ocr_pages(pages,cancelled=cancelled)
    return text,pages,boxes


def ocr_rasters(pages,*,cancelled=lambda:False):
    """Second OCR of sanitized pixels; caller must bind verification to visual digest."""
    return _ocr_pages(pages,cancelled=cancelled)[0]


def load_source(path:Path,*,cancelled=lambda:False)->LoadedSource:
    _check(cancelled);path=Path(path);suffix=path.suffix.lower()
    if suffix in ('.txt','.md','.markdown'):
        document=load_document(path);_check(cancelled)
        return LoadedSource(document,SourceKind.TEXT if suffix=='.txt' else SourceKind.MARKDOWN)
    kinds={'.pdf':SourceKind.PDF,'.docx':SourceKind.DOCX,'.png':SourceKind.IMAGE,
           '.jpg':SourceKind.IMAGE,'.jpeg':SourceKind.IMAGE,'.tif':SourceKind.IMAGE,'.tiff':SourceKind.IMAGE}
    if suffix not in kinds:raise AnonymizerError('INPUT_FORMAT')
    payload,identity=_read(path,cancelled);kind=kinds[suffix];notes=()
    if kind==SourceKind.DOCX:
        from .office import convert_docx
        pdf,notes=convert_docx(payload,cancelled=cancelled)
    elif kind==SourceKind.IMAGE:
        fitz,Image=_libraries()
        from io import BytesIO
        pages=[];total=0
        try:
            with Image.open(BytesIO(payload)) as image:
                if image.n_frames>MAX_PAGES:raise AnonymizerError('INPUT_PAGE_LIMIT')
                for i in range(image.n_frames):
                    _check(cancelled);image.seek(i)
                    if image.width*image.height>MAX_PAGE_PIXELS:raise AnonymizerError('INPUT_PIXEL_LIMIT')
                    frame=image.convert('RGB');frame.info.clear();buffer=BytesIO();frame.save(buffer,format='PNG');png=buffer.getvalue();total+=len(png)
                    if total>MAX_RASTER_BYTES:raise AnonymizerError('INPUT_RASTER_LIMIT')
                    pages.append(RasterPage(png,frame.width*72/150,frame.height*72/150,frame.width,frame.height))
        except AnonymizerError:raise
        except Exception:raise AnonymizerError('INPUT_IMAGE_INVALID') from None
        text,boxes=_ocr_pages(tuple(pages),cancelled=cancelled)
        notes=('VISUAL_REVIEW_REQUIRED','OCR_CAN_MISS_CONTENT','NONVISIBLE_CONTENT_NOT_INSPECTED')
        return LoadedSource(Document(str(uuid4()),0,path.absolute(),identity,text,hashlib.sha256(payload).hexdigest()),kind,tuple(pages),boxes,notes)
    else:pdf=payload
    pages,pdf_notes=_raster_pdf(pdf,cancelled=cancelled)
    text,boxes=_ocr_pages(pages,cancelled=cancelled);_check(cancelled)
    return LoadedSource(Document(str(uuid4()),0,path.absolute(),identity,text,hashlib.sha256(payload).hexdigest()),kind,pages,boxes,tuple(sorted(set(notes+pdf_notes))))
