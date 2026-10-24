# Local Document Anonymizer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el recorrido local TXT/Markdown → revisión humana → TXT nuevo verificado, sin modificar originales ni prometer anonimato.

**Architecture:** Opción A: motor modular y PySide6 en un mismo proceso. El núcleo usa biblioteca estándar y acepta un detector mediante protocolo; la GUI y los adaptadores NLP se incorporan después. Un único worker de Qt ejecuta operaciones costosas, con cancelación cooperativa y descarte de resultados tardíos.

**Tech Stack:** Python 3.12 arm64 ya disponible, biblioteca estándar y unittest para el núcleo. PySide6, Presidio y spaCy con modelo español local requieren autorización separada antes de instalar o descargar. No usar el entorno de graphify como entorno de la aplicación.

**Spec:** [Especificación aprobada](../specs/2026-10-23-local-document-anonymizer-design.md).

**Ejecución elegida:** nativa en esta sesión, por unidades pequeñas. La especificación está aprobada y el plan preaprobado; no repetir esa aprobación. Reutilizar el checkout actual limpio y crear la rama `codex/text-mvp` antes de escribir producto, con commit y push verificados por unidad. Mantener `main` en la documentación aprobada hasta revisar la integración. No instalar paquetes automáticamente ni introducir nuevos servicios. Las tareas 1–5 pueden completarse sin dependencias externas. El estado inicial no tiene código ni pruebas de producto.

## Global Constraints

- macOS Apple Silicon; una sesión y un archivo `.txt`, `.md` o `.markdown` cada vez; UTF-8 estricto con BOM inicial opcional.
- Máximo **1 MiB de bytes** y **100 000 caracteres Unicode**; nunca truncar ni normalizar Unicode o saltos de línea. Salida UTF-8 sin BOM.
- Rechazar NUL, C0/C1 salvo TAB/CR/LF, controles bidireccionales, U+200B, U+2060 y BOM interior; Markdown como texto plano, sin recursos externos.
- Soporte automático español: correo, teléfono español, DNI/NIF personal, NIE, pasaporte español, IBAN español, PERSONA/ORGANIZACION/UBICACION y fechas; dirección manual. Títulos/personajes/códigos por vocabulario literal o selección manual.
- Sin nube, telemetría, modelos remotos, descargas automáticas, logs persistentes, historial ni correspondencias guardadas. Sin datos sensibles en diagnósticos o informe.
- Origen inmutable; resultado nuevo; ninguna sobrescritura, incluso ante carreras, symlinks o hardlinks. Fallar cerrado ante cobertura incompleta, conflicto o verificación fallida.
- Etiquetas por orden de primera aparición y grupo; redacción `[ELIMINADO]` o supresión sin marcador cuando este reintroduciría un valor seleccionado.
- Toda edición de decisiones invalida vista previa, confirmación y rechazos residuales; solo una transformación desde el original.
- Solo fixtures sintéticos. Dobles de detector sirven para probar el protocolo, nunca para afirmar eficacia de Presidio/spaCy.
- Un commit descriptivo y push por cambio lógico con comprobaciones correctas; comprobar igualdad de SHA remoto/local. No force push. El grafo existente es una instantánea histórica, no se regenera en cada commit.

## Review Focus

1. Una colisión creada después del preflight nunca debe sustituir un archivo: test real de publicación exclusiva en tarea 4.
2. Una selección después de emoji o caracteres combinados no debe desplazar el fragmento: posiciones Python en tareas 1–3 y conversión UTF-16 en tarea 7.
3. Una eliminación que une texto puede recrear información sensible: comprobar salida completa y cruces de segmentos en tareas 2–3.
4. Cancelación y resultados antiguos no pueden rehabilitar una revisión ni borrar archivos ajenos: tareas 4–5 y worker Qt de tarea 7.
5. Excepciones de dependencias y fallos al limpiar no pueden volcar texto o borrar un destino sustituido por otro proceso: tareas 4, 6 y 8.

