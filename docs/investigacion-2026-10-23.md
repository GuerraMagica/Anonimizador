# Local Document Anonymizer: investigación de alternativas

Fecha de consulta: 23 de octubre de 2026. Estado: investigación documental; no es una especificación aprobada ni autorización para implementar.

## Alcance y evidencia

El usuario ha confirmado que la primera versión puede exportar texto saneado aunque cambie la maquetación. Se mantienen procesamiento local, originales intactos, revisión humana, verificación posterior y ausencia de garantía de anonimato contextual.

Se han consultado documentación, repositorios y metadatos públicos de paquetes. No se han instalado paquetes, descargado pesos, ejecutado bibliotecas ni utilizado documentos reales. Las compatibilidades publicadas son evidencia documental, no pruebas en el Mac del usuario. Una publicación reciente demuestra actividad de publicación; no demuestra calidad, seguridad ni mantenimiento futuro.

## Matriz de detección

| Componente y repositorio oficial | Licencia y mantenimiento observado | Apple Silicon, español y offline | Capacidades, límites y decisión provisional |
| --- | --- | --- | --- |
| [Presidio](https://github.com/data-privacy-stack/presidio) | MIT. La [transición oficial](https://github.com/data-privacy-stack/presidio/blob/main/docs/project_transition.md) confirma gobernanza comunitaria bajo Data Privacy Stack. La página de [releases](https://github.com/data-privacy-stack/presidio/releases) muestra 2.2.364 publicada el 22/07/2026. | Usable como biblioteca Python local; compatibilidad completa de sus dependencias ARM pendiente de prueba. El [soporte de idiomas](https://presidio.dataprivacystack.org/analyzer/languages/) exige configurar modelo y recognizers; el valor predeterminado es inglés. | Texto, recognizers extensibles, patrones, contexto y checksums. Candidato principal para reutilizar detección estructurada. No es por sí mismo un saneador integral de PDF/DOCX. Usar solo componentes locales, sin recognizers remotos. |
| [spaCy](https://github.com/explosion/spaCy) y [modelos españoles](https://spacy.io/models/es) | Biblioteca MIT. Documentación y repositorio de la serie 3.8 accesibles; no se ha auditado la cadencia de commits. El artefacto concreto [es_core_news_sm 3.8.0](https://github.com/explosion/spacy-models/releases/tag/es_core_news_sm-3.8.0) declara GPL-3.0 y unos 12 MB. | El [instalador documentado](https://spacy.io/usage) contempla ARM/M1. El modelo pequeño está optimizado para CPU y puede cargarse localmente una vez instalado. No se ha medido su ejecución. | NER español generalista de dominio periodístico, no detector especializado de guiones. Evaluar como primera base; revisar por separado condiciones de biblioteca, pesos y redistribución antes de empaquetar. No confundir es_dep_news_trf con un modelo NER: el catálogo lo clasifica como vocabulario y sintaxis. |
| [GLiNER](https://github.com/urchade/GLiNER), modelo [urchade/gliner_multi-v2.1](https://huggingface.co/urchade/gliner_multi-v2.1) | Repositorio y modelo seleccionado declaran Apache-2.0. Ficha pública accesible; no se ha auditado su cadencia de mantenimiento. | Modelo declarado multilingüe. Inferencia local posible con artefactos previamente disponibles; instalación ARM, consumo y rendimiento en español pendientes. No se ha verificado MPS. | Permite proponer tipos de entidades mediante etiquetas. Candidato para una comparación posterior; no hay evidencia aquí de que reconozca mejor personajes o producciones. Excluir del MVP hasta demostrar mejora sobre la base y fijar revisión, licencia y recursos del artefacto. |
| Reglas y diccionarios mediante [Presidio](https://presidio.dataprivacystack.org/supported_entities/) y [EntityRuler de spaCy](https://spacy.io/api/entityruler) | Reutilizan los motores anteriores; no implican entrenar otro modelo. Los diccionarios del usuario pueden ser confidenciales. | Locales; idioma y vocabulario configurables. No requieren aceleración de GPU. | Adecuados para títulos, personajes, empresas e identificadores definidos por el usuario. Validar límites de palabra, variantes, mayúsculas y solapamientos. Empezar con entradas literales, no regex arbitrarias del usuario. |

La tabla oficial de Presidio incluye ES_NIF, ES_NIE y ES_PASSPORT, además de entidades globales como correos e IBAN. Esta cobertura declarada no prueba que cada recognizer esté habilitado para español ni que su precisión sea suficiente. Se deben probar configuración, variantes y contexto de cada tipo. [Entidades soportadas](https://presidio.dataprivacystack.org/supported_entities/).

Las empresas, los títulos y los personajes requieren etiquetas distintas de PERSONA. Un nombre ficticio puede ser confidencial sin constituir PII. Las puntuaciones de distintos motores no deben presentarse como probabilidades comparables sin calibración.

## Matriz documental

| Componente y repositorio oficial | Licencia y señal de mantenimiento | Compatibilidad, formatos y offline | Limitación comprobada e implicación |
| --- | --- | --- | --- |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause según [PyPI](https://pypi.org/project/pypdf/); última publicación allí observada: 21/10/2026. | Python puro, PDF, procesamiento local. Esa portabilidad es favorable para ARM, pero no sustituye una prueba de instalación y corpus. | Su documentación explica las dificultades de orden, fuentes y extracción, y que [no realiza OCR](https://pypdf.readthedocs.io/en/stable/user/extract-text.html). Candidato para importar PDF a texto en una etapa posterior. Extraer texto no demuestra inspección completa ni redacción del PDF original. |
| [python-docx](https://github.com/python-openxml/python-docx) | MIT. [PyPI](https://pypi.org/project/python-docx/) publica 1.2.0 del 16/06/2025; no se ha verificado una release más reciente ni auditado la actividad de commits. | DOCX, local. Wheel Python independiente de arquitectura; dependencias como lxml necesitan validación ARM propia. | La [API de Document](https://python-docx.readthedocs.io/en/latest/api/document.html) advierte que paragraphs omite párrafos dentro de marcas de revisión y tables no cubre todas las tablas. Útil para contenido ordinario, insuficiente como único inventario de OOXML. |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | AGPL/comercial según su [documentación de licencia](https://pymupdf.readthedocs.io/en/latest/about.html). Documentación actual consultada; cadencia de commits no auditada. | PDF y otros formatos; trabajo local. La [instalación oficial](https://pymupdf.readthedocs.io/en/latest/installation.html) declara wheels para macOS ARM de 64 bits. | Tiene [redacción aplicada](https://pymupdf.readthedocs.io/en/latest/page.html#Page.apply_redactions) y [scrub](https://pymupdf.readthedocs.io/en/latest/document.html#Document.scrub). El guardado y garbage collection importan; otras anotaciones pueden permanecer. Reservar para una fase que necesite PDF visual; revisar licencia y validar estructuras e imágenes. |
| Lectura de TXT/Markdown con biblioteca estándar de Python | Sin dependencia documental adicional. La versión de Python y sus condiciones se fijarán al preparar el entorno. | Texto Unicode, sin interpretación de imágenes ni ejecución de Markdown. Funcionamiento local previsto. | Leer toda la fuente, incluidos front matter, comentarios, URLs y bloques de código. Exportar TXT UTF-8 nuevo. No renderizar HTML ni cargar recursos externos. Es la superficie inicial más acotada. |

Para DOCX, importar a TXT elimina la necesidad de conservar el paquete OOXML en la salida, pero no justifica afirmar que se ha leído todo el original. Será necesario inventariar partes, relaciones externas, comentarios, revisiones, encabezados, pies, notas, texto oculto y objetos. Las partes desconocidas impedirán declarar cobertura completa.

Para PDF, la futura preinspección deberá distinguir texto extraíble, imágenes, anotaciones, formularios, adjuntos, capas, metadatos y acciones. Un PDF con algo de texto seleccionable puede contener páginas o regiones que requieran OCR. El [tratamiento de metadatos](https://pypdf.readthedocs.io/en/stable/user/metadata.html) incluye estructuras Info y XMP distintas; borrar Author no basta.

Una salida TXT debe describirse como copia del texto procesado, con su cobertura y omisiones. No como PDF o DOCX original saneado. Aunque no se exporten las imágenes, omitirlas puede hacer que el resultado sea incompleto para la tarea del usuario.

## Interfaz y aplicaciones existentes

| Alternativa y fuente oficial | Licencia, mantenimiento y plataforma | Evaluación para este proyecto |
| --- | --- | --- |
| [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/index.html), [repositorio](https://code.qt.io/pyside/pyside-setup.git/) | LGPLv3/GPLv3/comercial según componente. [PyPI](https://pypi.org/project/PySide6/) muestra 6.12.0 del 08/10/2026. Qt documenta [macOS arm64](https://doc.qt.io/qtforpython-6/overviews/qtdoc-macos.html). GUI local, textos traducibles; no es detector ni lector de documentos. | Recomendación provisional: Qt Widgets, adecuado para editor, lista de hallazgos y revisión. Evaluación de adecuación, no prueba de UX ni empaquetado. Limitar módulos; revisar licencias y avisos de terceros antes de distribuir. |
| [Tkinter](https://docs.python.org/3/library/tkinter.html), [código en CPython](https://github.com/python/cpython/tree/main/Lib/tkinter) | Interfaz estándar de Python a Tcl/Tk, documentada para macOS. Licencia de Python y licencias propias de Tcl/Tk a inventariar en la distribución. Documentación actual accesible; combinación concreta ARM/Tk no probada. | Alternativa razonable si domina minimizar dependencias. Mi valoración: una revisión textual compleja requerirá más trabajo de interfaz. No aporta por sí mismo saneamiento, NER ni verificación. |
| [Dangerzone](https://github.com/freedomofpress/dangerzone) | AGPL-3.0. La [instalación oficial](https://docs.dangerzone.rocks/latest/how-to/install/) ofrece 0.11.1 para Apple Silicon. Maneja documentos ofimáticos, PDF e imágenes. | Aplicación existente relevante para documentos maliciosos. Su [arquitectura](https://dangerzone.rocks/about/) utiliza Podman, VM y sandbox sin red durante la conversión. No sustituye la detección semántica ni la revisión de PII: el texto visible puede seguir siendo confidencial. No incorporarla como dependencia del MVP, por finalidad y complejidad. |

No se ha encontrado ni probado en esta revisión una aplicación que pueda darse por equivalente al conjunto completo de requisitos. Eso no demuestra que no exista. Dangerzone sirve como referencia de contención de documentos hostiles, no como prueba de anonimización.

## Riesgos y controles que deben entrar en el diseño

La tabla siguiente contiene propuestas, no controles implementados.

| Amenaza o error | Control propuesto | Límite o comprobación pendiente |
| --- | --- | --- |
| PII o secretos narrativos no detectados | Vocabularios locales, selección manual de fragmentos, revisión del texto completo y métricas por categoría. | La revisión humana y un corpus sintético no demuestran anonimato de documentos reales. |
| Revisiones, capas o imágenes omitidas | Inventario de cobertura; distinguir procesado, pendiente y no inspeccionable; bloquear verificación completa ante desconocidos. | Cada formato requiere fixtures propios; no inferir cobertura por ausencia de errores. |
| Solapamientos o desplazamiento de posiciones | Trabajar sobre una versión inmutable del texto, conservar procedencia de hallazgos y resolver conflictos antes de sustituir. | Una edición posterior invalida revisión y verificación; debe exigir nuevo análisis. |
| Confundir personas con nombres iguales | Identidad por tipo y valor según política explícita; alias unidos solo con decisión del usuario. | Consistencia de una cadena no equivale a resolución de identidad. |
| Reidentificación por la tabla de correspondencias | No persistirla en el primer MVP; mantener solo el estado de sesión necesario. | Persistencia cifrada será otra funcionalidad con selección y revisión de criptografía existente. |
| Fugas por logs, informe o nombre de salida | Informe sin texto original, fragmentos, rutas ni nombre original; nombre neutro propuesto; errores con códigos y diagnósticos sanitizados. | Revisar también mensajes de excepciones de terceros y archivos de fallo. |
| Descargas o llamadas de red inesperadas | Cargar únicamente modelos locales, sin descarga automática, recognizers remotos ni telemetría; fallar si falta un recurso requerido. | Verificar con red bloqueada y observación de conexiones; una prueba de ejecución no demuestra ausencia de todos los caminos de red. |
| Pérdida o sustitución del original | Origen de solo lectura; destino nuevo, comprobación de identidad y rechazo de colisiones o alias al original. | Incluir symlinks, hardlinks, permisos, disco lleno y cambios durante el procesamiento. |
| Exportación parcial presentada como válida | Estado de revisión vinculado a la versión; escritura controlada, reapertura y comparación con salida esperada antes de confirmar éxito. | Si no se puede limpiar un archivo parcial, informar de su existencia y no marcarlo verificado. |
| Temporales, swap, copias o carpetas sincronizadas | Minimizar persistencia, temporales restringidos solo cuando sean necesarios, limpieza normal al terminar y destino local elegido conscientemente. | Python y el SO no permiten prometer borrado forense de RAM, SSD, snapshots o backups; la app tampoco controla servicios externos de sincronización. |
| Documento hostil o descompresión descontrolada | Límites de tamaño, tiempo y recursos; no abrir enlaces ni ejecutar macros; estudiar proceso separado antes de incorporar parsers complejos. | Un subprocess no constituye sandbox y no elimina el riesgo de ejecutar código con los permisos del usuario. |

En el MVP no conviene usar la etiqueta global «seguro para compartir». Proponer estados separados: revisión pendiente, comprobaciones técnicas superadas para el alcance declarado, verificación bloqueada y riesgo contextual pendiente de valoración humana.

## Secuencia y criterios propuestos para discutir el diseño

1. **MVP inicial:** un TXT UTF-8 o Markdown leído como fuente textual; salida exclusivamente TXT UTF-8. Español prioritario. Presidio con spaCy local y vocabulario manual. Sustitución por etiquetas consistentes o eliminación del fragmento seleccionado. Revisión con aceptar, rechazar, corregir y añadir hallazgos; previsualización y verificación posterior. Sin lotes ni correspondencias persistentes.
2. **DOCX a TXT:** añadir inventario OOXML y extracción con cobertura explícita. No conservar formato ni marcar estructuras desconocidas como inspeccionadas.
3. **PDF a TXT:** empezar por un subconjunto documentado de PDF textuales; declarar regiones e imágenes no inspeccionadas. Mantener bloqueo de verificación completa ante cobertura desconocida.
4. **Ampliaciones independientes:** OCR local, exportaciones DOCX/PDF, datos ficticios claramente identificados, mapa cifrado, lotes y hojas de cálculo. Cada una necesita alcance y pruebas propios.

Criterios candidatos, pendientes de aprobación y medición:

- Cero modificaciones de los originales en todos los casos del corpus de integración, verificado por bytes y hash en pruebas.
- Cero hallazgos sin decisión y cero conflictos de sustitución sin resolver antes de exportar con comprobaciones superadas.
- Reabrir el TXT exportado y exigir igualdad exacta con el resultado aprobado. Comprobar sustituciones previstas y rastrear por separado cualquier coincidencia residual de valores seleccionados, sin ignorarla silenciosamente.
- Ejecutar un segundo análisis como comprobación adicional; cero detecciones no equivale a ausencia de información sensible. Las detecciones residuales requieren decisión; no se borrarán automáticamente.
- Coherencia de etiquetas en todas las repeticiones del corpus y ningún cambio fuera de los intervalos aprobados, salvo transformaciones explícitas de codificación o saltos de línea.
- Fixtures para acentos, Unicode, controles invisibles, repeticiones, entidades solapadas, falsos positivos y negativos; además errores de lectura, cancelación, modelo ausente, disco lleno y fallo de verificación.
- Separar corpus de desarrollo y corpus congelado de evaluación. Objetivo inicial propuesto: al menos 50 positivos y 50 negativos por identificador estructurado, con 100 % de positivos detectados en ese conjunto; NER con precisión y recall de entidades de al menos 90 % en el conjunto español sintético congelado. Publicar tamaño, definición de coincidencia, denominadores y fallos. Son puertas de desarrollo propuestas, no garantías para producción.
- Medir por separado NER general, vocabulario audiovisual conocido y nombres de producción no incluidos en el diccionario. No presentar el acierto sobre términos suministrados como capacidad de descubrir títulos desconocidos.
- Demostrar el flujo con red bloqueada, sin modelos remotos y con pruebas de errores que no expongan texto en logs o informe. Comprobar manualmente la GUI en macOS Apple Silicon.
- Medir latencia, memoria y empaquetado en el M2 Pro antes de prometer rendimiento o compatibilidad con toda la familia M1 y posteriores. No añadir MPS, MLX ni LLM sin beneficio medido.

Actualización posterior a esta investigación: el usuario eligió provisionalmente la opción A, con GUI y motor modular en el mismo proceso. El alcance final y los contratos propuestos se recogen en la [especificación pendiente de aprobación](superpowers/specs/2026-10-23-local-document-anonymizer-design.md). Después vendrá un plan de implementación separado. Esta investigación no ha ejecutado pruebas de producto ni validado la combinación de dependencias.
