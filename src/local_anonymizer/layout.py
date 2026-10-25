"""Raster redaction and exclusive image-only PDF publication."""
from dataclasses import dataclass,field
import hashlib
from io import BytesIO
import math
import re
from pathlib import Path

from .domain import AnonymizerError,Finding,ResidualCandidate,ResidualDecision,ResidualKey
from .source import RasterPage,VisualRegion,TextBox
from .transform import build_preview
from .export import _publish_bytes

@dataclass(frozen=True,slots=True)
class VisualPreview:
    review_revision:int
    text_sha256:str
    pages:tuple[RasterPage,...]=field(repr=False)
    sha256:str


@dataclass(frozen=True,slots=True)
class VisualVerification:
    session_id:str
    review_revision:int
    text_sha256:str
    visual_sha256:str
    detector_fingerprint:str
    ocr_sha256:str
    ok:bool
    human_confirmed:bool
    issues:tuple[str,...]
    residuals:tuple[ResidualCandidate,...]=()
    ocr_text:str=field(default='',repr=False)
    boxes:tuple[TextBox,...]=()


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


def verify_visual(source,review,preview,visual,detector,*,regions=(),human_confirmed=False,
                  rejections=(),cancelled=lambda:False):
    """Check exactly the reviewed pixels; OCR residual decisions never inherit by value.

    Human confirmation must come from review of this visual preview. This check
    complements text verification and cannot guarantee OCR found all visible data.
    """
    from .formats import ocr_raster_details
    from .detectors import MAX_ANALYSIS_CHARACTERS
    fingerprint='unavailable';text='';boxes=();ocr_sha256=hashlib.sha256(b'').hexdigest()
    issues=[]
    def check_cancelled():
        if cancelled():raise AnonymizerError('CANCELLED')
    def result(residuals=()):
        return VisualVerification(review.document.session_id,review.revision,preview.sha256,
                                  visual.sha256,fingerprint,ocr_sha256,not issues,
                                  human_confirmed is True,tuple(issues),tuple(residuals),text,boxes)
    check_cancelled()
    if review.confirmed is not True:issues.append('HUMAN_REVIEW_REQUIRED')
    if human_confirmed is not True:issues.append('VISUAL_HUMAN_REVIEW_REQUIRED')
    try:
        expected=build_visual_preview(source,review,preview,regions)
        if expected!=visual:raise AnonymizerError('VISUAL_STATE_MISMATCH')
    except AnonymizerError as error:
        issues.append(error.code);return result()
    if issues:return result()
    try:
        text,boxes=ocr_raster_details(visual.pages,cancelled=cancelled)
        if (not isinstance(text,str) or len(text)>MAX_ANALYSIS_CHARACTERS or not isinstance(boxes,tuple)
                or any(not isinstance(b,TextBox) or b.end>len(text) or b.page>=len(visual.pages) for b in boxes)):
            raise AnonymizerError('OCR_FAILED')
        ocr_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest()
        check_cancelled()
    except AnonymizerError as error:
        if error.code=='CANCELLED':raise
        issues.append(error.code);return result()
    except Exception:
        issues.append('OCR_FAILED');return result()
    if any(value in text for value in preview.selected_values):issues.append('SELECTED_VALUE_REMAINS')
    try:
        fingerprint=detector.fingerprint
        if not isinstance(fingerprint,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}',fingerprint):
            fingerprint='unavailable';raise AnonymizerError('ANALYSIS_FAILED')
        analyze=getattr(detector,'analyze_cancellable',None)
        candidates=analyze(text,review.document.session_id,cancelled) if analyze else detector.analyze(text,review.document.session_id)
        check_cancelled()
        if not isinstance(candidates,tuple) or any(not isinstance(c,Finding) or c.end>len(text)
                or c.session_id!=review.document.session_id for c in candidates):
            raise AnonymizerError('ANALYSIS_FAILED')
        if detector.fingerprint!=fingerprint:raise AnonymizerError('DETECTOR_CHANGED')
        if not isinstance(rejections,tuple) or any(not isinstance(d,ResidualDecision) for d in rejections):
            raise AnonymizerError('INVALID_RESIDUAL_DECISION')
    except AnonymizerError as error:
        if error.code=='CANCELLED':raise
        issues.append(error.code);return result()
    except Exception:
        issues.append('ANALYSIS_FAILED');return result()
    # Domain-separated digest: a rejection expires on text, OCR, or pixel changes.
    binding=hashlib.sha256(('visual-verification:v1:'+preview.sha256+':'+visual.sha256+':'+ocr_sha256).encode()).hexdigest()
    rejected_keys={d.key for d in rejections};pending=[]
    for candidate in candidates:
        key=ResidualKey(review.document.session_id,review.revision,binding,fingerprint,
                        candidate.start,candidate.end,candidate.category,candidate.provenance)
        if key not in rejected_keys:pending.append(ResidualCandidate(candidate,key))
    if pending:issues.append('RESIDUAL_REVIEW_REQUIRED')
    return result(pending)


def publish_layout(source,review,preview,verification,visual,destination,regions=(),*,visual_verification=None):
    if (review.confirmed is not True or not verification.ok or verification.issues or verification.residuals
            or verification.detector_fingerprint=='unavailable'
            or verification.session_id!=review.document.session_id
            or verification.review_revision!=review.revision or verification.preview_sha256!=preview.sha256):
        raise AnonymizerError('EXPORT_NOT_VERIFIED')
    expected=build_visual_preview(source,review,preview,regions)
    if expected!=visual:raise AnonymizerError('VISUAL_STATE_MISMATCH')
    v=visual_verification
    if (not isinstance(v,VisualVerification) or v.ok is not True or v.human_confirmed is not True
            or v.issues or v.residuals or v.session_id!=review.document.session_id
            or v.review_revision!=review.revision or v.text_sha256!=preview.sha256
            or v.visual_sha256!=expected.sha256 or v.detector_fingerprint!=verification.detector_fingerprint
            or v.detector_fingerprint=='unavailable'
            or v.ocr_sha256!=hashlib.sha256(v.ocr_text.encode('utf-8')).hexdigest()):
        raise AnonymizerError('VISUAL_VERIFICATION_REQUIRED')
    if Path(destination).absolute()==source.document.source_path:raise AnonymizerError('EXPORT_ORIGINAL')
    return _publish_bytes(_pdf_bytes(expected.pages),destination)
