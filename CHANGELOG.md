# Cambios

## 0.1.0.dev0 — 2026-10-24

Versión experimental de TXT/Markdown UTF-8 a TXT nuevo, con entrada acotada, candidatos de Presidio/spaCy, vocabulario literal, selección y corrección manual, grupos/acciones, previsualización, confirmación humana, rondas residuales y publicación exclusiva. Informe JSON opcional independiente, sin texto ni rutas originales. Un worker Qt con cancelación cooperativa y resultados vinculados a sesión/revisión.

Dependencias fijadas con hashes y modelo español local autorizado; sin descargas en tiempo de análisis. Pruebas sintéticas de integridad, privacidad, estados y GUI. [Evaluación y límites](docs/validacion-2026-10-24.md): identificadores superan el corpus; NER no alcanza los objetivos. Aceptación global y smoke visual manual pendientes. No incluye PDF, DOCX, OCR, instalador ni garantía de anonimato.

Correcciones de revisión: publicación mediante creación final exclusiva sin ningún borrado automático (los fallos pueden dejar copias parciales informadas); capacidad de verificación derivada para salidas que crecen con etiquetas. Regresión final: 102 pruebas.
