# Evidencia de desarrollo — 24/10/2026

**Resultado: versión experimental; aceptación global NO superada.** La integración funciona, pero el modelo NER pequeño no alcanza los umbrales aprobados. No se han reducido objetivos ni afinado reglas contra este corpus. La interacción visual manual en macOS permanece pendiente.

## Detección real

Corpus sintético congelado antes de evaluar: [manifest y SHA-256](../tests/fixtures/evaluation-v1.manifest.json), [casos y anotaciones](../tests/fixtures/evaluation-v1.json). Contiene 851 casos: 50 positivos y 50 negativos por cada uno de los siete identificadores/contextos estructurados; 100 textos con 100 entidades de cada categoría NER; 50 casos de vocabulario y uno de producción desconocida. Son familias generadas con plantillas y valores repetidos, no una muestra representativa de documentación real.

Motor: Presidio 2.2.364, spaCy 3.8.16, `es_core_news_sm` 3.8.0. [Resultados completos, fingerprint y errores por caso](evaluation-v1-results.json). Coincidencia exacta de intervalo y categoría, sin crédito parcial. Los conjuntos de identificadores puntúan el recognizer de su familia; los conflictos entre categorías siguen siendo candidatos de revisión y no se puntúan como falsos positivos de otra familia.

| Familia | TP | FP | FN | Precisión | Recall | Puerta |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Correo | 50 | 0 | 0 | 100 % | 100 % | Superada en este corpus |
| Teléfono ES | 50 | 0 | 0 | 100 % | 100 % | Superada en este corpus |
| DNI/NIF personal | 50 | 0 | 0 | 100 % | 100 % | Superada en este corpus |
| NIE | 50 | 0 | 0 | 100 % | 100 % | Superada en este corpus |
| IBAN ES | 50 | 0 | 0 | 100 % | 100 % | Superada en este corpus |
| Pasaporte | 50 | 0 | 0 | 100 % | 100 % | Métrica; sin puerta de recall |
| Fecha | 50 | 0 | 0 | 100 % | 100 % | Métrica; sin puerta de recall |
| Persona | 76 | 50 | 24 | 60,32 % | 76 % | NO superada |
| Organización | 21 | 1 | 79 | 95,45 % | 21 % | NO superada |
| Ubicación | 97 | 47 | 3 | 67,36 % | 97 % | NO superada |
| Vocabulario literal | 50 | 0 | 0 | 100 % | 100 % | Superada en este corpus |

Los falsos positivos NER incluyen límites incorrectos y clasificaciones cruzadas. Se publican los intervalos junto al ID del caso para inspeccionar cada error en el corpus. El caso de producción desconocida se informa aparte: los títulos y personajes no suministrados no tienen cobertura automática declarada.

Reproducir desde la raíz:

```sh
PYTHONPATH=src .venv/bin/python tests/evaluate_detection.py
```

El evaluador devuelve **exit code 2** porque fallan puertas de aceptación. Las pruebas unitarias de medición/corpus pueden pasar aunque la calidad de detección no pase; son resultados distintos. Si se usan estos errores para ajustar el detector, este conjunto pasará a desarrollo y habrá que crear otro corpus independiente. Un siguiente experimento razonable es comparar un modelo español mayor en CPU, revisando tamaño, licencia y permiso de descarga antes de instalarlo; no se ha incorporado otro modelo.

## Integridad, privacidad y GUI

La regresión automatizada comprueba límites/UTF-8, preservación de CRLF, acentos y emoji, transformación por intervalos, procedencia, estados, revisión humana, rechazo residual vinculado, cancelación, carreras de publicación, identidad, fallos de disco/limpieza e informe cerrado sin datos originales. Incluye un recorrido de GUI con archivos sintéticos reales: revisión → confirmación → verificación → TXT y comprobación de bytes originales intactos.

`tests/privacy_probe.py` ejecuta un proceso nuevo, carga el modelo y realiza lectura, detección, revisión, segunda pasada y exportación de TXT/informe. Un audit hook de Python rechaza `socket.connect`, `socket.getaddrinfo`, `socket.sendto` y `urllib.Request`; se observaron **0 intentos**. Escanea logs, repr, informe, salida y temporales con un correo centinela. No cambia firewall, configuración de seguridad ni entornos externos. Esto demuestra ausencia de intentos observables en ese recorrido Python; no controla syscalls de código nativo, otros procesos ni todas las entradas posibles.