## Archivos y contratos compartidos

Crear paquete `src/local_anonymizer/` sin imports de Qt/NLP desde el núcleo. `pyproject.toml` contiene metadatos y dependencias opcionales, sin ejecutar instalación; `.venv/` permanece ignorado. Tests mediante `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.

- `domain.py`: enums `Category`, `Confidentiality`, `Disposition`, `Action`; dataclasses inmutables `FileIdentity(device, inode)`, `Document`, `Finding`, `Decision`, `Review`, `Segment`, `Preview`, `ResidualKey`, `ResidualDecision`, `Verification`, `Receipt`; excepción `AnonymizerError(code)` sin datos sensibles. Campos con texto, rutas o correspondencias excluidos de repr.
- `Document`: `session_id`, `revision`, `source_path`, `identity`, `text`, `source_sha256`. `Finding`: `id`, `session_id`, `start`, `end`, `category`, `confidentiality`, `provenance`, `score=None`, `group_id=None`. `Decision`: `finding_id`, `disposition`, `action`, `group_id=None`.
- `Review`: `document`, `findings`, `decisions`, `revision`, `coverage_complete`, `confirmed`. `Preview`: `text`, `segments`, `selected_values`, `labels`, `review_revision`, `sha256`. Las colecciones son tuplas, no diccionarios mutables compartidos.
- `Segment`: intervalo de salida y de origen, más `finding_id=None` para texto conservado; conservar también segmentos sustituidos de salida vacía. `ResidualKey`: sesión, revisión, digest de salida, fingerprint del detector, intervalo, categoría y procedencia. `Verification`: esos vínculos, `ok`, códigos de problemas y candidatos residuales. `Receipt`: destino, identidad y SHA-256 final; ruta excluida de repr.
- `Detector` (protocolo de `verification.py`): propiedad `fingerprint: str` y `analyze(text: str, session_id: str) -> tuple[Finding, ...]`. El adaptador debe devolver todos los conflictos sin ocultarlos por puntuación.
- `ingest.py`, `transform.py`, `verification.py`, `export.py`, `report.py`, `session.py`, `detectors.py`, `gui.py` y `__main__.py` según las tareas siguientes. Mantener módulos centrados, sin framework de plugins ni clases innecesarias.

## Task 1: Dominio y lectura acotada

**Files:** crear `pyproject.toml`, `src/local_anonymizer/__init__.py`, `domain.py`, `ingest.py`, `tests/test_ingest.py`, `tests/test_domain.py`.

**Interfaces:** produce tipos anteriores y `load_document(path: Path) -> Document`. La revisión inicial es 0; una sesión nueva recibe un ID aleatorio. Rechazar entradas no regulares y symlinks de entrada en esta versión. Leer descriptor con tamaño acotado; comparar fstat antes/después para detectar cambios durante la lectura. No seguir cambios posteriores.

- [x] Crear `.venv` con el Python 3.12 arm64 existente y `venv --without-pip`; no descargar Python ni instalar paquetes.
- [x] Escribir pruebas de límites exactos, UTF-8/BOM, CRLF, emoji, formato incorrecto, controles y archivo cambiado durante lectura; usar `TemporaryDirectory` y originales sintéticos.

```python
def test_preserves_crlf_and_non_bmp(self):
    source.write_bytes(b'\xef\xbb\xbf' + 'Hola 😀\r\n'.encode())
    self.assertEqual(load_document(source).text, 'Hola 😀\r\n')
    self.assertEqual(source.read_bytes(), original_bytes)
```

- [x] Ejecutar `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_ingest.py' -v`; registrar fallo por módulo ausente.
- [x] Implementar los tipos y la lectura mínima; mensajes de error solo por código, sin texto/ruta ni traceback de terceros.
- [x] Repetir tests de entrada y dominio; añadir 1 048 576/1 048 577 bytes, 100 000/100 001 caracteres y repr sin centinelas sensibles. Se exige PASS.
- [x] Commit `feat: add validated local text ingestion`; push y verificar SHA.

