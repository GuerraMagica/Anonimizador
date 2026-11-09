# Graph Report - Anonimizador  (2026-11-09)

## Corpus Check
- 64 archivos versionados: 58 archivos Python y 6 archivos JSON de casos y manifiestos sintéticos.

## Summary
- 769 nodes · 2528 edges · 24 communities (17 shown, 7 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 312 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23

## God Nodes (most connected - your core abstractions)
1. `AnonymizerError` - 153 edges
2. `MainWindow` - 58 edges
3. `MainWindow` - 53 edges
4. `finding()` - 51 edges
5. `Session` - 45 edges
6. `reviewed()` - 45 edges
7. `Decision` - 43 edges
8. `build_preview()` - 40 edges
9. `guarded()` - 36 edges
10. `Finding` - 32 edges

## Surprising Connections (you probably didn't know these)
- `DesktopTests` --uses--> `MainWindow`  [INFERRED]
  tests/test_desktop.py → src/local_anonymizer/desktop.py
- `DetectorTests` --uses--> `AnonymizerError`  [INFERRED]
  tests/test_detectors.py → src/local_anonymizer/domain.py
- `LiteralTests` --uses--> `AnonymizerError`  [INFERRED]
  tests/test_detectors.py → src/local_anonymizer/domain.py
- `DomainTests` --uses--> `AnonymizerError`  [INFERRED]
  tests/test_domain.py → src/local_anonymizer/domain.py
- `AnalysisTests` --uses--> `AnonymizerError`  [INFERRED]
  tests/test_enhanced_ner.py → src/local_anonymizer/domain.py

## Import Cycles
- None detected.

## Communities (24 total, 7 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (12): Batch, BatchEntry, MainWindow, AnonymizerError, Category, guarded(), invoke(), MainWindow (+4 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (28): Action, Decision, Disposition, Finding, Preview, ResidualCandidate, ResidualDecision, ResidualKey (+20 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (30): _check(), _libraries(), load_source(), _ocr_pages(), _ocr_pages_impl(), ocr_pdf(), ocr_raster_details(), ocr_rasters() (+22 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (14): default_model_path(), LocalDetector, _PrivateRecognizerLogs, Confidentiality, EnhancedDetector, text_windows(), DetectorTests, AnalysisTests (+6 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (12): operation(), _TaskThread, literal_findings(), ConfiguredDetector, python_to_qt(), qt_to_python(), LiteralTests, BaseGuiCase (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (9): _check_cancelled(), convert_docx(), _convert_docx(), _find_engine(), _terminate(), _validate(), _xml_parts(), OfficeTests (+1 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (5): JobToken, Session, document(), EmptyDetector, SessionTests

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (9): Receipt, _publish_bytes(), publish_text(), build_report(), save_report(), _validate(), save_then_wait(), ExportTests (+1 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (6): EmptyDetector, measure(), compare(), read_frozen_ner_corpus(), score_ner(), ComparisonTests

### Community 10 - "Community 10"
Cohesion: 0.19
Nodes (9): build_visual_preview(), _digest(), publish_layout(), verify_visual(), check_cancelled(), EmptyDetector, RasterTests, VisualGateTests (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (3): load_document(), DomainTests, IngestTests

### Community 12 - "Community 12"
Cohesion: 0.16
Nodes (4): Document, evaluate(), evaluate_sets(), AcceptanceMeasurementTests

### Community 13 - "Community 13"
Cohesion: 0.19
Nodes (4): LoadedSource, RasterPage, DesktopTests, slow()

### Community 14 - "Community 14"
Cohesion: 0.17
Nodes (4): LinkTarget, resolve_resource(), SafeMarkdownBrowser, MarkdownTests

### Community 15 - "Community 15"
Cohesion: 0.25
Nodes (4): FileIdentity, _check_file(), _identity(), _matches()

### Community 17 - "Community 17"
Cohesion: 0.14
Nodes (3): main(), _Page, VisualRegion

### Community 20 - "Community 20"
Cohesion: 0.43
Nodes (4): result(), VisualVerification, TextBox, SourceContractTests

## Knowledge Gaps
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AnonymizerError` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 11`, `Community 12`, `Community 13`, `Community 14`, `Community 15`, `Community 17`, `Community 20`?**
  _High betweenness centrality (0.441) - this node is a cross-community bridge._
- **Are the 41 inferred relationships involving `AnonymizerError` (e.g. with `Batch` and `BatchEntry`) actually correct?**
  _`AnonymizerError` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.055385660890248045 - nodes in this community are weakly interconnected._
- **Why does `MainWindow` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 13`, `Community 14`, `Community 17`, `Community 18`, `Community 23`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `MainWindow` (e.g. with `Batch` and `BatchEntry`) actually correct?**
  _`MainWindow` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07199625993454885 - nodes in this community are weakly interconnected._
- **Why does `MainWindow` connect `Community 0` to `Community 1`, `Community 3`, `Community 4`, `Community 6`, `Community 9`, `Community 17`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
## Cobertura y reproducción

- Revisión de entrada `acdfdb1c4a23948d95f3debd2ec5453c03e52114`, en la rama `codex/next-version`.
- Extracción estructural de `src/`, `scripts/` y `tests/` con Graphify 0.9.92 y la red bloqueada. Se conservaron los nombres de comunidad generados por la herramienta.
- El diagnóstico encontró 2 autorrelaciones y ningún extremo ausente ni relación exactamente duplicada. Las relaciones inferidas orientan la navegación y se contrastan con el código.
- El visor HTML carga `vis-network` desde un CDN. El informe y las consultas de Graphify se pueden usar sin red.
- Para reproducir la instantánea, exportar esos tres directorios desde la revisión indicada y ejecutar `graphify extract <directorio> --code-only` y `graphify cluster-only <directorio> --no-label`.