Los tests Qt usan `offscreen` y dobles para aislar estado, selección y cancelación; no acreditan precisión NLP. Un smoke adicional con backend **Cocoa** abrió una ventana visible de 1260 × 900 en macOS 26.5.2, una pantalla. El primer arranque en sandbox mostró errores de servicios gráficos; se repitió fuera del sandbox con permiso técnico normal. El control de UI no identifica el Python sin bundle en su inventario; por tanto **no se completó la inspección/interacción visual manual** y no se presenta el smoke automático como equivalente.

Para completar esa comprobación manual: abrir la aplicación, cargar un TXT sintético con emoji y CRLF, revisar candidatos, seleccionar una omisión, corregir fragmento/categoría, probar alias y redacción, previsualizar, confirmar, resolver residuales, guardar un TXT nuevo e informe separado y probar cancelar/cerrar durante análisis. Comparar los bytes del original antes/después. No usar material de producción para esta aceptación inicial.

## Rendimiento medido

[Datos y método](runtime-benchmark.json): Python 3.12.14 arm64, macOS 26.5.2. No se verificó el modelo comercial del chip desde el sandbox. Texto sintético continuo sin identificadores; tres análisis calientes por tamaño, CPU, una sesión. No representa el peor caso de documentos densos en entidades.

- Primera inicialización de modelo/imports en un proceso nuevo: **0,742 s**; segunda inicialización: **0,131 s**. No se vaciaron cachés del sistema operativo.
- 20 000 caracteres: **0,384–0,395 s**; 100 000: **1,915–1,967 s**.
- Pico RSS del proceso completo: **602 570 752 bytes** (aprox. 575 MiB).
- Cancelación solicitada a los 0,053 s durante análisis real de 100 000 caracteres: **1,868 s** adicionales hasta terminar/desestimar. Mayor separación entre ticks Qt de 20 ms: **21 ms** en ese recorrido offscreen. No es una promesa de latencia ni validación manual de fluidez.

## Estado de entrega

Código en la rama `codex/text-mvp`; no integrado en `main`. Sin instalador, firma, notarización ni modelos empaquetados. Las dependencias se instalaron solo en la `.venv` autorizada. Pesos GPL-3.0; revisar condiciones antes de redistribuir. El original se conserva; la salida es texto y la segunda pasada puede repetir omisiones del mismo modelo.

Permanecen dos puertas abiertas: calidad NER y smoke visual manual. La revisión final de código se registra junto a los cambios correspondientes; ni una regresión verde ni un informe técnico de exportación certifican anonimato o aceptación del producto.

## Revisión final y correcciones

La revisión independiente de toda la rama identificó dos hallazgos Important, ninguno Critical y ningún Minor; no apartó comportamientos del juicio por estar fuera de la especificación. Ambos se reprodujeron antes de corregir y la regresión final pasó **102 pruebas**:

1. Un `stat` seguido de `unlink` no impide que otro proceso sustituya un temporal justo antes del borrado. La exportación ahora crea directamente el nombre final con `O_CREAT|O_EXCL|O_NOFOLLOW`, permisos 0600, descriptor del directorio fijado y dos reaperturas de comprobación. **No borra automáticamente ninguna ruta.** El nombre es visible durante la escritura y un fallo puede dejar una copia parcial sin verificar. Se comunica la ubicación elegida para inspección, advirtiendo que el archivo/directorio pueden haber cambiado. Los tests reproducen colisión, sustitución, disco lleno, fallo de lectura y cambio del directorio; comprueban que nunca se llama a unlink.
2. El límite de 100 000 caracteres era de entrada y no debía rechazar una salida que creciese con etiquetas. La capacidad de análisis ahora se deriva del máximo de expansión de las etiquetas sobre esa entrada y se aplica también a `spaCy.max_length`. La prueba real transforma 40 000 caracteres en 120 000 y ejecuta la verificación completa sin fallo de análisis. No se trunca ni fragmenta. Este límite derivado no constituye una promesa de rendimiento para salidas extremas.

Se repitió el evaluador tras las correcciones técnicas: mismas métricas y puertas NER fallidas, nuevo fingerprint de configuración. No se cambiaron patrones, modelo ni anotaciones para mejorar la puntuación. Los tiempos del benchmark de prosa corresponden al adaptador anterior a estos fixes, con las mismas operaciones para entradas hasta 100 000 caracteres; no se midió el rendimiento máximo de salidas expandidas.

Además se midió una [tabla densa](runtime-dense-table.json): 3 000 candidatos sobre 12 000 caracteres, **5,537 s** para poblar y procesar eventos, **438 009 856 bytes** de pico RSS, **0,063 s** al cerrar el documento. Es una única prueba offscreen con detector doble, sin NLP: evidencia una ralentización relevante que no cubría la prosa sin entidades. Se recomienda paginar o usar un modelo de tabla antes de ampliar la aceptación a documentos densos; no hay promesa de respuesta inmediata.

