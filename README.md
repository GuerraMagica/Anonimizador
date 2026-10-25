# Local Document Anonymizer

Aplicación local para revisar información sensible y guardar copias saneadas. La versión **0.2.0.dev0** incorpora Markdown, PDF, DOCX, OCR y lotes. Las puertas NER del corpus independiente pasan; la aceptación completa de uso profesional sigue pendiente. La revisión humana y del riesgo contextual permanece obligatoria: ninguna comprobación certifica anonimato.

## Ejecutar

Desde la carpeta del proyecto, con su entorno y recursos preparados:

```sh
PYTHONPATH=src .venv/bin/python -m local_anonymizer
```

1. Pulsa **Abrir documentos / lote**. Cada documento mantiene su revisión independiente; seleccionar el siguiente lo carga y analiza localmente.
2. Revisa el texto y, en documentos visuales, cada página original. Decide todos los candidatos, corrige los fragmentos y añade omisiones. Arrastra sobre una página original para redactar una zona que OCR no haya detectado. Puedes quitarla en la lista de zonas.
3. Construye la vista previa. Revisa todo el texto y todas las páginas de salida, marca la casilla de revisión y confirma. Cambiar candidatos, vocabulario o zonas revoca la confirmación.
4. Revisa los residuales del texto y de una segunda OCR de la salida visual. Corrige el original o rechaza explícitamente los falsos positivos de esa salida. Un valor seleccionado que persiste siempre bloquea la exportación.
5. Guarda una copia nueva. TXT/Markdown producen TXT. PDF/DOCX/imagen producen **PDF rasterizado** con la apariencia y tamaños de página del render local. El botón de lote exporta únicamente los documentos ya verificados y omite los pendientes; comunica errores por separado. Nunca sobrescribe destinos existentes ni elimina copias correctas por un fallo posterior.

Markdown dispone de vista renderizada y fuente literal separadas. No carga automáticamente imágenes, hojas de estilo o recursos. Un enlace compatible muestra su destino y requiere una acción explícita antes de abrir la aplicación asociada o el navegador. Los archivos locales enlazados deben estar dentro de la carpeta del documento; se rechazan scripts, ejecutables y escapes mediante enlaces simbólicos.

## Formatos y límites

| Entrada | Tratamiento | Salida |
| --- | --- | --- |
| TXT / Markdown UTF-8 | Texto original, selección exacta; Markdown renderizado aparte | TXT nuevo |
| PDF nativo o escaneado | Todas las páginas a imagen y OCR ES/EN | PDF nuevo de imágenes saneadas |
| DOCX | Copia convertida por LibreOffice local contenido, después imagen/OCR | PDF nuevo; no DOCX editable |
| PNG / JPEG / TIFF | Todos los frames, OCR y zonas manuales | PDF nuevo |

Texto canónico: 100.000 caracteres, sin truncar. TXT/MD: 1 MiB. Visuales: 50 MiB, 50 páginas y 20 MP por página. Lote: 20 documentos / 200 MiB; imágenes PNG retenidas: 300 MiB entre documentos. Estos límites no equivalen a un máximo de RAM del proceso: render, modelo y transferencia entre procesos necesitan memoria adicional.

El PDF final contiene imágenes comprobadas, sin texto recuperable ni capas, adjuntos, acciones, formularios, firmas o metadatos del original. Se cubren palabras OCR completas con margen; las etiquetas se dibujan solo cuando caben, o se utiliza redacción negra. OCR puede omitir letras, manuscritos y otros contenidos: las zonas manuales y la revisión visual son esenciales. DOCX no promete equivalencia tipográfica exacta con Word; se rechazan relaciones externas y contenido activo, incluidos documentos con ciertos hipervínculos externos.

La cancelación descarta resultados tardíos. NER comprueba cancelación entre ventanas y Office termina su grupo de procesos propio. PDF/OCR ejecutado desde la interfaz usa procesos `spawn`, porque PyMuPDF no admite uso entre varios hilos. Una llamada nativa bloqueada se detiene tras el plazo del supervisor (600 s; gracia de cancelación 60 s). La publicación de un archivo empezado se completa o comunica su fallo; cancelar el lote detiene las siguientes copias. El cierre espera al trabajo activo.