## Task 2: Revisión, etiquetas y mapa de procedencia

**Files:** crear `transform.py`, `tests/test_transform.py`; ampliar `domain.py` solo si lo exige el contrato.

**Interfaces:** consume `Review`; produce `build_preview(review: Review) -> Preview` y `map_output_span(preview: Preview, start: int, end: int) -> tuple[Segment, ...]`. Construcción sin exigir `confirmed` (la confirmación ocurre después); exigir cobertura y decisiones completas. Etiquetas reservadas ya presentes en la fuente se saltan.

- [x] Escribir tests de pendientes, duplicados agrupables, conflictos, sesión incorrecta, grupos separados, alias explícitos, redacción vacía, etiquetas reservadas y coincidencias repetidas.

```python
def test_same_group_has_same_label(self):
    self.assertEqual(build_preview(review).text, 'PERSONA_001 y PERSONA_001')
    self.assertEqual(review.document.text, 'Ana y Ana')
```

- [x] Ejecutar `... -m unittest discover -s tests -p 'test_transform.py' -v` y observar FAIL antes de implementar.
- [x] Implementar reconstrucción por intervalos no solapados y orden de primera aparición. Preservar todos los segmentos y usar valores originales seleccionados solo en RAM.
- [x] Ejecutar el fichero de tests y regresión de tarea 1. Probar que segmentos conservados concatenados coinciden exactamente con sus intervalos originales, incluidos CRLF y emoji. Se exige PASS.
- [x] Commit `feat: add reviewed transformations and provenance`; push y verificar SHA.

## Task 3: Verificación residual vinculada a revisión

**Files:** crear `verification.py`, `tests/test_verification.py`.

**Interfaces:** consume `Review`, `Preview`, `Detector`; produce `verify_preview(review: Review, preview: Preview, detector: Detector, rejections: tuple[ResidualDecision, ...] = ()) -> Verification`. El resultado liga sesión, revisión, digest y configuración. Nunca escribir archivos en esta tarea.

- [x] Escribir tests con detector determinista: valor original persistente, contenido recreado al unir segmentos, etiqueta detectada como falso positivo, cruce conservado/sustituido y rechazo caducado por revisión/configuración/digest.

```python
def test_selected_value_elsewhere_blocks_export(self):
    result = verify_preview(review, preview, detector)
    self.assertFalse(result.ok)
    self.assertIn('SELECTED_VALUE_REMAINS', result.issues)
```

- [x] Ejecutar `... -m unittest discover -s tests -p 'test_verification.py' -v` y observar FAIL.
- [x] Implementar comparación con reconstrucción esperada, búsqueda exacta residual y segunda pasada. Heredar rechazos del original solo con correspondencia continua exacta de segmentos y misma categoría/procedencia; nunca por valor igual. Rechazos de salida requieren `ResidualKey` completo. No convertir coordenadas residuales en hallazgos originales.
- [x] Ejecutar tests del módulo y toda la regresión. Confirmación humana falsa y detector que falla deben bloquear; ningún mensaje/repr contiene centinelas. Se exige PASS.
- [x] Commit `feat: verify residual content against review state`; push y verificar SHA.

## Task 4: Publicación sin sobrescritura e informe

**Files:** crear `export.py`, `report.py`, `tests/test_export.py`, `tests/test_report.py`.

**Interfaces:** `publish_text(review: Review, preview: Preview, verification: Verification, destination: Path) -> Receipt`; `build_report(receipt: Receipt, counts: dict[str, int], versions: dict[str, str]) -> dict` y `save_report(report: dict, destination: Path) -> Receipt`. Contenido sensible fuera del esquema del informe; validar claves/valores, no aceptar diccionarios arbitrarios como informe final.

- [x] Escribir tests de destino existente, symlink/hardlink al original, bytes y permisos de salida, espacio/permisos/lectura fallidos, colisión concurrente y sustitución de destino antes de limpiar. Probar informe sin texto, valores, rutas o hash de origen.