## Decisiones de implementación y costes

- Se reutilizó el checkout limpio en una rama de desarrollo: conserva `main`, pero los archivos de trabajo muestran la rama activa.
- Inicialmente se conservaron destinos publicados ante fallo y se intentó limpiar staging por identidad. La revisión mostró que la limpieza seguía expuesta a una carrera; quedó sustituida por la política de cero borrados automáticos descrita arriba. Un fallo puede requerir inspección manual de una copia parcial.
- Los recognizers de Presidio se invocan por separado y PER/ORG/LOC se mapean directamente desde spaCy para conservar conflictos. El coste es mantener esa configuración explícita al actualizar dependencias; el correo usa el snapshot local de dominios y los avisos/timeouts bloquean cobertura.
- Las posiciones Qt cuentan cada CRLF como una unidad UTF-16 y traducen emoji correctamente. Las posiciones imposibles dentro de un par CRLF o surrogate se rechazan; la fuente exacta se conserva.
- La creación exclusiva directa sustituye `staging → hardlink → unlink`: evita la carrera de borrado, a cambio de que el nombre final aparezca durante la escritura y pueda quedar parcial si falla.
- La capacidad de análisis del resultado se dimensiona según la expansión máxima de etiquetas. Mantiene los límites de entrada, a cambio de mayor consumo posible al verificar resultados largos.

No se han diferido hallazgos Minor de esta revisión. Quedan pendientes las puertas de aceptación descritas, además de la limitación de tabla densa medida.

## Continuación: revisión paginada

Se sustituyó la tabla completa por páginas de **100 candidatos** manteniendo todos los hallazgos y decisiones en Session. El contador de pendientes es global; los pendientes de otras páginas impiden previsualizar/exportar. Navegar no modifica la revisión ni revoca su confirmación; editar o corregir un candidato de cualquier página sí lo hace. Los tests cubren correspondencia de filas con coordenadas originales, decisiones presentadas en orden distinto, página final parcial y cambio de documento.

[Benchmark paginado](runtime-dense-table-paged.json), mismo tamaño sintético (12 000 caracteres y 3 000 candidatos), proceso nuevo, sin NLP:

| Medida | Tabla completa anterior | Tabla paginada |
| --- | ---: | ---: |
| Poblar/procesar eventos | 5,537 s | 0,0455 s |
| Pico RSS | 438 009 856 bytes | 123 256 832 bytes |
| Cerrar documento | 0,0625 s | 0,00385 s |

La navegación a la página siguiente tardó 0,0392 s. Son ensayos puntuales, no una promesa de latencia ni sustituto del smoke visual manual. Reproducir la nueva medición con `QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python tests/benchmark_dense_table.py`. El coste de esta decisión es pasar de una lista continua a navegación por páginas; no se ocultan candidatos ni se cambian las puertas de revisión.

## Comparación autorizada con el modelo mediano

