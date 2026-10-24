# Local Document Anonymizer

Aplicación local para revisar información sensible en español y exportar una copia TXT. **Versión experimental: las puertas de calidad NER no se superan; pendiente de aceptación completa.** No certifica anonimato: la revisión humana y el riesgo contextual siguen siendo necesarios.

Admite un TXT/Markdown UTF-8 por sesión, hasta 1 MiB y 100 000 caracteres. Conserva el original y los saltos de línea; no renderiza Markdown ni abre recursos enlazados. PDF, DOCX, OCR, lotes y exportación con maquetación quedan fuera de esta versión.

## Entorno de desarrollo

Se usa Python 3.12 arm64 en macOS. La preparación requiere acceso a Internet y permiso para descargar; el análisis posterior carga únicamente recursos locales. No hay descarga automática de modelos.

```sh
python3.12 -m venv .venv
uv pip sync --python .venv/bin/python --require-hashes --only-binary :all: requirements.lock
```

El modelo aprobado es `es_core_news_sm` 3.8.0, del [repositorio oficial de spaCy](https://github.com/explosion/spacy-models/releases/tag/es_core_news_sm-3.8.0). Descargar el wheel oficial, verificar SHA-256 `e451a83d6df79b87e9eed0cb553f03e99e36a3bab18a7b79f0dcfd1fdf875e12` y solo entonces instalarlo con `uv pip install --python .venv/bin/python --no-deps --no-index RUTA_AL_WHEEL`. No usar documentos de producción para comprobar la instalación.

El [registro de artefactos](docs/dependency-artifacts.json) recoge procedencias, versiones y hashes; `requirements.lock` fija las dependencias con hashes. El límite superior conservador de descargas autorizadas fue 164 531 549 bytes, incluido el modelo de 12 884 212 bytes; no es una medición de tráfico real. El entorno de desarrollo fue instalado y el checksum del modelo comprobado. Python, uv y sus instalaciones previas no forman parte de ese cálculo.

## Detección y límites

Presidio aporta recognizers configurados explícitamente para correo, teléfonos ES, DNI/NIF personal, NIE, pasaporte, IBAN ES y fechas. spaCy aporta PER, ORG y LOC. Los candidatos conflictivos se conservan para revisión. Las direcciones completas, proyectos, personajes y códigos se marcan manualmente o mediante vocabulario literal de sesión; ese vocabulario distingue mayúsculas y respeta límites Unicode en extremos de palabra. No acepta regex. Puede haber falsos positivos y falsos negativos.

El correo usa la lista de dominios incluida en `tldextract`, sin caché ni actualizaciones de red. El modelo se carga por ruta local; si falta o falla un detector, el análisis se bloquea. No hay telemetría ni persistencia de documentos o diccionarios en la aplicación.

## Uso de la versión de desarrollo

```sh
PYTHONPATH=src .venv/bin/python -m local_anonymizer
```

1. Abre un TXT/Markdown. El análisis se ejecuta en un único worker y el original permanece intacto.
2. Revisa toda la fuente y todas las páginas de candidatos (100 por página), decide cada uno (`Sustituir` o `Conservar`) y resuelve solapamientos. El contador muestra pendientes de toda la sesión; cambiar de página conserva decisiones y confirmación. Puedes corregir categoría o fragmento, seleccionar omisiones y añadir vocabulario literal. Reanalizar reinicia las decisiones.
3. Elige etiqueta o redacción. El grupo opcional permite compartir una etiqueta entre alias de la misma categoría; por defecto se agrupan valores idénticos. No uses el mismo grupo para personas distintas.
4. Construye la vista previa, comprueba todo el resultado, marca la revisión humana y confirma. Cualquier cambio obliga a reconstruir y confirmar.
5. Revisa los residuales. Localízalos en el original para corregirlo o rechaza explícitamente falsos positivos de esa salida. Un valor seleccionado que persista siempre bloquea la exportación.
6. Guarda un TXT nuevo. El destino no puede existir: también se bloquean enlaces y colisiones concurrentes. Después puedes guardar un informe JSON independiente y opcional.

Cancelar descarta resultados pero espera a que termine la llamada del motor; no mata hilos. El cierre también espera al trabajo activo. El nombre del destino aparece al comenzar la escritura. Solo se anuncia éxito tras reabrir y comprobar la copia. Si la operación falla, puede quedar un archivo parcial sin verificar: se comunica la ubicación elegida y no se borra nada automáticamente, porque otro proceso podría haber sustituido el archivo o su directorio. La aplicación no garantiza borrado físico en SSD, memoria, snapshots o copias sincronizadas.

## Pruebas

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Se usan archivos y textos sintéticos. Las pruebas del núcleo validan transformación, estado, procedencia y publicación exclusiva; no demuestran eficacia del modelo. La [evaluación y evidencia](docs/validacion-2026-10-24.md) separa métricas reales, pruebas Qt y smoke Cocoa. Los cinco identificadores exigidos pasan el corpus sintético; NER no alcanza los umbrales de persona/organización/ubicación. La comprobación visual manual sigue pendiente. El comando `PYTHONPATH=src .venv/bin/python tests/evaluate_detection.py` devuelve 2 por esas puertas fallidas; una regresión unitaria verde no las sustituye. No se ha afinado el detector contra ese corpus. La tabla mantiene solo 100 filas visibles: en el ensayo de 3 000 candidatos, la primera página tardó 0,045 s frente a los 5,54 s de la tabla completa anterior. Es una medición offscreen, no una garantía de respuesta ni validación visual manual.

## Licencias y distribución

Presidio y spaCy declaran MIT; PySide6/Qt permite opciones LGPL/GPL/comerciales según componente. Los pesos españoles `es_core_news_sm` 3.8.0 declaran **GPL-3.0**. No se incluyen pesos ni paquetes binarios en Git. Sus licencias y las transitivas requieren revisión antes de redistribuir un instalador. Este proyecto no incluye instalador, firma ni notarización.

La [especificación](docs/superpowers/specs/2026-10-23-local-document-anonymizer-design.md) y el [plan](docs/superpowers/plans/2026-10-24-local-document-anonymizer.md) separan requisitos aprobados, implementación y aceptación. `graphify-out/` es una instantánea documental histórica, anterior al código actual.

## Experimento NER adicional

Se comparó `es_core_news_md` 3.8.0 con el pequeño mediante una descarga autorizada aparte (42,3 MB, GPL-3.0, checksum verificado). Mejora resultados, pero en el segundo corpus el recall de organizaciones alcanza solo el 60 %, con precisión de persona/ubicación también por debajo del 90 %. Sigue siendo un recurso de evaluación: **el modelo activo continúa siendo el pequeño y la aceptación global está pendiente**. Véanse [protocolo y resultados](docs/validacion-2026-10-24.md). El comparador `tests/compare_ner_models.py` no descarga recursos ni cambia el modelo de la aplicación.