Si una escritura falla puede quedar una copia parcial: se comunica la ubicación elegida y no se borra automáticamente. No se garantiza borrado físico en RAM, SSD, snapshots o carpetas sincronizadas. Los originales permanecen intactos y los documentos no se envían a servicios externos.

## NER y validación

El detector activo combina GLiNER multilingüe local con los recognizers estructurados de Presidio. Mantiene candidatos conflictivos para revisión. Vocabulario literal de sesión, grupos de alias y redacción por intervalos conservan el comportamiento del MVP. No hay descargas durante el análisis; recursos ausentes o modificados bloquean la operación.

Evaluación congelada v3: 100 documentos sintéticos, al menos 100 entidades por categoría, exactitud de intervalos, umbrales de precisión y recall del 90 % sin rebajarlos:

| Categoría | Precisión | Recall |
| --- | ---: | ---: |
| Persona | 100 % | 100 % |
| Organización | 100 % | 96 % |
| Ubicación | 95,24 % | 100 % |

La [evidencia de NER](docs/ner-enhanced-ner-independent-v3.json) incluye errores, fingerprint, hash del corpus y mediciones. Las plantillas sintéticas no representan todos los documentos profesionales. Los modelos spaCy pequeño/mediano y sus evaluaciones anteriores se conservan como referencia histórica; ya no son el detector activo. Consulta el [informe de esta versión](docs/informe-2026-10-25.md) para pruebas, resultados y pendientes.

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
RUN_ENHANCED_NER=1 QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_enhanced_ner.py
RUN_OFFICE_INTEGRATION=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_office.py
PYTHONPATH=src .venv/bin/python scripts/evaluate_enhanced_ner.py ner-independent-v3
PYTHONPATH=src .venv/bin/python scripts/evaluate_identifiers.py
PYTHONPATH=src .venv/bin/python scripts/benchmark_ner.py
```

Las pruebas nativas Office requieren macOS y contención disponible; un sandbox anidado puede impedirlas. Las pruebas Qt automatizadas no sustituyen una revisión manual completa en macOS con documentos representativos autorizados.
Para activar también el lote mixto completo: `RUN_DESKTOP_INTEGRATION=1`. La regresión histórica del MVP requiere además el modelo spaCy pequeño documentado en su evaluación anterior; la aplicación 0.2 utiliza GLiNER y no lo necesita para analizar.

## Preparar otro entorno

Python 3.12 arm64/macOS. La preparación es una acción explícita con Internet; no instala nada globalmente:

```sh
python3.12 -m venv .venv
uv pip install --python .venv/bin/python --require-hashes --only-binary :all: -r requirements.lock
.venv/bin/python scripts/download_ner.py
.venv/bin/python scripts/prepare_ocr.py --download
```

NER necesita aproximadamente 1,16 GB de recursos locales fijados y OCR 6,4 MB. Procedencias, hashes, tamaños y licencias: [NER](docs/ner-resources.json), [OCR](docs/ocr-model-artifacts.json), [dependencias](docs/dependency-next-artifacts.json). No se publican pesos, entornos ni documentos originales.

DOCX necesita LibreOffice local: se busca `soffice` en PATH, `/Applications/LibreOffice.app`, o una ruta absoluta de ejecutable guardada únicamente en `.venv/resources/soffice-path`. No se modifica el perfil del usuario. La ausencia de motor o de contención produce un error explícito. El entorno comprobado usa LibreOfficeDev 26.8 alpha; compatibilidad con una versión estable y otros equipos queda pendiente.

PyMuPDF declara AGPL-3.0 o licencia comercial; GLiNER y tessdata Apache-2.0, tokenizer MIT. Los componentes Qt y dependencias transitivas tienen condiciones propias; los pesos spaCy históricos son GPL-3.0. Revisión de licencias, empaquetado, firma y notarización quedan pendientes antes de distribuir un instalador.

## Desarrollo

[Diseño aprobado](docs/superpowers/specs/2026-10-25-next-version-design.md) y [plan](docs/superpowers/plans/2026-10-25-next-version.md). Los cambios completos, comprobados y revisados se registran con commit descriptivo y push a GitHub, excluyendo datos privados. `graphify-out/` es una instantánea documental histórica y no representa el código actual.