```python
def test_concurrent_destination_is_never_overwritten(self):
    # Introducir el competidor justo antes de os.link sobre archivos reales.
    self.assertRaises(AnonymizerError, publish)
    self.assertEqual(destination.read_bytes(), b'competidor')
    self.assertEqual(source.read_bytes(), original_bytes)
```

- [x] Ejecutar tests del módulo y observar FAIL.
- [x] Implementar directorio fijado con descriptor, temporal aleatorio exclusivo 0600, escritura/fsync y lectura de comprobación. Publicar con `os.link` sin reemplazo; un fallo de soporte no permite fallback a rename/copia sobrescribible. Reabrir destino con no-follow, comprobar identidad/bytes/digest y limpiar únicamente inodos propios. Usar `dir_fd` para no depender de cambios de symlinks en directorios.
- [x] Ejecutar tests en el sistema de archivos local y regresión; comprobar que no quedan temporales en éxito y que limpieza fallida se comunica sin traceback sensible. Informe independiente: su fallo no borra el TXT correcto. Se exige PASS.
- [x] Commit `feat: publish verified copies without replacing files`; push y verificar SHA.

## Task 5: Estado de sesión y cancelación

**Files:** crear `session.py`, `tests/test_session.py`.

**Interfaces:** `Session` coordina `load`, `set_findings`, `set_decisions`, `preview`, `confirm`, `verify` y `cancel`; métodos reciben un token de trabajo `(session_id, revision, job_id)` para resultados asíncronos. No depende de Qt.

- [ ] Escribir tests de cambio de decisiones tras confirmar, resultado tardío de otro documento, cancelación pendiente, un solo trabajo activo y limpieza de estado al cerrar. `confirmed` no se vuelve verdadero por terminar un detector.

```python
def test_late_result_cannot_reenable_export(self):
    session.cancel()
    self.assertFalse(session.accept_result(old_token, findings))
    self.assertFalse(session.can_export)
```

- [ ] Ejecutar tests del módulo y observar FAIL.
- [ ] Implementar estado, tokens y revocación; ejecutar regresión con detector doble, sin presentarla como validación de NLP real.
- [ ] Commit `feat: manage review sessions and stale work results`; push y verificar SHA.

## Task 6: Entorno y detección real — puerta de autorización

**Files:** crear `detectors.py`, `tests/test_detectors.py`, ficheros de requisitos bloqueados y `README.md`; ampliar metadatos de proyecto.

**Interfaces:** `LocalDetector(model_path: Path)` implementa `Detector`; carga solo un modelo ya presente, recognizers explícitos para español/España y categorías declaradas. `literal_findings(document: Document, terms: tuple[tuple[str, Category], ...]) -> tuple[Finding, ...]` no admite regex arbitrarias.

- [ ] Consultar metadatos oficiales para identificar versiones compatibles con Python 3.12, wheels arm64, licencias, tamaño de descargas y modelo concreto. Registrar lista y procedencia; no resolver instalando sin permiso.
- [ ] Presentar la instalación local y descarga del modelo como solicitud concreta. **Esperar autorización para esos pasos**, continuando únicamente trabajo independiente. No incorporar LLM, GPU, extras cloud o nuevos modelos.
- [ ] Tras autorización, preparar entorno aislado, lock con hashes y registro de modelo/revisión/checksum/licencia. No modificar entornos existentes ni almacenar rutas personales en Git.
- [ ] Escribir pruebas: recurso ausente bloquea sin red; excepciones sanitizadas; ORG expuesta; recognizers ES habilitados; vocabulario literal exacto, mayúsculas, límites y solapamientos.
- [ ] Observar FAIL, implementar adaptador y ejecutar pruebas reales con el modelo local, más regresión. Si falta una categoría declarada, informar antes de sustituirla por detector propio.
- [ ] Commit `feat: integrate explicitly configured offline Spanish detection`; push y verificar SHA.