Se instaló únicamente para evaluación `es_core_news_md` 3.8.0, **42 284 033 bytes**, sin dependencias nuevas, dentro de la `.venv`. SHA-256 oficial comprobado antes de instalar: `478b8bb3f3e8eb149192f7d80e7cd64f990b7e9bccbc5329df41a57e86326be2`. La [publicación oficial](https://github.com/explosion/spacy-models/releases/tag/es_core_news_md-3.8.0) declara CPU, compatibilidad spaCy 3.8 y GPL-3.0. El registro de artefactos distingue esta autorización adicional del entorno original.

El modelo candidato se eligió antes de preparar o medir el segundo corpus. Se congelaron [100 casos NER adicionales](../tests/fixtures/ner-comparison-v2.json), [hash y protocolo](../tests/fixtures/ner-comparison-v2.manifest.json), con 100 personas, 100 organizaciones y 100 ubicaciones. Las organizaciones mezclan 50 nombres públicos en contextos ficticios y 50 inventados. v1 se usa como referencia de comparación; v2 fue congelado antes de ejecutar ambos modelos. Si estos errores guían nuevos ajustes, ese conjunto pasa a desarrollo y se necesitará otra evaluación independiente.

[Comparación completa y errores exactos](ner-model-comparison.json):

| Categoría en v2 | Pequeño: precisión / recall | Mediano: precisión / recall | TP / FP / FN del mediano |
| --- | --- | --- | --- |
| Persona | 80 % / 96 % | 88,50 % / 100 % | 100 / 13 / 0 |
| Organización | 97,67 % / 42 % | 100 % / 60 % | 60 / 0 / 40 |
| Ubicación | 73,77 % / 90 % | 86,96 % / 100 % | 100 / 15 / 0 |

**El mediano mejora las métricas, pero NO supera las puertas NER de precisión y recall ≥90 % por categoría.** En v1, el recall de organización pasa del 21 % al 38 %, también insuficiente. No se integra como modelo activo ni se declara el producto aceptado. La aplicación conserva `es_core_news_sm`; no se cambia ningún patrón o peso ni se reetiqueta el corpus para mejorar resultados.

Ambos modelos se cargaron desde rutas locales con un audit hook de Python que bloquea conexiones; se observaron 0 intentos de red en esa ejecución. Esto no inspecciona syscalls nativas. El benchmark del comparador mide cargas secuenciales y análisis de textos pequeños; el pico de memoria es del proceso completo, no atribuible de forma aislada a un solo modelo.

Reproducir después de preparar expresamente ambos recursos locales: `PYTHONPATH=src .venv/bin/python tests/compare_ner_models.py`. Devuelve **2** porque el candidato no supera las puertas. Su instalación para evaluación no modifica el lock de dependencias ni la selección de modelo del producto. El siguiente paso de calidad necesita revisar la estrategia de reconocimiento, especialmente ante organizaciones inventadas; un modelo mayor por sí solo no ha resuelto el requisito.

## Revisión y smoke de la continuación

Una revisión independiente del incremento `f402a07..85c3343` no encontró hallazgos Critical ni Important. Reprodujo 112 pruebas correctas y contrastó en memoria las métricas y errores guardados de los dos modelos y corpus. Encontró una limitación metodológica **Minor**, diferida para conservar la congelación del corpus: en v2 el tipo de organización (pública/inventada) y la plantilla de frase están correlacionados por construcción (`i % 2` frente a `i % 10`). Las métricas agregadas y el veredicto fallido se mantienen, pero no permiten atribuir diferencias entre grupos solo al nombre. Un futuro corpus independiente deberá cruzar ambos tipos de organización con las mismas plantillas; v2 se conserva intacto.

El smoke visual ha avanzado mediante un lanzador `.app` temporal creado solo en `/tmp`, sin instalar ni empaquetar el producto. En la ventana Cocoa real se observó apertura de un TXT sintético, análisis local, selección de «Ana» después de un emoji y selección/añadido manual de «Nube Zafiro» como candidato. El original sintético conservó sus 74 bytes, incluidos CRLF. Se cerró la ventana de prueba. La herramienta de control no accionó de forma fiable los desplegables incrustados en la tabla; no se atribuye ese límite al producto ni se declara completado el recorrido manual de decisiones, vista previa, residuales y exportación. Las pruebas Qt automatizadas cubren ese flujo por separado, incluyendo eventos de ratón/teclado en un desplegable.

Los límites que la revisión dejó fuera de su juicio se conservan explícitos: eficacia con documentación real no evaluada (solo escenarios sintéticos), red nativa no auditada por los hooks Python y código anterior a la base cubierto por la revisión/regresión previa, sin una nueva auditoría de todo su historial. No se modificaron configuraciones de seguridad ni se usaron documentos de producción para ampliar esas afirmaciones.

## Propuesta de ajuste posterior

Aumentar de pequeño a mediano mejora NER pero no alcanza el objetivo, por lo que repetir únicamente aumentos de tamaño no tiene evidencia suficiente. Un experimento siguiente podría comparar un detector guiado por etiquetas, manteniendo el mismo contrato de candidatos y los identificadores de Presidio. [GLiNER](https://github.com/urchade/GLiNER) y el [modelo multilingüe gliner_multi-v2.1](https://huggingface.co/urchade/gliner_multi-v2.1) son candidatos de investigación: declaran Apache-2.0 y permiten elegir tipos de entidad, pero su eficacia en este proyecto sigue sin demostrarse. El [artefacto safetensors publicado](https://huggingface.co/urchade/gliner_multi-v2.1/tree/main) ocupa aproximadamente **1,16 GB**, además de las dependencias y recursos de tokenización que habría que resolver y revisar.

Esta propuesta queda **fuera de las descargas autorizadas** y no añade un modelo, framework ni instalación a la aplicación. Antes de ejecutarla haría falta fijar revisión, archivos/hashes, dependencias compatibles con Python 3.12 arm64, presupuesto total de disco/red y pruebas offline/CPU, y obtener una autorización específica. Se congelaría otro corpus con plantillas cruzadas antes de medir; si falla, se publican los errores manteniendo los umbrales. El marcado manual y el vocabulario de sesión continúan disponibles, pero no sustituyen la puerta de calidad automática.
