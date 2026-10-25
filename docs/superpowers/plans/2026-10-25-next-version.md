# Next Version Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar NER y entregar Markdown/enlaces, PDF, DOCX, OCR, lotes y exportación con maquetación visual con controles verificables.

**Architecture:** Núcleo existente por intervalos, fuentes visuales normalizadas a PNG+OCR, salida PDF nueva sin estructuras originales y vista/revisión por documento. Trabajos independientes de NER, formatos y conversión DOCX; integración GUI en el controlador.

**Tech Stack:** Python 3.12, Qt Widgets, Presidio, detector NER local evaluado, PyMuPDF/Tesseract, Pillow, parser XML seguro y LibreOffice local para DOCX. Dependencias fijadas e instaladas solo en el proyecto.

**Spec:** ../specs/2026-10-25-next-version-design.md. Plan e implementación preaprobados por el usuario; no preguntas durante ejecución.

## Global Constraints

- Originales intactos, revisión humana real, publicación exclusiva, cero cargas de documentos a servicios y sin gastos. Solo fixtures sintéticos en Git.
- Texto máximo 100 000 caracteres; TXT/MD 1 MiB; visuales 50 MiB/50 páginas/20 MP por página/300 MiB PNG RAM; DOCX 2 000 entradas/200 MiB expandidos; lotes 20 documentos/200 MiB.
- Sin truncar, sin aceptar cobertura incompleta ni declarar superadas puertas fallidas. NER exacto ≥90 % precisión/recall por categoría, ≥100 entidades/categoría.
- No sobrescribir destinos ni borrar archivos publicados tras fallo. Un worker activo, cancelación cooperativa o del proceso de conversión propio y descarte de resultados tardíos.
- Commit/push por unidad completa y comprobada, SHA remoto igual. No main merge ni force push. Mantener exclusión de originales/pesos/entornos/cachés.

## Review Focus

1. Un enlace Markdown o una relación OOXML no puede ejecutar scripts ni provocar lecturas o conexiones automáticas.
2. Una redacción visual debe retirar píxeles y capas originales, no solo pintar un rectángulo sobre contenido recuperable.
3. Una región seleccionada en otra página o documento no debe aplicarse a la fuente equivocada; editarla revoca confirmación.
4. Cancelación/lote parcial no puede publicar trabajos viejos, borrar resultados correctos o marcar documentos no revisados como aceptados.
5. Ventanas NER y OCR no pueden truncar cobertura silenciosamente; la evaluación final no comparte ejemplos ajustados.

## Task 1: Contratos y dependencias (controlador)

Files: crear source.py, tests/test_source.py; fijar dependencias y artefactos. Reutilizar checkout limpio en rama codex/next-version desde 4a23bff.
- [ ] Escribir tests de valores, rectángulos, repr y límites; observar RED; implementar dataclasses del contrato; GREEN.
- [ ] Resolver versiones y wheels arm64 antes de instalar. Preparar PyMuPDF/Pillow/defusedxml/python-docx y stack NER compatible; conservar locks/hashes. Preparar tessdata ES/EN y motor DOCX local sin configuraciones globales.
- [ ] Regresión, commit y push de contratos/entorno reproducible, sin binarios ni pesos.

## Task 2: NER mejorado y evaluación (agente NER)

Files: crear ner.py, tests/test_enhanced_ner.py, scripts de preparación/evaluación y fixtures/evidencia nuevos. No modificar requisitos ni GUI compartidos sin coordinar.
Interfaces: EnhancedDetector y analyze_cancellable según spec; mantener protocolo existente y structured recognizers. Recurso oficial local, safetensors, sin trust_remote_code, sin descargas en análisis.
- [ ] Investigar API/versiones aprobadas, preparar recurso local con checksum y documentar tamaño/licencia. TDD de recurso ausente, excepciones, offsets, ventanas solapadas, conflictos, cancelación y fingerprint.
- [ ] Afinar solo contra desarrollo v1/v2; congelar evaluación v3 independiente con tipos/plantillas cruzados antes de medir. No bajar objetivos. Publicar métricas/errores reales.
- [ ] Verificar offline real, integridad y rendimiento; commit/push revisable. Si falla, iterar con otra evaluación independiente después de ajustes, sin afirmar aceptación.

