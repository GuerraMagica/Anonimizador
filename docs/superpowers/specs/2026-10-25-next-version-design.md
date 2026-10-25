# Anonimizador — ampliación de la siguiente versión

Autorización: petición expresa del usuario del 25/10/2026, con plan e implementación preaprobados, sin preguntas durante esta ejecución. Amplía el MVP de texto; no declara completadas las puertas de aceptación anteriores.

## Objetivo y enfoque

Superar las puertas NER y añadir Markdown renderizado, apertura controlada de enlaces, PDF, DOCX, OCR, lotes y exportación con maquetación visible. Conservar originales, revisión humana y publicación exclusiva. La preaprobación técnica no equivale a confirmar el contenido de un documento. Solo fixtures sintéticos para desarrollo y evaluación; no reutilizar documentos personales del chat.

Decisiones de implementación del agente:

- Mantener el núcleo por intervalos y el protocolo Detector. Comparar un detector por etiquetas local con los modelos existentes; no bajar precisión/recall ni llamar independiente a un corpus utilizado para ajustes.
- Mantener fuente textual y vista renderizada separadas. El render Markdown no carga recursos automáticamente ni ejecuta contenido activo. El usuario puede abrir enlaces compatibles de forma explícita con destino visible, validación de esquema, ruta y tipo de recurso.
- Normalizar documentos visuales a páginas PNG y texto OCR con coordenadas. Para PDF se conserva la apariencia de cada página, sin trasladar estructuras, capas, adjuntos, JavaScript, formularios ni metadatos originales a la copia. Para DOCX, convertir una copia con LibreOffice local y perfil temporal restringido, después seguir la misma ruta visual. Las partes no visibles se inventarían: quedan excluidas físicamente de la salida visual, sin afirmar que el OCR las ha inspeccionado.
- La salida que conserva maquetación será PDF rasterizado, también para entradas DOCX. Conserva tamaños de página y apariencia del render local; no promete DOCX editable ni equivalencia tipográfica exacta entre Word y LibreOffice. TXT sigue disponible para el texto inspeccionado. Esto incluye DOCX como entrada y maquetación visual como salida; la limitación debe constar claramente en UI y documentación.
- OCR se ejecuta localmente, con Tesseract integrado en PyMuPDF y datos ES/EN fijados. Todas las páginas se rasterizan y pasan por OCR, incluidas páginas con texto nativo y posibles imágenes. Los errores de OCR no equivalen a ausencia de datos sensibles. La revisión visual de todas las páginas es obligatoria para un documento visual; se permiten áreas de redacción manual para omisiones del OCR.
- La redacción visual cubre palabras completas que intersectan un hallazgo, con margen de píxeles; las etiquetas se dibujan solo cuando caben de forma legible, usando redacción opaca en los demás casos. El resultado visual se previsualiza y se confirma, sin prometer exactitud de reemplazo carácter a carácter en un raster.
- Lotes con estado y revisión independientes por documento, un único trabajo costoso activo, ninguna aceptación automática de candidatos, y publicación nueva por archivo. Un fallo no elimina salidas correctas de otros elementos ni convierte un lote parcial en éxito completo.

## Límites y cobertura

Python 3.12 arm64/macOS. Texto canónico: máximo 100 000 caracteres por documento (sin truncar). TXT/Markdown conservan límite de 1 MiB y UTF-8 del MVP. PDF/DOCX/imagen: hasta 50 MiB de entrada, 50 páginas, 20 megapíxeles por página y 300 MiB de imágenes PNG en RAM; DOCX: máximo 2 000 entradas ZIP y 200 MiB expandidos, sin rutas de escape, entradas duplicadas, macros ni objetos incrustados ejecutables. Lotes: máximo 20 documentos y 200 MiB de entrada total. Fallar explícitamente ante límites o formatos no soportados, sin éxito parcial encubierto.

Admitir PDF textual y escaneado, DOCX normal sin macros/objetos activos, imágenes PNG/JPEG/TIFF para OCR y TXT/Markdown. Detectar cifrado, firmas/formularios/adjuntos o relaciones externas peligrosas y explicar su tratamiento. El parser no debe ejecutar macros ni actualizar enlaces. LibreOffice usa perfil temporal propio; el sandbox del proceso bloquea red y restringe escrituras cuando está disponible, y los fallos de contención se diagnostican sin relajar la seguridad global. No se edita configuración de Office ni seguridad del usuario.

