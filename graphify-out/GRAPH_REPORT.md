# Graph Report - Anonimizador  (2026-10-24)

## Corpus Check
- Corpus is ~6,410 words - fits in a single context window. You may not need a graph.

## Summary
- 40 nodes · 54 edges · 6 communities (5 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: unavailable — the agent tool did not expose measured usage; zero counters in local sidecars are placeholders, not a zero-cost claim.

## Graph Freshness
- Built from commit: `74fe844e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Alternativas y cobertura documental
- Revisión, transformación y verificación
- Alcance, decisiones y versionado
- Interfaz y posiciones Unicode
- Privacidad y aceptación
- Detección local de entidades

## God Nodes (most connected - your core abstractions)
1. `Investigación documental de alternativas` - 10 edges
2. `Exportación y verificación: responsabilidad lógica propuesta` - 7 edges
3. `Detección: responsabilidad lógica propuesta` - 6 edges
4. `Revisión y transformación: responsabilidad lógica propuesta` - 5 edges
5. `Cobertura documental explícita` - 4 edges
6. `Aplicación y GUI: responsabilidad lógica propuesta` - 4 edges
7. `Criterios de aceptación propuestos` - 4 edges
8. `PySide6 y Qt Widgets` - 3 edges
9. `Especificación propuesta del primer MVP` - 3 edges
10. `Local Document Anonymizer: MVP propuesto` - 3 edges

## Surprising Connections (you probably didn't know these)
- `Especificación propuesta del primer MVP` --references--> `Investigación documental de alternativas`  [EXTRACTED]
  docs/superpowers/specs/2026-10-23-local-document-anonymizer-design.md → docs/investigacion-2026-10-23.md
- `Detección: responsabilidad lógica propuesta` --references--> `Presidio`  [EXTRACTED]
  docs/superpowers/specs/2026-10-23-local-document-anonymizer-design.md → docs/investigacion-2026-10-23.md
- `Detección: responsabilidad lógica propuesta` --references--> `spaCy y es_core_news_sm`  [EXTRACTED]
  docs/superpowers/specs/2026-10-23-local-document-anonymizer-design.md → docs/investigacion-2026-10-23.md
- `Opción A: GUI y motor modular en un proceso` --references--> `PySide6 y Qt Widgets`  [EXTRACTED]
  docs/superpowers/specs/2026-10-23-local-document-anonymizer-design.md → docs/investigacion-2026-10-23.md
- `Evolución posterior DOCX, PDF y OCR` --conceptually_related_to--> `Cobertura documental explícita`  [EXTRACTED]
  docs/superpowers/specs/2026-10-23-local-document-anonymizer-design.md → docs/investigacion-2026-10-23.md

## Hyperedges (group relationships)
- **Seis responsabilidades propuestas, sin imponer archivos ni clases** — docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_dominio, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_entrada, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_deteccion, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_revision_transformacion, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_exportacion, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_gui [EXTRACTED 1.00]
- **Flujo propuesto de revisión, reconstrucción y comprobación** — docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_texto_inmutable, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_revision_humana, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_revision_transformacion, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_rondas_residuales, docs_superpowers_specs_2026_10_23_local_document_anonymizer_design_publicacion_exclusiva [EXTRACTED 1.00]

## Communities (6 total, 1 thin omitted)

### Community 0 - "Alternativas y cobertura documental"
Cohesion: 0.32
Nodes (7): Dangerzone, GLiNER multi-v2.1, Investigación documental de alternativas, PyMuPDF, pypdf, python-docx, Tkinter

### Community 1 - "Revisión, transformación y verificación"
Cohesion: 0.36
Nodes (3): Dominio: responsabilidad lógica propuesta, Exportación y verificación: responsabilidad lógica propuesta, Revisión y transformación: responsabilidad lógica propuesta

### Community 2 - "Alcance, decisiones y versionado"
Cohesion: 0.29
Nodes (3): Especificación propuesta del primer MVP, Evolución posterior DOCX, PDF y OCR, Local Document Anonymizer: MVP propuesto

### Community 3 - "Interfaz y posiciones Unicode"
Cohesion: 0.33
Nodes (3): PySide6 y Qt Widgets, Entrada: responsabilidad lógica propuesta, Aplicación y GUI: responsabilidad lógica propuesta

### Community 5 - "Detección local de entidades"
Cohesion: 0.50
Nodes (4): Presidio, spaCy y es_core_news_sm, Categorías de detección y confidencialidad propuestas, Detección: responsabilidad lógica propuesta

## Knowledge Gaps
- **4 isolated node(s):** `GLiNER multi-v2.1`, `Tkinter`, `Dangerzone`, `Categorías de detección y confidencialidad propuestas`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 9 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Investigación documental de alternativas` connect `Alternativas y cobertura documental` to `Alcance, decisiones y versionado`, `Interfaz y posiciones Unicode`, `Detección local de entidades`?**
  _High betweenness centrality (0.473) - this node is a cross-community bridge._
- **What connects `GLiNER multi-v2.1`, `Tkinter`, `Dangerzone` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Why does `Detección: responsabilidad lógica propuesta` connect `Detección local de entidades` to `Revisión, transformación y verificación`, `Privacidad y aceptación`?**
  _High betweenness centrality (0.311) - this node is a cross-community bridge._
- **Why does `Exportación y verificación: responsabilidad lógica propuesta` connect `Revisión, transformación y verificación` to `Privacidad y aceptación`, `Detección local de entidades`?**
  _High betweenness centrality (0.267) - this node is a cross-community bridge._
## Scope and reproducibility

- Documentation-only graph of a proposed application, not evidence of implemented or tested product behavior.
- Built from the two documentation files at commit `74fe844efa5b982e8954d04a5972e42dd3c7bbdb`. Later design changes must be compared with this snapshot.
- The phase-3 review on 24/10/2026 was written after this extraction. Its added section and revised plan-approval wording are not included in these nodes; this graph is a historical snapshot, not a live index.
- Semantic extraction used a Codex session agent; no Gemini API, model download or package installation was used for this build.
- The default HTML viewer loads vis-network JavaScript from unpkg.com. It needs that network resource; graph.json and this report can be consulted locally without it.
- `graphify-out/` is in the working tree. Only reviewed, portable outputs are versioned; machine paths and caches are ignored.
- Source-file SHA-256 values:
  - `docs/investigacion-2026-10-23.md`: `b1a833243002065e1c0bfc5439e817a2aad9a01e17caa100cb059788d54e523c`
  - `docs/superpowers/specs/2026-10-23-local-document-anonymizer-design.md`: `f52610c10b75ac8d86854c86ab8ed815dd016373468d1d5e1b9f210f4812ce56`

### Numeric cohesion by community

- Alternativas y cobertura documental: 0.32142857142857145
- Revisión, transformación y verificación: 0.35714285714285715
- Alcance, decisiones y versionado: 0.2857142857142857
- Interfaz y posiciones Unicode: 0.3333333333333333
- Privacidad y aceptación: 0.3333333333333333
- Detección local de entidades: 0.5

## Benchmark limitations

The default CLI used an estimated 2,000-word corpus. Recalculation with the detected 6,410 words gives about 8546 corpus tokens and 3322 query tokens. Only one of five generic English questions matched. These are text-size approximations, not measured model usage or evidence of workflow savings. See benchmark.json.
