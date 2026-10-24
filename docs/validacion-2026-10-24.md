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