## Task 7: GUI y worker

**Files:** crear `gui.py`, `__main__.py`, `tests/test_gui.py`; ampliar README.

**Interfaces:** `MainWindow` usa `Session`, el detector aprobado y un worker de Qt; mostrar entrada y previsualización de solo lectura y texto plano. Menú para abrir, tabla de candidatos, aceptar/rechazar/corregir, selección manual, términos, grupos, acción, confirmación, rondas residuales, destino e informe independiente.

- [ ] Escribir tests de Qt con `unittest` y `QtTest`, sin añadir pytest-qt: UTF-16 con emoji, confirmación invalidada, un trabajo activo, cancelación pendiente, HTML mostrado literalmente y errores sin texto sensible.
- [ ] Observar FAIL; implementar interfaz mínima y mensajes profesionales en español; no añadir servicios ni exponer configuración técnica innecesaria.
- [ ] Ejecutar tests con `QT_QPA_PLATFORM=offscreen` y un smoke manual en macOS. Registrar lo automático y lo observado por separado. No afirmar éxito de la GUI por inspección estática.
- [ ] Commit `feat: add local document review desktop workflow`; push y verificar SHA.

## Task 8: Evaluación, privacidad y entrega

**Files:** crear `tests/fixtures/`, `tests/test_acceptance.py`, `tests/test_privacy.py`, `tests/evaluate_detection.py`, `CHANGELOG.md`; ampliar README con instalación, mantenimiento, límites y validación.

- [ ] Construir y congelar corpus sintético separado de desarrollo: 50 positivos/50 negativos por identificador exigido; 100 entidades por PERSONA/ORGANIZACION/UBICACION; fecha/pasaporte con métricas publicadas; términos conocidos y producciones desconocidas separados. Guardar anotaciones, hash y denominadores, sin materiales reales.
- [ ] Ejecutar evaluación real; exigir los umbrales de la sección 9 de la especificación. Publicar falsos negativos; si se ajusta contra el corpus, reclasificarlo como desarrollo y crear evaluación independiente. No bajar umbrales ni sustituir datos ausentes por estimaciones.
- [ ] Ejecutar regresión de núcleo, adaptadores y GUI; pruebas de centinelas en diagnósticos/informe/temporales. Comprobar ejecución sin red con mecanismos de prueba del proceso, sin cambiar la seguridad del equipo; señalar los límites de esa evidencia.
- [ ] Medir arranque frío/caliente, análisis 20 000/100 000 caracteres, memoria y cancelación; smoke de apertura/revisión/exportación real en macOS. Ningún original puede cambiar.
- [ ] Solicitar revisión final de código y resolver hallazgos antes de declarar aceptación. Documentar diferencias entre núcleo probado, integración real, GUI y métricas. Commit `test: document acceptance evidence and operating limits`; push y verificar SHA.

## Autorrevisión del plan

- Cobertura: secciones 3–5 de la especificación → tareas 1, 2, 6 y 7; sección 6 → 3, 5 y 7; sección 7 → 2–4; privacidad → 1, 4, 6 y 8; aceptación → pruebas por tarea y tarea 8; preparación/versionado → todas las tareas y puerta 6.
- Interfaces: todos los tipos compartidos se definen en tarea 1; los adaptadores reciben el protocolo de tarea 3; la GUI consume Session y las mismas funciones, sin duplicar motores.
- Review Focus: los cinco casos tienen pruebas asignadas, incluidos colisiones reales, Unicode, uniones de texto, resultados tardíos y limpieza condicionada a identidad.
- Método: TDD por unidad, pruebas de biblioteca estándar para el núcleo; no confundir dobles, pruebas de integración y métricas del modelo. No se instalan dependencias para adelantar artificialmente el estado de aceptación.
- Estado inicial: plan guardado antes de escribir producto; las casillas solo se marcarán con evidencia de ejecución. El plan ya está preaprobado por el usuario.