## Task 3: DOCX a representación visual (agente Office)

Files: office.py, tests/test_office.py. Produce convert_docx(payload, cancelled) -> (pdf_bytes, notes).
- [ ] TDD de ZIP inválido/bomba/rutas/duplicados/macros/objetos activos, relaciones externas, motor ausente y cancelación. Inventariar partes no visibles sin afirmar cobertura OCR de ellas.
- [ ] Convertir copia privada con LibreOffice local, perfil propio restrictivo y red bloqueada por proceso cuando disponible; nada de cambiar perfiles del usuario. Errores saneados y recursos acotados.
- [ ] Fixture DOCX real con párrafos, estilos, tabla, cabecera y metadatos. Reabrir PDF, comprobar layout/estructura, original intacto y documentar motor. Commit/push revisable.

## Task 4: PDF/imagen/OCR y salida visual (agente Formatos)

Files: formats.py, layout.py, tests/test_formats.py, tests/test_layout.py. Consume source.py y office.convert_docx (importación diferida para desarrollo paralelo).
- [ ] TDD de PDF nativo/escaneado/imagen y errores/límites/cifrado/páginas; OCR real ES/EN y mapa palabra→rectángulo. Texto canónico íntegro y cancelación entre páginas.
- [ ] TDD de transformación visual por intervalos/regiones, dimensiones, sustituciones que no caben, píxeles cubiertos, contenido oculto/metadata eliminados, verificación vigente y destino exclusivo.
- [ ] Implementar raster seguro y salida PDF nueva; reapertura/comparación exacta de imágenes esperadas, segunda OCR/detección accesible a integración. Validación visual de fixture real. Commit/push revisable.

## Task 5: Markdown y recursos (controlador)

Files: markdown_view.py, tests/test_markdown_view.py. Source plain-text sigue permitiendo selección exacta; render es vista separada.
- [ ] TDD de HTML/script/imagen remota, esquemas peligrosos, ruta fuera de raíz, recursos locales permitidos y enlaces HTTP(S) explícitos con destino visible.
- [ ] Implementar QTextBrowser sin carga automática, apertura controlada, política de enlaces y avisos. Regresión y commit/push.

## Task 6: Lotes e integración GUI (controlador)

Files: batch.py, gui.py, __main__.py, session.py, tests/test_batch.py, tests/test_gui.py; vistas auxiliares si responsabilidad lo exige.
- [ ] TDD de lotes, estado independiente, límites, pendientes, cambio de fuente, regiones manuales, confirmación/visual preview revocadas y resultados tardíos.
- [ ] Integrar carga visual en worker, páginas/imágenes y regiones, Markdown renderizado, selección NER validada, navegación de lote y exportación TXT/PDF con revisión individual. Un trabajo activo.
- [ ] Flujo real con fixtures de todos los tipos, lote parcial, errores, cancelación y publicación exclusiva; medir rendimiento/memoria y distinguir automatización/manual. Commit/push.

## Task 7: Aceptación de versión y entrega

Files: README, CHANGELOG, informe y métricas/requisitos reproducibles.
- [ ] Ejecutar regresión completa, evaluación independiente NER/identificadores, pruebas de privacidad, visuales y formatos; registrar pruebas no realizadas sin inventarlas.
- [ ] Revisión independiente del incremento e importantes corregidos con RED→GREEN. Mantener límites de aceptación honestos.
- [ ] Commit/push final verificado e informe conciso. No declarar completa la versión si una capacidad o puerta requerida sigue pendiente.
