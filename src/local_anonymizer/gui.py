"""Desktop review workflow. Source values only enter plain-text widgets."""
from collections import Counter
from dataclasses import replace
from functools import wraps
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import platform
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from . import __version__
from .detectors import LocalDetector, default_model_path, literal_findings
from .domain import (Action, AnonymizerError, Category, Confidentiality, Decision,
                     Disposition, Document, FileIdentity, Finding)
from .export import publish_text
from .report import build_report, save_report
from .session import Session
from .transform import map_output_span
from .verification import verify_preview


def python_to_qt(text, position):
    if not 0 <= position <= len(text):raise AnonymizerError('INVALID_SELECTION')
    if 0 < position < len(text) and text[position-1:position+1] == '\r\n':
        raise AnonymizerError('INVALID_SELECTION')
    return len(text[:position].replace('\r\n','\n').encode('utf-16-le')) // 2


def qt_to_python(text, position):
    if position < 0:raise AnonymizerError('INVALID_SELECTION')
    index = offset = 0
    while index < len(text):
        if offset == position:return index
        width = 2 if ord(text[index]) > 0xffff else 1
        if offset < position < offset + width:raise AnonymizerError('INVALID_SELECTION')
        offset += width
        index += 2 if text[index:index+2] == '\r\n' else 1
    if offset == position:return index
    raise AnonymizerError('INVALID_SELECTION')


class ConfiguredDetector:
    """Bind session vocabulary to both initial and residual analysis."""
    def __init__(self, base, terms):
        self.base, self.terms = base, tuple(terms)
        config = json.dumps(self.terms,ensure_ascii=False).encode()
        self.fingerprint = 'session:' + sha256(base.fingerprint.encode()+config).hexdigest()

    def analyze(self, text, session_id):
        document = Document(session_id,0,Path('.'),FileIdentity(0,0),text,'')
        return self.base.analyze(text,session_id) + literal_findings(document,self.terms)


class _Worker(QObject):
    finished = Signal()
    def __init__(self, operation):
        super().__init__();self.operation=operation;self.result=None;self.error=None
    @Slot()
    def run(self):
        try:self.result=self.operation()
        except AnonymizerError as error:self.error=error.code
        except Exception:self.error='ANALYSIS_FAILED'
        finally:
            self.operation=None
            self.finished.emit()


def guarded(method):
    @wraps(method)
    def invoke(self,*args,**kwargs):
        try:return method(self,*args,**kwargs)
        except AnonymizerError as error:self.show_error(error)
        except Exception:self.show_error(AnonymizerError('OPERATION_FAILED'))
    return invoke


def plain_label(text):
    label=QLabel(text);label.setTextFormat(Qt.PlainText);label.setWordWrap(True)
    return label


