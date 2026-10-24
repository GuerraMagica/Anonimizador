# Local Document Anonymizer

Aplicación local para revisar información sensible en español y exportar una copia TXT. **Versión de desarrollo; pendiente de aceptación completa.** No certifica anonimato: la revisión humana y el riesgo contextual siguen siendo necesarios.

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

## Pruebas

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Se usan archivos y textos sintéticos. Las pruebas del núcleo validan transformación, estado, procedencia y publicación exclusiva; no demuestran eficacia del modelo. La evaluación independiente de detección y la comprobación de GUI se documentarán por separado antes de declarar aceptación.

## Licencias y distribución

Presidio y spaCy declaran MIT; PySide6/Qt permite opciones LGPL/GPL/comerciales según componente. Los pesos españoles `es_core_news_sm` 3.8.0 declaran **GPL-3.0**. No se incluyen pesos ni paquetes binarios en Git. Sus licencias y las transitivas requieren revisión antes de redistribuir un instalador. Este proyecto no incluye instalador, firma ni notarización.

La [especificación](docs/superpowers/specs/2026-10-23-local-document-anonymizer-design.md) y el [plan](docs/superpowers/plans/2026-10-24-local-document-anonymizer.md) separan requisitos aprobados, implementación y aceptación. `graphify-out/` es una instantánea documental histórica, anterior al código actual.
