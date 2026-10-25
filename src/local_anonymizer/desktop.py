"""Multi-format desktop orchestration; domain checks remain UI independent."""
from pathlib import Path
import sys
from threading import Event
from PySide6.QtCore import QThread, QUrl, Qt, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QListWidget, QTabWidget, QMessageBox

from .gui import MainWindow as TextWindow, ConfiguredDetector, guarded
from .batch import Batch, BatchEntry
from .domain import AnonymizerError, ResidualDecision
from .source import LoadedSource, SourceKind, MAX_RASTER_BYTES
from .session import Session
from .formats import load_source
from .layout import build_visual_preview, verify_visual, publish_layout
from .markdown_view import SafeMarkdownBrowser, resolve_resource
from .page_view import PageViewer
from .verification import verify_preview


class _TaskThread(QThread):
    """One operation, no worker event loop or queued quit handshake."""
    def __init__(self,operation,parent):
        super().__init__(parent);self.operation=operation;self.result=None;self.error=None

    def run(self):
        try:self.result=self.operation()
        except AnonymizerError as error:self.error=error.code
        except Exception:self.error='OPERATION_FAILED'
        finally:self.operation=None


class MainWindow(TextWindow):
    """Extend the tested text workflow with independent queued visual reviews."""
    def __init__(self, *, detector=None):
        self.batch=Batch();self.entry=None;self._entry_index=-1
        self._cancel_event=Event();self._snapshot=None;self._switching=False
        self._residual_rows=[]
        super().__init__(detector=detector)
        self.open_button.setText('Abrir documentos / lote')
        self.clear_button.setText('Cerrar lote')
        self.status.setText('TXT, Markdown, PDF, DOCX, PNG, JPEG y TIFF. Hasta 20 documentos / 200 MiB por lote.')
        layout=self.centralWidget().layout()
        self.batchlist=QListWidget();self.batchlist.setMaximumHeight(85)
        self.batchlist.setAccessibleName('Documentos del lote; revisión independiente')
        self.batchlist.currentRowChanged.connect(self.select_entry);layout.insertWidget(3,self.batchlist)
        self.input_tabs=QTabWidget();self.output_tabs=QTabWidget()
        for edit,tabs in ((self.source,self.input_tabs),(self.output,self.output_tabs)):
            parent=edit.parentWidget();box=parent.layout();box.removeWidget(edit)
            box.itemAt(0).widget().setText('Fuente local' if edit is self.source else 'Vista previa que se exportará')
            tabs.addTab(edit,'Texto');box.addWidget(tabs)
        self.markdown=SafeMarkdownBrowser(Path('.'));self.input_tabs.addTab(self.markdown,'Markdown')
        self.markdown.resourceRequested.connect(self.open_resource)
        self.markdown.linkBlocked.connect(lambda code:self.show_error(AnonymizerError(code)))
        self.visual_source=PageViewer(editable=True);self.input_tabs.addTab(self.visual_source,'Páginas originales')
        self.visual_output=PageViewer();self.output_tabs.addTab(self.visual_output,'Páginas de salida')
        self.visual_source.regionAdded.connect(self.add_region)
        self.regions_list=QListWidget();self.regions_list.setMaximumHeight(55)
        self.regions_list.setAccessibleName('Zonas manuales de redacción');layout.addWidget(self.regions_list)
        self.remove_region_button=self.button('Quitar zona manual seleccionada',self.remove_region,layout)
        self.batch_export_button=self.button('Exportar documentos verificados del lote',self.export_batch_dialog,layout)
        self.attestation.setText('He revisado todo el texto, todas las páginas de salida y el riesgo contextual.')
        self.update_controls()

    def _store_entry(self):
        if self.entry:
            self.entry.terms=self._terms;self.entry.report=self._saved_report

    def _is_visual(self):
        return bool(self.entry and self.entry.source and self.entry.source.pages)

    def can_publish(self,entry=None):
        e=entry or self.entry
        if not e or not e.session.can_export:return False
        if not e.source.pages:return True
        v=e.visual_verification;r=e.session.review;p=e.session.current_preview
        return bool(e.visual and v and v.ok and v.human_confirmed and not v.issues and not v.residuals
                    and v.session_id==r.document.session_id and v.review_revision==r.revision
                    and v.text_sha256==p.sha256 and v.visual_sha256==e.visual.sha256
                    and v.detector_fingerprint==e.session.verification.detector_fingerprint)

    def update_controls(self,*_):
        super().update_controls()
        if not hasattr(self,'batchlist'):return
        busy=self._thread is not None
        self.batchlist.setEnabled(not busy)
        self.export_button.setText('Guardar PDF con maquetación' if self._is_visual() else 'Guardar TXT nuevo')
        self.export_button.setEnabled(not busy and self.can_publish())
        self.batch_export_button.setEnabled(not busy and any(self.can_publish(e) for e in self.batch.entries))
        self.remove_region_button.setEnabled(self._is_visual() and not busy and bool(self.entry.regions))
        self.visual_source.editable=self._is_visual() and not busy
        self.batchlist.setVisible(len(self.batch.entries)>1)
        self.terms.setVisible(bool(self._terms));self.remove_term_button.setVisible(bool(self._terms))
        self.regions_list.setVisible(bool(self.entry and self.entry.regions))
        self.remove_region_button.setVisible(bool(self.entry and self.entry.regions))
        residual=bool(self._residual_rows and not busy)
        self.reject_button.setEnabled(residual);self.locate_button.setEnabled(residual)
        self.residual_table.setVisible(bool(self._residual_rows))
        self.reject_button.setVisible(bool(self._residual_rows));self.locate_button.setVisible(bool(self._residual_rows))
        total=len(self.session.review.findings) if self.session.review else 0
        self.table.setVisible(total>0);self.table.setMaximumHeight(180)
        self.previous_button.setVisible(total>self.PAGE_SIZE);self.next_button.setVisible(total>self.PAGE_SIZE)
        self.page_label.setVisible(total>0)
        for i,e in enumerate(self.batch.entries):
            item=self.batchlist.item(i)
            if item:
                status=('guardado' if e.receipt else 'verificado' if self.can_publish(e)
                        else 'error: '+e.error if e.error else 'revisión pendiente' if e.source else 'sin cargar')
                item.setText(f'{i+1}. {e.path.name} · {status}')

    def invalidate_display(self):
        self._residual_rows=[]
        if self.entry:
            self.entry.visual=None;self.entry.visual_verification=None;self.entry.visual_rejections=()
            self.entry.report=None
        if hasattr(self,'visual_output'):self.visual_output.set_pages(())
        super().invalidate_display()

    def attestation_changed(self,checked):
        if not checked and self.entry:
            self.entry.visual_verification=None;self.entry.visual_rejections=()
            self._residual_rows=[]
        super().attestation_changed(checked)

    @guarded
    def open_document(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Abrir documentos locales','',
            'Documentos (*.txt *.md *.markdown *.pdf *.docx *.png *.jpg *.jpeg *.tif *.tiff)')
        if paths:self.open_paths(tuple(Path(p) for p in paths))

    def open_paths(self,paths):
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        queue=Batch(paths)
        if not queue.entries:return
        self.batch=queue;self.entry=None;self.session=Session();self._entry_index=-1
        self._saved_report=None;self._terms=()
        self._switching=True;self.batchlist.clear()
        for e in queue.entries:self.batchlist.addItem(e.path.name)
        self._switching=False;self.select_entry(0)

    @guarded
    def select_entry(self,index):
        if self._switching or index<0 or index>=len(self.batch.entries):return
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        if index==self._entry_index:return
        self._store_entry();self.entry=self.batch.entries[index];self._entry_index=index
        self.session=self.entry.session;self._terms=self.entry.terms;self._saved_report=self.entry.report
        self._switching=True;self.batchlist.setCurrentRow(index);self._switching=False
        self._page=0;self._residual_rows=[]
        if self.entry.source:self._restore_entry()
        else:
            self.source.clear();self.output.clear();self.markdown.clear()
            self.visual_source.set_pages(());self.visual_output.set_pages(())
            self.regions_list.clear();self.terms.clear();self.term.clear()
            self.batch.validate_limits()
            self._cancel_event=Event();cancel=self._cancel_event.is_set;path=self.entry.path
            self._run_standalone('load',lambda:load_source(path,cancelled=cancel))
            self.status.setText('Cargando copia local y OCR cuando procede… La conversión DOCX requiere LibreOffice contenido.')

    def set_document(self,document):
        kind=SourceKind.MARKDOWN if document.source_path.suffix.lower() in ('.md','.markdown') else SourceKind.TEXT
        self.set_loaded_source(LoadedSource(document,kind))

    def set_loaded_source(self,source):
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        self.entry=BatchEntry(source.document.source_path);self.entry.attach(source)
        self.batch=Batch();self.batch.entries=[self.entry];self._entry_index=0;self.session=self.entry.session
        self._switching=True;self.batchlist.clear();self.batchlist.addItem(self.entry.path.name)
        self.batchlist.setCurrentRow(0);self._switching=False
        self._new_document();self._show_source()

    def _show_source(self):
        s=self.entry.source
        self.source.setPlainText(s.document.text)
        self.markdown.root=s.document.source_path.parent
        self.markdown.render_markdown(s.document.text if s.kind==SourceKind.MARKDOWN else '')
        self.input_tabs.setTabEnabled(1,s.kind==SourceKind.MARKDOWN)
        self.input_tabs.setTabEnabled(2,bool(s.pages))
        self.visual_source.set_pages(s.pages,self.entry.regions)
        self._render_regions()
        if s.pages:
            self.input_tabs.setCurrentIndex(2)
            self.status.setText('Revisa cada página: OCR puede omitir texto. Arrastra sobre el original para añadir zonas manuales. Partes no visibles, firmas y formularios no se conservan.')
        elif s.kind==SourceKind.MARKDOWN:self.input_tabs.setCurrentIndex(1)
        else:self.input_tabs.setCurrentIndex(0)

    def _restore_entry(self):
        self.terms.clear()
        for text,category in self._terms:self.terms.addItem(f'{category}: {text}')
        self.term.clear();self.render_review(invalidate=False);self._show_source()
        p=self.session.current_preview
        self.output.setPlainText(p.text if p else '')
        self.attestation.blockSignals(True);self.attestation.setChecked(bool(self.session.review.confirmed));self.attestation.blockSignals(False)
        self.visual_output.set_pages(self.entry.visual.pages if self.entry.visual else ())
        if self.entry.visual:self.output_tabs.setCurrentIndex(1)
        if self.session.verification:self.render_verification()
        self.update_controls()

    @guarded
    def clear_document(self):
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        for e in self.batch.entries:e.session.close()
        self.entry=None;self.batch=Batch();self._entry_index=-1
        self._switching=True;self.batchlist.clear();self._switching=False
        self.markdown.clear();self.visual_source.set_pages(());self.visual_output.set_pages(());self.regions_list.clear()
        super().clear_document()

    def _configured_detector(self,terms):
        if self._detector is None:
            from .ner import EnhancedDetector
            self._detector=EnhancedDetector(Path(sys.prefix)/'models/gliner-multi-v2.1')
        return ConfiguredDetector(self._detector,terms,cancelled=self._cancel_event.is_set)

    def _report_versions(self):
        versions=super()._report_versions();versions.pop('model',None)
        from .ner import EnhancedDetector
        if isinstance(self._detector,EnhancedDetector):versions['model']='2.1'
        return versions

    def _start_worker(self,kind,operation,*,verification=False):
        self._cancel_event=Event()
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        self._token=self.session.begin_job(verification=verification);self._kind=kind
        self._launch_thread(operation)

    def _launch_thread(self,operation):
        self._thread=_TaskThread(operation,self);self._worker=self._thread
        self._thread.finished.connect(self.work_finished)
        self._thread.start();self.update_controls()

    def _run_standalone(self,kind,operation):
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        self._kind=kind;self._token=None
        r=self.session.review;self._snapshot=(r.document.session_id,r.revision) if r else None
        self._launch_thread(operation)

    @Slot()
    @guarded
    def work_finished(self):
        worker,thread,kind,token=self._worker,self._thread,self._kind,self._token
        self._worker=self._thread=self._token=None;thread.deleteLater()
        cancelled=self._cancel_event.is_set()
        error=worker.error;result=worker.result;worker.result=None
        if kind=='batch_export' and not error:
            self._finish_batch_export(result)
            self._store_entry();self.update_controls()
            if self._closing:self.close()
            return
        if error or cancelled:
            valid=self.session.finish_job(token) if token else not cancelled
            if valid and error:
                if kind=='load':self.entry.error=error
                self.show_error(AnonymizerError(error))
            else:self.status.setText('Trabajo cancelado; resultados descartados.')
        elif kind=='load':
            self.batch.validate_limits(result,self.entry)
            retained=sum(len(p.png) for e in self.batch.entries if e.source for p in e.source.pages)
            if retained+sum(len(p.png) for p in result.pages)>MAX_RASTER_BYTES:
                self.entry.error='BATCH_RASTER_LIMIT';self.show_error(AnonymizerError('BATCH_RASTER_LIMIT'))
            else:
                self.entry.attach(result);self._new_document();self._show_source()
                if not self._closing:self.start_analysis()
        elif kind=='analysis':
            if self.session.accept_result(token,result):
                self._page=0;self.render_review()
                self.status.setText('Análisis completo. Decide cada candidato y revisa las omisiones en texto y páginas.')
        elif kind=='visual_preview':
            r=self.session.review
            if self._snapshot==(r.document.session_id,r.revision) and self.session.current_preview:
                self.entry.visual=result;self.entry.visual_verification=None
                self.visual_output.set_pages(result.pages);self.output_tabs.setCurrentIndex(1)
                self.status.setText('Revisa todas las páginas de salida antes de confirmar. Las zonas manuales y palabras seleccionadas están cubiertas.')
        elif kind=='visual_verification':
            text_result,visual_result=result
            if self.session.accept_verification(token,text_result):
                self.entry.visual_verification=visual_result;self.render_verification()
        else:
            if self.session.accept_verification(token,result):self.render_verification()
        self._store_entry();self.update_controls()
        if self._closing:self.close()

    @guarded
    def cancel_work(self):
        self._cancel_event.set()
        if self._kind=='batch_export':
            self.status.setText('Cancelando las siguientes copias. La publicación empezada y las copias correctas se conservan.')
            return
        super().cancel_work()

    @guarded
    def make_preview(self):
        super().make_preview()
        if self._is_visual() and self.session.current_preview:
            self._cancel_event=Event();s=self.entry.source;r=self.session.review;p=self.session.current_preview;regions=self.entry.regions
            self._run_standalone('visual_preview',lambda:build_visual_preview(s,r,p,regions))

    @guarded
    def confirm_review(self):
        if self._is_visual():
            if not self.entry.visual or self.visual_output.visited!=set(range(len(self.entry.visual.pages))):
                raise AnonymizerError('VISUAL_PAGES_REVIEW_REQUIRED')
        super().confirm_review()

    def start_verification(self):
        if not self._is_visual():return super().start_verification()
        e=self.entry;r=self.session.review;p=self.session.current_preview;rejections=self.session.rejections
        terms=self._terms;visual=e.visual;regions=e.regions;visual_rejections=e.visual_rejections
        def operation():
            detector=self._configured_detector(terms)
            text=verify_preview(r,p,detector,rejections)
            visual_result=verify_visual(e.source,r,p,visual,detector,regions=regions,human_confirmed=True,
                                        rejections=visual_rejections,cancelled=self._cancel_event.is_set)
            return text,visual_result
        self._start_worker('visual_verification',operation,verification=True)
        self.status.setText('Verificando texto y segunda OCR de los píxeles de salida…')

    def _render_regions(self):
        self.regions_list.clear()
        if self.entry:
            for i,r in enumerate(self.entry.regions):self.regions_list.addItem(f'Zona {i+1} · Página {r.page+1}')

    @guarded
    def add_region(self,region):
        if self._thread is not None or not self._is_visual():raise AnonymizerError('JOB_ACTIVE')
        if region.page>=len(self.entry.source.pages):raise AnonymizerError('INVALID_VISUAL_REGION')
        self.entry.invalidate_visual();self.entry.regions+= (region,)
        self.visual_source.regions=self.entry.regions;self.visual_source.image.update()
        self.invalidate_display();self._render_regions();self.status.setText('Zona añadida. Reconstruye la vista previa y revisa de nuevo.')

    @guarded
    def remove_region(self):
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        row=self.regions_list.currentRow()
        if row<0:raise AnonymizerError('SELECT_VISUAL_REGION')
        self.entry.invalidate_visual();self.entry.regions=self.entry.regions[:row]+self.entry.regions[row+1:]
        self.visual_source.regions=self.entry.regions;self.visual_source.image.update()
        self.invalidate_display();self._render_regions()

    def render_verification(self):
        if not self._is_visual():
            super().render_verification()
            self._residual_rows=[('text',c) for c in self.session.verification.residuals]
            self.update_controls();return
        from PySide6.QtWidgets import QTableWidgetItem
        text=self.session.verification;visual=self.entry.visual_verification
        self._residual_rows=[('text',c) for c in text.residuals]+[('visual',c) for c in (visual.residuals if visual else ())]
        self.residual_table.setRowCount(len(self._residual_rows))
        for row,(kind,candidate) in enumerate(self._residual_rows):
            f=candidate.finding;value=(self.session.current_preview.text if kind=='text' else visual.ocr_text)[f.start:f.end]
            for col,value in enumerate((value,f.category.value,kind+': '+', '.join(f.provenance))):
                item=QTableWidgetItem(value);item.setFlags(item.flags() & ~Qt.ItemIsEditable);self.residual_table.setItem(row,col,item)
        if self.can_publish():self.status.setText('Texto y píxeles verificados para esta revisión. Puedes guardar un PDF nuevo. La detección y OCR pueden omitir información.')
        else:
            issues=text.issues+(visual.issues if visual else ('VISUAL_VERIFICATION_REQUIRED',))
            self.status.setText('Exportación bloqueada. Revisa los residuales o corrige las zonas: '+', '.join(dict.fromkeys(issues)))
        self.update_controls()

    @guarded
    def reject_residuals(self):
        if not self._is_visual():return super().reject_residuals()
        rows={i.row() for i in self.residual_table.selectionModel().selectedRows()}
        if not rows:raise AnonymizerError('SELECT_RESIDUAL')
        chosen=[self._residual_rows[i] for i in sorted(rows)]
        text=tuple(c.key for kind,c in chosen if kind=='text')
        if text:self.session.reject_residuals(text)
        self.entry.visual_rejections+=tuple(ResidualDecision(c.key) for kind,c in chosen if kind=='visual')
        self.entry.visual_verification=None;self.start_verification()

    @guarded
    def locate_residual(self):
        row=self.residual_table.currentRow()
        if row<0:raise AnonymizerError('SELECT_RESIDUAL')
        kind,c=self._residual_rows[row]
        if kind=='text':return super().locate_residual()
        matches=[b for b in self.entry.visual_verification.boxes if b.start<c.finding.end and b.end>c.finding.start]
        if not matches:raise AnonymizerError('VISUAL_LOCATION_UNAVAILABLE')
        self.input_tabs.setCurrentIndex(2);self.visual_source.show_page(matches[0].page)
        self.status.setText('Residual de OCR en página '+str(matches[0].page+1)+'. Compara la salida y añade una zona en el original si contiene datos sensibles.')

    @guarded
    def open_resource(self,target):
        box=QMessageBox(self);box.setTextFormat(Qt.PlainText);box.setWindowTitle('Abrir recurso enlazado')
        box.setText('Se abrirá con la aplicación asociada. Los enlaces web usarán tu navegador y conexión.\n\n'+target.destination)
        box.setStandardButtons(QMessageBox.Open|QMessageBox.Cancel);box.setDefaultButton(QMessageBox.Cancel)
        if box.exec()!=QMessageBox.Open:return
        href=target.destination
        checked=resolve_resource(href if target.kind=='web' else str(Path(href).relative_to(self.markdown.root.resolve())),self.markdown.root)
        url=QUrl.fromLocalFile(checked.destination) if checked.kind=='local' else QUrl(checked.destination)
        if not QDesktopServices.openUrl(url):raise AnonymizerError('LINK_OPEN_FAILED')

    @guarded
    def export_dialog(self):
        if not self.can_publish():raise AnonymizerError('VERIFICATION_REQUIRED')
        suffix='PDF (*.pdf)' if self._is_visual() else 'Texto (*.txt)'
        path,_=QFileDialog.getSaveFileName(self,'Guardar copia nueva','',suffix,options=QFileDialog.DontConfirmOverwrite)
        if path:self.export_to(Path(path))

    def export_to(self,path):
        if not self.can_publish():raise AnonymizerError('VERIFICATION_REQUIRED')
        if not self._is_visual():
            result=super().export_to(path);self.entry.report=self._saved_report
        else:
            e=self.entry;s=self.session
            result=publish_layout(e.source,s.review,s.current_preview,s.verification,e.visual,path,e.regions,
                                  visual_verification=e.visual_verification)
            self._saved_report=None;self.entry.report=None
            self.status.setText('PDF nuevo guardado y reabierto: imágenes verificadas, sin capas originales. No se certifica anonimato.')
        self.entry.receipt=result;self.update_controls();return result

    @guarded
    def export_batch_dialog(self):
        path=QFileDialog.getExistingDirectory(self,'Carpeta para copias nuevas verificadas')
        if path:self.start_batch_export(Path(path))

    def start_batch_export(self,directory):
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        entries=tuple(self.batch.entries)
        ready=tuple(self.can_publish(e) for e in entries)
        self._cancel_event=Event();cancelled=self._cancel_event.is_set
        self._run_standalone('batch_export',lambda:self._publish_batch(entries,ready,directory,cancelled))
        self.status.setText('Publicando copias verificadas. Cancelar detiene las siguientes; las copias ya guardadas se conservan.')

    def export_batch(self,directory):
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        entries=tuple(self.batch.entries);ready=tuple(self.can_publish(e) for e in entries)
        return self._finish_batch_export(self._publish_batch(entries,ready,directory,lambda:False))

    @staticmethod
    def _publish_batch(entries,ready,directory,cancelled):
        from .export import publish_text
        results=[];skipped=0
        for index,(e,verified) in enumerate(zip(entries,ready)):
            if not verified or cancelled():skipped+=1;continue
            visual=bool(e.source.pages);dest=directory/f'documento-{index+1:03d}.{ "pdf" if visual else "txt" }'
            s=e.session
            try:
                receipt=(publish_layout(e.source,s.review,s.current_preview,s.verification,e.visual,dest,e.regions,
                           visual_verification=e.visual_verification) if visual else
                           publish_text(s.review,s.current_preview,s.verification,dest))
                results.append((index,receipt,None))
            except AnonymizerError as error:
                results.append((index,None,error))
            except Exception:
                results.append((index,None,AnonymizerError('EXPORT_FAILED')))
        return tuple(results),skipped

    def _finish_batch_export(self,result):
        results,skipped=result;saved=failed=0
        for index,receipt,error in results:
            if error:failed+=1;self.show_error(error)
            else:saved+=1;self.batch.entries[index].receipt=receipt
        self.status.setText(f'Lote: {saved} copias guardadas; {skipped} pendientes omitidos; {failed} errores. Las copias correctas se conservan.')
        self.update_controls();return saved,skipped,failed

    def closeEvent(self,event):
        if self._thread is None:
            for e in self.batch.entries:e.session.close()
            self.batch=Batch();self.entry=None
        super().closeEvent(event)