class MainWindow(QMainWindow):
    def __init__(self, *, detector=None):
        super().__init__()
        self.setWindowTitle('Anonimizador local — versión de desarrollo')
        self.resize(1260,900)
        self.session=Session();self._detector=detector;self._terms=()
        self._thread=None;self._worker=None;self._token=None;self._kind=None
        self._rendering=False;self._closing=False;self._saved_report=None
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root)
        layout.addWidget(plain_label('Revisa toda la fuente y el riesgo contextual. La detección puede omitir información; ninguna comprobación certifica anonimato.'))
        controls=QHBoxLayout();layout.addLayout(controls)
        self.open_button=self.button('Abrir TXT / Markdown',self.open_document,controls)
        self.analyze_button=self.button('Analizar de nuevo',self.start_analysis,controls)
        self.cancel_button=self.button('Cancelar trabajo',self.cancel_work,controls)
        self.clear_button=self.button('Cerrar documento',self.clear_document,controls)
        self.status=plain_label('Abre un archivo UTF-8. Máximo 1 MiB y 100 000 caracteres.');layout.addWidget(self.status)
        splitter=QSplitter(Qt.Horizontal);layout.addWidget(splitter,3)
        self.source=QPlainTextEdit();self.source.setReadOnly(True);self.source.setAccessibleName('Fuente original')
        self.output=QPlainTextEdit();self.output.setReadOnly(True);self.output.setAccessibleName('Vista previa del TXT')
        for title,edit in (('Fuente original (texto plano)',self.source),('Vista previa (texto plano)',self.output)):
            panel=QWidget();box=QVBoxLayout(panel);box.addWidget(plain_label(title));box.addWidget(edit);splitter.addWidget(panel)
        manual=QHBoxLayout();layout.addLayout(manual)
        self.category=QComboBox();self.category.addItems([c.value for c in Category]);self.category.setCurrentText(Category.CONFIDENCIAL)
        self.category.setAccessibleName('Categoría de selección o término');manual.addWidget(self.category)
        self.add_button=self.button('Añadir selección del original',self.add_selection,manual)
        self.correct_button=self.button('Corregir fragmento de fila seleccionada',self.correct_selection,manual)
        self.term=QLineEdit();self.term.setPlaceholderText('Término literal de esta sesión');self.term.setAccessibleName('Término literal');manual.addWidget(self.term)
        self.term_button=self.button('Añadir término y reanalizar',self.add_term,manual)
        self.terms=QListWidget();self.terms.setMaximumHeight(55);self.terms.setAccessibleName('Vocabulario de sesión');layout.addWidget(self.terms)
        self.remove_term_button=self.button('Quitar término seleccionado y reanalizar',self.remove_term,layout)
        layout.addWidget(plain_label('Decide cada candidato. Corrige categoría o fragmento si procede. Un mismo grupo explícito comparte etiqueta dentro de su categoría; dejar vacío agrupa valores idénticos. Reanalizar reinicia las decisiones.'))
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['Fragmento original','Categoría','Detector / regla','Puntuación','Decisión','Acción','Grupo (opcional)'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self.rows_changed);self.table.itemSelectionChanged.connect(self.locate_finding)
        layout.addWidget(self.table,2)
        actions=QHBoxLayout();layout.addLayout(actions)
        self.preview_button=self.button('Construir vista previa',self.make_preview,actions)
        self.attestation=QCheckBox('He revisado todo el texto, las sustituciones y el riesgo contextual.');actions.addWidget(self.attestation)
        self.attestation.toggled.connect(self.attestation_changed)
        self.confirm_button=self.button('Confirmar revisión y verificar',self.confirm_review,actions)
        self.residual_table=QTableWidget(0,3);self.residual_table.setHorizontalHeaderLabels(['Candidato residual en salida','Categoría','Procedencia'])
        self.residual_table.setSelectionBehavior(QTableWidget.SelectRows);self.residual_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.residual_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.residual_table.setMaximumHeight(130);layout.addWidget(self.residual_table)
        residual_actions=QHBoxLayout();layout.addLayout(residual_actions)
        self.locate_button=self.button('Localizar residual en original',self.locate_residual,residual_actions)
        self.reject_button=self.button('Rechazar residuales seleccionados como falsos positivos y verificar',self.reject_residuals,residual_actions)
        self.export_button=self.button('Guardar TXT nuevo',self.export_dialog,residual_actions)
        self.report_button=self.button('Guardar informe técnico opcional',self.report_dialog,residual_actions)
        self.update_controls()

    def button(self,text,callback,container):
        b=QPushButton(text);b.clicked.connect(lambda _checked=False: callback());container.addWidget(b);return b

    def show_error(self,error):
        messages={
            'REVIEW_PENDING':'Decide todos los candidatos antes de previsualizar.',
            'REVIEW_CONFLICT':'Hay candidatos aceptados que se solapan. Corrige el fragmento o rechaza el duplicado conflictivo.',
            'MODEL_UNAVAILABLE':'No se pudo cargar el modelo local autorizado. Revisa la instalación.',
            'ANALYSIS_FAILED':'No se completó el análisis. La exportación permanece bloqueada.',
            'EXPORT_EXISTS':'El destino ya existe. Elige un archivo nuevo.',
            'SELECTED_VALUE_REMAINS':'Un valor seleccionado persiste en la salida. Cambia la revisión del original o la acción; este bloqueo no se puede rechazar.',
        }
        self.status.setText(messages.get(error.code,'Operación no completada.')+' Código: '+error.code)
        if error.cleanup_paths:
            box=QMessageBox(self);box.setTextFormat(Qt.PlainText);box.setWindowTitle('Archivo pendiente de inspección')
            box.setText('La operación falló y puede quedar una copia parcial sin verificar. Inspecciona la ubicación elegida; el archivo o su directorio podrían haber sido sustituidos o movidos. No se ha borrado nada automáticamente:\n'+'\n'.join(map(str,error.cleanup_paths)))
            box.exec()
        self.update_controls()

    def update_controls(self,*_):
        busy=self._thread is not None
        loaded=self.session.review is not None
        complete=loaded and self.session.review.coverage_complete
        self.open_button.setEnabled(not busy);self.clear_button.setEnabled(loaded and not busy)
        self.analyze_button.setEnabled(loaded and not busy)
        for widget in (self.add_button,self.correct_button,self.term_button,self.remove_term_button,self.term,self.category,self.terms,self.table):
            widget.setEnabled(loaded and not busy)
        self.cancel_button.setEnabled(busy and not self.session.cancel_pending)
        self.preview_button.setEnabled(bool(complete and not busy))
        self.attestation.setEnabled(bool(self.session.current_preview and not busy))
        self.confirm_button.setEnabled(bool(self.session.current_preview and self.attestation.isChecked() and not busy))
        residual=bool(self.session.verification and self.session.verification.residuals and not busy)
        self.reject_button.setEnabled(residual);self.locate_button.setEnabled(residual)
        self.export_button.setEnabled(self.session.can_export and not busy)
        self.report_button.setEnabled(self._saved_report is not None and not busy)

    def invalidate_display(self):
        self.output.clear();self.attestation.setChecked(False);self.residual_table.setRowCount(0)
        self._saved_report=None;self.update_controls()

    def attestation_changed(self, checked):
        if not checked and self.session.review and self.session.review.confirmed:
            self.session.withdraw_confirmation()
            self.residual_table.setRowCount(0)
        self.update_controls()

    @guarded
    def open_document(self):
        path,_=QFileDialog.getOpenFileName(self,'Abrir texto UTF-8','','Texto (*.txt *.md *.markdown)')
        if path:
            self.session.load(Path(path));self._new_document();self.start_analysis()

    def set_document(self,document):
        self.session.load(document);self._new_document()

    def _new_document(self):
        self._terms=();self.terms.clear();self.term.clear()
        self.source.setPlainText(self.session.review.document.text)
        self.render_review();self.status.setText('Fuente textual cargada. Pendiente de análisis y revisión.')

    @guarded
    def clear_document(self):
        self.session.close();self._terms=();self.terms.clear();self.term.clear()
        self.source.clear();self.table.setRowCount(0);self.invalidate_display()
        self.status.setText('Documento cerrado; estado de sesión descartado. No se garantiza borrado físico de memoria.')

    def _configured_detector(self,terms):
        if self._detector is None:self._detector=LocalDetector(default_model_path())
        return ConfiguredDetector(self._detector,terms)

    def _start_worker(self,kind,operation,*,verification=False):
        if self._thread is not None:raise AnonymizerError('JOB_ACTIVE')
        self._token=self.session.begin_job(verification=verification);self._kind=kind
        self._thread=QThread(self);self._worker=_Worker(operation);self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self.work_finished)
        self._thread.start();self.update_controls()

    @guarded
    def start_analysis(self):
        if self.session.review is None:return
        doc=self.session.review.document;terms=self._terms
        self._start_worker('analysis',lambda:self._configured_detector(terms).analyze(doc.text,doc.session_id))
        self.invalidate_display();self.status.setText('Analizando toda la fuente textual localmente…')

    @Slot()
    @guarded
    def work_finished(self):
        worker,thread=self._worker,self._thread
        self._worker=None;self._thread=None
        thread.deleteLater()
        if worker.error:
            valid=self.session.finish_job(self._token)
            if valid:self.show_error(AnonymizerError(worker.error))
            else:self.status.setText('Trabajo cancelado; resultados descartados.')
        elif self._kind=='analysis':
            if self.session.accept_result(self._token,worker.result):
                self.render_review();self.status.setText('Análisis completo. Revisa toda la fuente y decide cada candidato; añade los datos omitidos.')
            else:self.status.setText('Trabajo cancelado; resultados descartados.')
        else:
            if self.session.accept_verification(self._token,worker.result):self.render_verification()
            else:self.status.setText('Verificación cancelada; exportación bloqueada.')
        worker.result=None;self._token=None;self.update_controls()
        if self._closing:self.close()

    @guarded
    def cancel_work(self):
        self.session.cancel();self.invalidate_display()
        self.status.setText('Cancelación pendiente: esperando a que termine la llamada local. No se aplicarán sus resultados.')
        self.update_controls()

    def render_review(self):
        self._rendering=True
        try:
            r=self.session.review;self.table.setRowCount(len(r.findings) if r else 0)
            if r:
                decisions={d.finding_id:d for d in r.decisions}
                for row,f in enumerate(r.findings):
                    for col,text in ((0,r.document.text[f.start:f.end]),(2,', '.join(f.provenance)),(3,'' if f.score is None else f'{f.score:.2f}')):
                        item=QTableWidgetItem(text);item.setFlags(item.flags() & ~Qt.ItemIsEditable);self.table.setItem(row,col,item)
                    for col,values,current in (
                        (1,[c.value for c in Category],f.category.value),
                        (4,['Pendiente','Sustituir','Conservar'],['Pendiente','Sustituir','Conservar'][list(Disposition).index(decisions[f.id].disposition)]),
                        (5,['Etiqueta','Redactar'],'Etiqueta' if decisions[f.id].action==Action.LABEL else 'Redactar')):
                        combo=QComboBox();combo.addItems(values);combo.setCurrentText(current)
                        combo.currentIndexChanged.connect(self.rows_changed);self.table.setCellWidget(row,col,combo)
                    self.table.setItem(row,6,QTableWidgetItem(decisions[f.id].group_id or f.group_id or ''))
        finally:self._rendering=False
        self.invalidate_display()

    @guarded
    def rows_changed(self,*_):
        if self._rendering or self.session.review is None:return
        findings=[];decisions=[]
        for row,f in enumerate(self.session.review.findings):
            category=Category(self.table.cellWidget(row,1).currentText())
            group=self.table.item(row,6).text().strip() or None
            findings.append(replace(f,category=category))
            decisions.append(Decision(f.id,list(Disposition)[self.table.cellWidget(row,4).currentIndex()],
                                      [Action.LABEL,Action.REDACT][self.table.cellWidget(row,5).currentIndex()],group))
        complete=self.session.review.coverage_complete
        self.session.set_findings(tuple(findings),coverage_complete=complete)
        self.session.set_decisions(tuple(decisions));self.invalidate_display()
        self.status.setText('Revisión modificada. Reconstruye la vista previa y confirma de nuevo.')

    def _source_span(self):
        if self.session.review is None:raise AnonymizerError('NO_DOCUMENT')
        cursor=self.source.textCursor();text=self.session.review.document.text
        start,end=(qt_to_python(text,p) for p in (cursor.selectionStart(),cursor.selectionEnd()))
        if start==end:raise AnonymizerError('SELECT_SOURCE_TEXT')
        return start,end

    @guarded
    def add_selection(self):
        start,end=self._source_span();r=self.session.review
        f=Finding(uuid4().hex,r.document.session_id,start,end,Category(self.category.currentText()),
                  Confidentiality.CUSTOM,('manual:v1',))
        self.session.set_findings(r.findings+(f,),coverage_complete=r.coverage_complete)
        self.session.set_decisions(r.decisions+(Decision(f.id,Disposition.PENDING),))
        self.render_review()

    @guarded
    def correct_selection(self):
        row=self.table.currentRow()
        if row<0:raise AnonymizerError('SELECT_FINDING')
        start,end=self._source_span();r=self.session.review
        findings=list(r.findings);findings[row]=replace(findings[row],start=start,end=end,provenance=('manual:corrected:v1',))
        self.session.set_findings(tuple(findings),coverage_complete=r.coverage_complete)
        self.session.set_decisions(r.decisions);self.render_review()

    @guarded
    def locate_finding(self):
        if self._rendering or self.session.review is None:return
        row=self.table.currentRow()
        if row>=0:
            f=self.session.review.findings[row];self.select_original(f.start,f.end)

    def select_original(self,start,end):
        text=self.session.review.document.text;cursor=self.source.textCursor()
        cursor.setPosition(python_to_qt(text,start));cursor.setPosition(python_to_qt(text,end),QTextCursor.KeepAnchor)
        self.source.setTextCursor(cursor);self.source.ensureCursorVisible()

    @guarded
    def add_term(self):
        term=(self.term.text(),Category(self.category.currentText()))
        literal_findings(self.session.review.document,(term,))
        if term not in self._terms:
            self._terms+=(term,);self.terms.addItem(f'{term[1]}: {term[0]}')
        self.term.clear();self.start_analysis()

    @guarded
    def remove_term(self):
        row=self.terms.currentRow()
        if row<0:raise AnonymizerError('SELECT_TERM')
        self._terms=self._terms[:row]+self._terms[row+1:];self.terms.takeItem(row);self.start_analysis()

    @guarded
    def make_preview(self):
        preview=self.session.preview();self.output.setPlainText(preview.text)
        self.attestation.setChecked(False);self.residual_table.setRowCount(0)
        self.status.setText('Vista previa construida. Comprueba las sustituciones y cualquier redacción sin marcador antes de confirmar.')
        self.update_controls()

    @guarded
    def confirm_review(self):
        if not self.attestation.isChecked():raise AnonymizerError('HUMAN_REVIEW_REQUIRED')
        self.session.confirm();self.start_verification()

    def start_verification(self):
        review,preview,rejections=self.session.review,self.session.current_preview,self.session.rejections
        terms=self._terms
        self._start_worker('verification',lambda:verify_preview(review,preview,self._configured_detector(terms),rejections),verification=True)
        self.status.setText('Comprobando valores seleccionados y candidatos residuales en toda la salida…')

    def render_verification(self):
        v=self.session.verification;p=self.session.current_preview
        self.residual_table.setRowCount(len(v.residuals))
        for row,candidate in enumerate(v.residuals):
            f=candidate.finding
            for col,text in enumerate((p.text[f.start:f.end],f.category.value,', '.join(f.provenance))):
                item=QTableWidgetItem(text);item.setFlags(item.flags() & ~Qt.ItemIsEditable);self.residual_table.setItem(row,col,item)
        if v.ok:self.status.setText('Comprobaciones técnicas superadas para esta revisión. Puedes guardar un TXT nuevo. La detección puede omitir información y el riesgo contextual permanece.')
        elif 'SELECTED_VALUE_REMAINS' in v.issues:self.show_error(AnonymizerError('SELECTED_VALUE_REMAINS'))
        elif v.residuals:self.status.setText('Exportación bloqueada: revisa los candidatos residuales. Corrige el original o rechaza explícitamente los falsos positivos de esta salida.')
        else:self.show_error(AnonymizerError(v.issues[0] if v.issues else 'VERIFICATION_FAILED'))
        self.update_controls()

    @guarded
    def reject_residuals(self):
        rows={i.row() for i in self.residual_table.selectionModel().selectedRows()}
        if not rows:raise AnonymizerError('SELECT_RESIDUAL')
        self.session.reject_residuals(tuple(self.session.verification.residuals[row].key for row in sorted(rows)))
        self.start_verification()

    @guarded
    def locate_residual(self):
        row=self.residual_table.currentRow()
        if row<0:raise AnonymizerError('SELECT_RESIDUAL')
        f=self.session.verification.residuals[row].finding
        segments=map_output_span(self.session.current_preview,f.start,f.end)
        self.select_original(min(s.source_start for s in segments),max(s.source_end for s in segments))
        self.status.setText('Se ha seleccionado la procedencia en el original. Puede incluir texto sustituido o varios segmentos; ajusta la selección y corrige o añade el hallazgo.')

    @guarded
    def export_dialog(self):
        if not self.session.can_export:raise AnonymizerError('VERIFICATION_REQUIRED')
        path,_=QFileDialog.getSaveFileName(self,'Guardar TXT nuevo','','Texto (*.txt)',options=QFileDialog.DontConfirmOverwrite)
        if path:self.export_to(Path(path))

    def export_to(self,path):
        if not self.session.can_export:raise AnonymizerError('VERIFICATION_REQUIRED')
        receipt=publish_text(self.session.review,self.session.current_preview,self.session.verification,path)
        self._saved_report=None
        try:
            counts=Counter(f.category.value for f in self.session.review.findings)
            counts.update(d.disposition.value for d in self.session.review.decisions)
            versions={'application':__version__.split('.dev')[0],'python':platform.python_version(),
                      'model':'3.8.0','spacy':metadata.version('spacy'),
                      'presidio_analyzer':metadata.version('presidio-analyzer'),
                      'pyside6':metadata.version('PySide6-Essentials')}
            self._saved_report=build_report(receipt,dict(counts),versions)
        except Exception:
            self.status.setText('TXT verificado; informe no preparado. La copia TXT se ha conservado.')
        else:
            self.status.setText('TXT nuevo guardado y comprobado. Informe opcional pendiente de una acción separada. No se certifica anonimato.')
        self.update_controls();return receipt

    @guarded
    def report_dialog(self):
        if self._saved_report is None:raise AnonymizerError('EXPORT_REQUIRED')
        path,_=QFileDialog.getSaveFileName(self,'Guardar informe técnico opcional','','JSON (*.json)',options=QFileDialog.DontConfirmOverwrite)
        if path:
            try:save_report(self._saved_report,Path(path))
            except AnonymizerError as error:
                self.show_error(error);self.status.setText('TXT verificado; informe no guardado. Código: '+error.code);return
            self.status.setText('Informe técnico guardado por separado. No incluye rutas, texto ni correspondencias originales.')

    def closeEvent(self,event):
        if self._thread is not None:
            self._closing=True;self.cancel_work();self.status.setText('Cierre pendiente: esperando al trabajo local para cerrar sin interrumpir el hilo.');event.ignore()
        else:
            self.session.close();self._terms=();self._saved_report=None;self._detector=None
            self.source.clear();self.output.clear();self.table.setRowCount(0);self.residual_table.setRowCount(0)
            self.terms.clear();self.term.clear();event.accept()
