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
