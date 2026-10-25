"""Raster redaction and exclusive image-only PDF publication."""
from dataclasses import dataclass,field
import hashlib
from io import BytesIO
import math
from pathlib import Path

from .domain import AnonymizerError
from .source import RasterPage,VisualRegion
from .transform import build_preview
from .export import _publish_bytes

@dataclass(frozen=True,slots=True)
class VisualPreview:
    review_revision:int
    text_sha256:str
    pages:tuple[RasterPage,...]=field(repr=False)
    sha256:str


def _digest(pages):
    digest=hashlib.sha256()
    for page in pages:
        digest.update(repr((page.width_points,page.height_points,page.pixel_width,page.pixel_height)).encode())
        digest.update(hashlib.sha256(page.png).digest())
    return digest.hexdigest()


def build_visual_preview(source,review,preview,regions=()):
    from PIL import Image,ImageDraw,ImageFont
    regions=tuple(regions)
    if source.document!=review.document or preview!=build_preview(review) or not source.pages:
        raise AnonymizerError('VISUAL_STATE_MISMATCH')
    if any(not isinstance(r,VisualRegion) or r.page>=len(source.pages) for r in regions):
        raise AnonymizerError('INVALID_VISUAL_REGION')
    pages=[]
    for index,page in enumerate(source.pages):
        image=Image.open(BytesIO(page.png)).convert('RGB')
        image.info.clear()
        if image.size!=(page.pixel_width,page.pixel_height):raise AnonymizerError('INVALID_RASTER_PAGE')
        draw=ImageDraw.Draw(image);redactions=[]
        for segment in preview.segments:
            if segment.finding_id is None:continue
            matches=[box for box in source.boxes if box.page==index and box.start<segment.source_end and box.end>segment.source_start]
            for box in matches:
                redactions.append((box.rect,''))
            # Label only in a single full-word rectangle when legible; never expose partial words.
            if len(matches)==1:
                redactions[-1]=(matches[0].rect,preview.text[segment.output_start:segment.output_end])
        redactions.extend((r.rect,'') for r in regions if r.page==index)
        pixel_rects=[]
        for rect,label in redactions:
            x0,y0,x1,y1=rect
            coords=(max(0,math.floor(x0*image.width)-3),max(0,math.floor(y0*image.height)-3),
                    min(image.width-1,math.ceil(x1*image.width)+3),min(image.height-1,math.ceil(y1*image.height)+3))
            draw.rectangle(coords,fill='black');pixel_rects.append((coords,label))
        font=ImageFont.load_default(size=14)
        # All original pixels removed first; labels are public generated tokens.
        for coords,label in pixel_rects:
            if not label:continue
            bbox=draw.textbbox((0,0),label,font=font)
            if bbox[2]-bbox[0]+4<=coords[2]-coords[0] and bbox[3]-bbox[1]+4<=coords[3]-coords[1]:
                draw.text((coords[0]+2,coords[1]+2-bbox[1]),label,font=font,fill='white')
        stream=BytesIO();image.save(stream,format='PNG')
        pages.append(RasterPage(stream.getvalue(),page.width_points,page.height_points,page.pixel_width,page.pixel_height))
    pages=tuple(pages)
    return VisualPreview(review.revision,preview.sha256,pages,_digest(pages))


def _pdf_bytes(pages):
    import pymupdf as fitz
    from PIL import Image
    with fitz.open() as doc:
        for raster in pages:
            page=doc.new_page(width=raster.width_points,height=raster.height_points)
            page.insert_image(page.rect,stream=raster.png)
        payload=doc.tobytes(garbage=4,deflate=True)
    with fitz.open(stream=payload,filetype='pdf') as check:
        if len(check)!=len(pages) or check.embfile_count() or check.is_form_pdf or check.get_xml_metadata():
            raise AnonymizerError('LAYOUT_EXPORT_MISMATCH')
        for page,expected in zip(check,pages):
            images=page.get_images(full=True)
            if (page.get_text() or list(page.annots() or ()) or page.get_links() or len(images)!=1
                    or abs(page.rect.width-expected.width_points)>.001
                    or abs(page.rect.height-expected.height_points)>.001):
                raise AnonymizerError('LAYOUT_EXPORT_MISMATCH')
            actual=fitz.Pixmap(check,images[0][0]);target=Image.open(BytesIO(expected.png)).convert('RGB')
            if (actual.width,actual.height)!=target.size or actual.samples!=target.tobytes():
                raise AnonymizerError('LAYOUT_EXPORT_MISMATCH')
        # A fresh image-only graph cannot contain imported text/actions/metadata.
        for xref in range(1,check.xref_length()):
            obj=check.xref_object(xref)
            if any(token in obj for token in ('/JavaScript','/OpenAction','/AA ','/EmbeddedFiles','/AcroForm','/Metadata')):
                raise AnonymizerError('LAYOUT_EXPORT_MISMATCH')
    return payload


def publish_layout(source,review,preview,verification,visual,destination,regions=()):
    if (review.confirmed is not True or not verification.ok or verification.issues or verification.residuals
            or verification.detector_fingerprint=='unavailable'
            or verification.session_id!=review.document.session_id
            or verification.review_revision!=review.revision or verification.preview_sha256!=preview.sha256):
        raise AnonymizerError('EXPORT_NOT_VERIFIED')
    expected=build_visual_preview(source,review,preview,regions)
    if expected!=visual:raise AnonymizerError('VISUAL_STATE_MISMATCH')
    if Path(destination).absolute()==source.document.source_path:raise AnonymizerError('EXPORT_ORIGINAL')
    return _publish_bytes(_pdf_bytes(expected.pages),destination)