Original leído con límites e identidad/digest; nunca escribir en su ruta. Destinos finales con creación exclusiva, sin borrar rutas automáticamente tras fallo. Reportar ubicaciones elegidas de copias parciales para inspección. Logs y errores sin textos ni rutas originales; no servicios externos durante análisis. Dependencias/modelos abiertos y locales autorizados por esta petición: fijar versión/hash/licencia/tamaño, revisar procedencia y registrar consumo, sin instalar globalmente ni introducir gastos.

## Contratos

`source.py`: valores inmutables `SourceKind`, `RasterPage(png, width_points, height_points, pixel_width, pixel_height)`, `TextBox(start, end, page, rect)`, `VisualRegion(page, rect)`, `LoadedSource(document, kind, pages=(), boxes=(), notes=())`; `rect` es una tupla de cuatro fracciones entre 0 y 1. PNG y datos de documento quedan fuera de repr. Índices de texto en Unicode Python. Las regiones visuales son independientes de los intervalos OCR y cambian la revisión al editarse.

`formats.py`: `load_source(path: Path, *, cancelled=lambda: False) -> LoadedSource`; `ocr_pdf(payload: bytes, *, cancelled=lambda: False) -> tuple[str, tuple[RasterPage, ...], tuple[TextBox, ...]]`. Texto canónico por palabras OCR, con espacios y separadores de página; mapeo exacto entre cada palabra y su rectángulo. El tipo de origen y su hash son del archivo original, no de un intermedio.

`layout.py`: `VisualPreview(review_revision, text_sha256, pages, sha256)`; `build_visual_preview(source, review, preview, regions=())` valida la transformación textual y produce páginas saneadas; `publish_layout(source, review, preview, verification, visual, destination, regions=()) -> Receipt` exige confirmación y verificación vigentes, reconstruye/compara el raster esperado y publica un PDF nuevo comprobado. Ningún adjunto/capa/texto original se copia al resultado. La revisión adicional mediante OCR del raster saneado queda vinculada al mismo estado.

`office.py`: `convert_docx(payload: bytes, *, cancelled=lambda: False) -> tuple[bytes, tuple[str, ...]]`, devuelve PDF de la copia y notas de inventario. Detección explícita de motor local; entorno de desarrollo puede guardar ruta en `.venv/resources/soffice-path`, nunca en Git. Perfil temporal con macros deshabilitadas y actualización de enlaces deshabilitada; cancelar termina solo el proceso de conversión propio.

`ner.py`: `EnhancedDetector` implementa Detector, carga solo modelos locales fijados; mantiene recognizers estructurados. Análisis por ventanas con solapamiento y offsets si el modelo tiene límite de tokens, sin truncar y conservando candidatos en conflicto. Proporciona `analyze_cancellable(text, session_id, cancelled)` para cancelación entre ventanas; fingerprint incluye modelo, etiquetas, umbrales y configuración.

`markdown_view.py`: vista Qt sin carga automática y política explícita de apertura de recursos. `batch.py`: `BatchEntry(source, session, regions, visual_preview, receipt)` y coordinador independiente de widgets. GUI integra fuentes, vistas, regiones, lotes, vista previa y exportación conservando revisión/worker único.

## Aceptación

Mantener regresión del MVP y las puertas de identificadores. NER: ≥100 entidades por categoría en evaluación congelada independiente, precisión y recall ≥90 % exactos. Si no se supera, documentar fallo, seguir mejorando con conjuntos de desarrollo y congelar otra evaluación; nunca modificar anotaciones para favorecer resultados.

Formatos: fixtures sintéticos de PDF nativo/escaneado, DOCX con estilos/tablas/cabeceras/notas y recursos, imágenes, Unicode, límites, ZIP malicioso, contenido activo y cifrado. Comprobar identidad del original, cobertura de páginas, caracteres/rectángulos, eliminación efectiva de texto y píxeles, metadatos y contenido oculto ausentes, dimensiones de páginas, reapertura y comparación de imagen final. Validación visual separada mediante render de páginas.

GUI: Markdown literal/rendido, enlaces bloqueados/permitidos, ningún recurso remoto automático, selección y regiones por coordenadas, cancelación, cambios invalidantes, pendientes fuera de página y lote, estados parciales y exportación nueva. Distinguir Qt offscreen de interacción manual en macOS. Informe conciso final con estado real por capacidad, métricas, descargas, pruebas, riesgos y SHA remoto.
