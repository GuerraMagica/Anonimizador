"""Crash isolation for native PDF/OCR called from background threads.

Fresh spawn children own all their PyMuPDF objects on their main thread. IPC
contains only application bytes/dataclasses. This is process isolation for native
stability, not a security sandbox. Office conversion stays in the caller so its
cooperative process-group cleanup cannot be interrupted by this supervisor.
"""
import multiprocessing
import threading
import time

from .domain import AnonymizerError

NATIVE_TIMEOUT=600
CANCEL_GRACE=60


def background_thread():
    return threading.current_thread() is not threading.main_thread()


def _child_entry(send,target,args,event):
    try:
        value=target(*args,cancelled=event.is_set)
        send.send(('result',value))
    except AnonymizerError as error:
        send.send(('error',error.code))
    except Exception:
        send.send(('error','NATIVE_PROCESS_FAILED'))
    finally:
        send.close()


def _stop(process):
    if process.is_alive():
        process.terminate();process.join(2)
    if process.is_alive():
        process.kill();process.join(2)


def _run_native_call(target,args=(),*,cancelled=lambda:False,timeout=NATIVE_TIMEOUT,cancel_grace=CANCEL_GRACE):
    """Supervise one trusted application function; never fork a running Qt host.

    Cancellation first signals the child and discards any late result. A native
    call that never returns is terminated after the grace period. These children
    never own LibreOffice conversions or publications and never write originals.
    """
    if cancelled():raise AnonymizerError('CANCELLED')
    context=multiprocessing.get_context('spawn')
    receive,send=context.Pipe(duplex=False)
    event=context.Event();process=context.Process(target=_child_entry,args=(send,target,tuple(args),event),daemon=True)
    started=False;message=None;cancel_started=None
    try:
        try:
            process.start();started=True;send.close()
        except (OSError,RuntimeError,ValueError):
            raise AnonymizerError('NATIVE_PROCESS_FAILED') from None
        begin=time.monotonic()
        while True:
            now=time.monotonic()
            if cancelled():
                event.set()
                if cancel_started is None:cancel_started=now
            if cancel_started is not None and now-cancel_started>=cancel_grace:
                raise AnonymizerError('CANCELLED')
            if now-begin>=timeout:
                event.set();raise AnonymizerError('CANCELLED' if cancel_started is not None else 'NATIVE_TIMEOUT')
            if receive.poll(.05):
                try:message=receive.recv()
                except (EOFError,OSError):raise AnonymizerError('NATIVE_PROCESS_FAILED') from None
                break
            if not process.is_alive():
                raise AnonymizerError('CANCELLED' if cancel_started is not None else 'NATIVE_PROCESS_FAILED')
        process.join(2)
        if cancel_started is not None or cancelled():raise AnonymizerError('CANCELLED')
        if process.is_alive() or process.exitcode!=0:
            raise AnonymizerError('NATIVE_PROCESS_FAILED')
        if not isinstance(message,tuple) or len(message)!=2 or message[0] not in ('result','error'):
            raise AnonymizerError('NATIVE_PROCESS_FAILED')
        if message[0]=='error':raise AnonymizerError(message[1])
        return message[1]
    finally:
        if started:_stop(process)
        receive.close();send.close()
        if started:process.close()


def _dispatch(operation,args,*,cancelled):
    # Fixed production entrypoints; no caller-supplied module/function names.
    from . import formats
    if operation=='load_source':
        if args[0].suffix.lower()=='.docx':raise AnonymizerError('NATIVE_OPERATION_INVALID')
        return formats.load_source(*args,cancelled=cancelled)
    if operation=='pdf_details':
        pages,notes=formats._raster_pdf(*args,cancelled=cancelled)
        text,boxes=formats._ocr_pages(pages,cancelled=cancelled)
        return text,pages,boxes,notes
    if operation=='ocr_pdf':return formats.ocr_pdf(*args,cancelled=cancelled)
    if operation=='ocr_raster_details':return formats.ocr_raster_details(*args,cancelled=cancelled)
    if operation=='pdf_bytes':
        from .layout import _pdf_bytes
        if cancelled():raise AnonymizerError('CANCELLED')
        return _pdf_bytes(*args)
    raise AnonymizerError('NATIVE_OPERATION_INVALID')


def run_native(operation,args=(),*,cancelled=lambda:False):
    return _run_native_call(_dispatch,(operation,tuple(args)),cancelled=cancelled)
