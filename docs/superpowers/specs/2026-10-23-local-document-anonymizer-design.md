# Local Document Anonymizer — especificación del primer MVP

Fecha inicial: 23 de octubre de 2026. Última revisión: 24 de octubre de 2026. Estado: **propuesta para revisión; implementación no autorizada**.

## 1. Objetivo y decisiones

Ayudar a un profesional audiovisual a revisar información personal, empresarial y narrativa confidencial antes de decidir si comparte una copia del texto con terceros. La aplicación procesa localmente, conserva el original y permite comprobar las sustituciones realizadas. No certifica anonimato ni decide que un documento sea seguro para compartir.

Decisiones expresas del usuario:

- macOS Apple Silicon; preferencia por Python y herramientas abiertas, locales y sencillas.
- La primera versión puede cambiar la maquetación y exportar texto saneado.
- **Opción A elegida de momento:** interfaz y motor en el mismo proceso, con módulos separados.
- Trabajar por etapas: aprobar especificación y preparar plan antes de implementar. La autorización posterior del usuario preaprueba el plan que se considere adecuado; no se repetirá esa aprobación si el plan respeta el alcance aprobado.

El alcance reducido, los límites, las métricas y los detalles siguientes son propuestas del autor de esta especificación. La elección de A no se interpreta como aprobación de todos ellos.

La [investigación previa](../../investigacion-2026-10-23.md) recoge fuentes, alternativas, licencias y límites documentados. No se han instalado ni probado las herramientas. Las versiones y dependencias definitivas deberán verificarse y fijarse antes de su instalación autorizada.

## 2. Alternativas consideradas

| Arquitectura | Ventaja | Coste y riesgo | Decisión |
| --- | --- | --- | --- |
| A. PySide6 y motor modular en un proceso | Menos piezas, sin protocolo entre procesos; facilita comenzar con texto. | Una caída nativa del motor puede cerrar la aplicación; un trabajo no interrumpible retrasa la cancelación. | Elegida provisionalmente por el usuario. |
| B. PySide6 y worker Python en otro proceso | Mejora gestión de cancelación y contención de ciertas caídas. | Añade comunicación, ciclo de vida y pruebas; no equivale a sandbox. | Reservada para reevaluación antes de incorporar parsers complejos. |

Se propone PySide6 con Qt Widgets, Presidio y un modelo español pequeño de spaCy en CPU. Son elecciones técnicas propuestas, no componentes ya validados. No se necesita un servidor HTTP, navegador integrado, base de datos, Docker ni LLM.

## 3. Alcance de la entrega

### Incluido

- Una sesión y un archivo cada vez: `.txt`, `.md` o `.markdown`, codificado en UTF-8, con BOM inicial opcional.
- Markdown tratado como fuente textual completa: incluir comentarios, front matter, enlaces, HTML y bloques de código sin renderizarlos ni ejecutar contenido o cargar recursos.
- Español como único idioma de detección soportado inicialmente. Correos e identificadores estructurados pueden aparecer en cualquier texto, pero no se afirmará cobertura NER de otros idiomas.
- Lectura, detección, revisión, selección manual de fragmentos, previsualización y exportación de un **TXT nuevo**.
- Dos acciones por hallazgo: etiqueta consistente, como `PERSONA_001`, o redacción mediante el marcador visible `[ELIMINADO]`, sin conservar el fragmento seleccionado en la copia. Si el propio marcador contiene alguno de los valores seleccionados para retirar, la redacción suprime el fragmento sin marcador; la vista previa muestra esa decisión y exige confirmación.
- Informe técnico opcional en JSON, guardado por una acción separada del usuario y sin valores sensibles originales.

### Fuera de esta entrega

PDF, DOCX, OCR, imágenes, lotes, XLSX/CSV, exportar al formato original, nombres ficticios, persistencia de sesiones, restauración de originales y archivos de correspondencias. Tampoco reconocimiento automático fiable de personajes o títulos desconocidos ni mitigación completa de documentos maliciosos.

La correspondencia necesaria para las etiquetas existe solo en RAM durante la sesión. No se guardan preferencias con términos sensibles, historial de documentos ni diccionarios personalizados entre sesiones. La limpieza de referencias de Python no garantiza borrado físico de memoria.

### Límites iniciales propuestos

- Un máximo de 1 MiB de entrada y 100 000 caracteres Unicode; comprobar ambos, con lectura acotada. No truncar para seguir procesando.
- Rechazar codificación inválida, contenido con NUL, firmas identificables de formatos no soportados y controles C0/C1 salvo TAB, CR y LF. Los marcadores de dirección bidireccional y separadores invisibles U+200B, U+2060 y BOM interior bloquearán esta versión con un diagnóstico de contenido no soportado; no se eliminarán silenciosamente.
- No normalizar el contenido ni sus saltos de línea. Solo se retira del texto de trabajo un BOM inicial de transporte, si existe. UTF-8 de salida sin BOM.
- No dividir documentos en fragmentos para el modelo en esta entrega. Si el motor no puede procesar todo el texto admitido, bloquear el análisis completo.

Estos límites permiten probar el recorrido completo antes de ampliar cobertura. La extensión por sí sola no acredita que el contenido sea texto compatible.

## 4. Organización del software

Un paquete Python con seis responsabilidades, sin framework adicional de plugins:

| Módulo lógico | Responsabilidad | Dependencias permitidas |
| --- | --- | --- |
| Dominio | Documento de sesión, hallazgos, decisiones, grupos de identidad, estado y cobertura. | Biblioteca estándar; sin Qt, Presidio ni acceso a disco. |
| Entrada | Leer con límites, validar contenido, capturar identidad del original y producir texto inmutable. | Biblioteca estándar. |
| Detección | Adaptar Presidio/spaCy y términos literales; devolver candidatos con posiciones y procedencia. | Dominio y herramientas locales seleccionadas. |
| Revisión y transformación | Validar decisiones y solapamientos, asignar etiquetas y construir el resultado esperado. | Dominio; sin GUI ni escritura de archivos. |
| Exportación y verificación | Escribir un archivo nuevo, comprobarlo, publicar el resultado y generar el informe. | Dominio, transformación y detector mediante interfaces acotadas. |
| Aplicación y GUI | Coordinar trabajos, mostrar texto y hallazgos, recibir decisiones y controlar el estado. | Módulos anteriores y PySide6. |

No se exige un archivo por responsabilidad ni una jerarquía de clases. Usar funciones y estructuras tipadas sencillas; el plan decidirá nombres concretos y distribución de archivos.

La GUI se ejecuta en el hilo principal y el trabajo costoso en un único worker mediante mecanismos de Qt. Solo habrá un trabajo activo, con identificador de sesión y revisión para descartar resultados tardíos. El worker no modifica widgets y el motor NLP no se comparte concurrentemente. Todo contenido procedente del documento, términos o rutas se muestra como texto plano, sin interpretación HTML, Markdown o rich text automática de Qt.

Cancelar impide aplicar resultados pendientes y se atiende entre etapas; no se matan hilos. Mientras una llamada de terceros no termine, la interfaz indica cancelación pendiente y no permite iniciar otro trabajo. Al cerrar en esas condiciones se pide esperar al cierre controlado del trabajo; no se promete cancelación inmediata ni tiempo máximo hasta medirlo.

## 5. Contrato de datos y detección

El texto de trabajo es inmutable y tiene un identificador interno de revisión. Un hallazgo contiene: ID de sesión, inicio inclusivo y fin exclusivo, categoría, clase de confidencialidad, detector y regla de origen, puntuación original opcional, decisión y acción elegida. Las posiciones se expresan en caracteres Unicode de Python.

La interfaz traduce esas posiciones al sistema UTF-16 de Qt. Se probarán acentos, caracteres combinados y emoji fuera del plano básico para evitar seleccionar o sustituir caracteres equivocados. La puntuación se muestra, si resulta útil, como valor del detector; no como probabilidad de que el documento sea seguro.

Categorías iniciales:

| Grupo | Categorías | Alcance |
| --- | --- | --- |
| PII estructurada | Correo, teléfono español, DNI/NIF personal español, NIE, pasaporte español e IBAN español. | Reutilizar recognizers existentes con configuración explícita para español/España y sus validaciones. El correo no tiene restricción geográfica. Pasaportes y casos ambiguos siguen siendo candidatos para revisar. Teléfonos e IBAN de otros países quedan fuera del soporte automático de esta entrega; se pueden marcar manualmente. |
| NER general | Persona, organización y ubicación. | Modelo español local; exponer ORG mediante el adaptador si Presidio no la proporciona. No atribuir esa cobertura a la configuración predeterminada sin probarla. |
| Contexto sensible | Fecha y dirección física. | Fechas propuestas por reglas existentes; dirección como categoría manual. No se promete detectar automáticamente direcciones completas en esta entrega. |
| Confidencialidad audiovisual y empresarial | Proyecto, personaje, código interno y término confidencial. | Términos definidos durante la sesión y selección manual. No inferir estas clases a partir de MISC de spaCy. |

Cada categoría tiene un prefijo estable: `PERSONA`, `ORGANIZACION`, `UBICACION`, `CORREO`, `TELEFONO`, `DOCUMENTO`, `IBAN`, `FECHA`, `DIRECCION`, `PROYECTO`, `PERSONAJE`, `CODIGO` o `CONFIDENCIAL`. El usuario puede corregir la categoría. Una organización puede tener clase empresarial o PII según lo revisado; el motor no decide su condición jurídica.

Los términos personalizados serán literales y sensibles a mayúsculas por defecto. El usuario podrá añadir variantes explícitas, ver sus coincidencias y revisar límites de palabra. No se admitirán regex arbitrarias ni equivalencias fonéticas en este MVP. Una entrada vacía se rechaza.

No se descartarán conflictos de confidencialidad por elegir silenciosamente el detector con mayor puntuación. Los duplicados de igual intervalo y categoría pueden agruparse conservando todas las procedencias. Los solapamientos restantes se muestran para resolverlos; no se aplican sustituciones superpuestas.

Las etiquetas se asignan determinísticamente por orden de primera aparición aceptada, dentro de cada categoría y sesión. Se saltan identificadores ya presentes literalmente en la fuente para no confundir texto original con etiquetas nuevas. Un grupo explícito de identidad conserva una etiqueta. Las cadenas idénticas de igual categoría se proponen como el mismo grupo, con posibilidad de separarlas; nombres diferentes solo se unen como alias mediante decisión del usuario. No se asume que dos personas con el mismo nombre sean la misma persona.

## 6. Revisión y estados

Flujo propuesto:

1. Seleccionar archivo y validar la entrada.
2. Analizar el texto completo con recursos locales.
3. Mostrar fuente de solo lectura y hallazgos pendientes.
4. Aceptar o rechazar cada hallazgo; corregir intervalo, categoría, grupo y acción; añadir selecciones manuales.
5. Resolver solapamientos y revisar coincidencias repetidas. Una operación en grupo requiere acción explícita, no aplica decisiones automáticamente por mostrar un término idéntico.
6. Generar vista previa de solo lectura y confirmar que se ha revisado el texto completo, incluido el riesgo contextual.
7. Elegir destino nuevo y ejecutar exportación y comprobaciones posteriores.
8. Mostrar resultado y, opcionalmente, guardar el informe.

No se ofrece edición libre del original ni del TXT previsualizado en el MVP. Las correcciones se hacen mediante hallazgos y decisiones; así quedan dentro del resultado esperado verificable.

Estados mínimos: sin documento, entrada válida, analizando, revisión pendiente, listo para previsualizar, previsualizado y confirmado, comprobando contenido residual, revisión residual pendiente, exportando/verificando, comprobaciones superadas, cancelado o bloqueado por error. Cualquier cambio en términos, hallazgos, grupos o decisiones del original invalida la vista previa, la confirmación y todas las decisiones residuales. Un nuevo análisis del original invalida sus decisiones previas. La pasada de verificación del resultado no es un nuevo análisis del original y no borra sus decisiones. No se acepta un resultado tardío de una revisión anterior.

No se podrá iniciar exportación mientras existan candidatos sin decidir, intervalos inválidos, conflictos, recursos ausentes, un análisis incompleto o falta de confirmación humana. Cero detecciones no evita la revisión del texto y la confirmación. Rechazar un candidato es una decisión registrada, no una prueba de ausencia de sensibilidad.

## 7. Exportación y verificación

### Invariantes de integridad

- Abrir el origen únicamente para leer. La copia de trabajo corresponde a los bytes leídos en esa sesión; la aplicación no sigue cambios posteriores del origen ni vuelve a guardarlo.
- No copiar metadatos, atributos extendidos, permisos, comentarios ni nombre del origen a la salida. Proponer `documento_saneado.txt`; el usuario elige el destino.
- Nunca reemplazar archivos existentes, ni siquiera si el usuario selecciona su nombre. Rechazar origen/destino idénticos y alias por symlink o hardlink.
- Crear archivos de trabajo con permisos restrictivos y nombre exclusivo en el directorio de destino; ninguna API de temporales usará contenido o nombres originales como prefijo.
- Publicar el TXT mediante una operación exclusiva que no pueda sobrescribir un destino aparecido durante el proceso. Si el sistema de archivos no permite garantizarlo, bloquear y explicar que debe elegirse otro destino. El plan elegirá la primitiva y sus pruebas de concurrencia.

El motor aplica una lista de intervalos ordenados y no solapados sobre el texto original. Debe reconstruir el texto sin alterar segmentos externos a ellos. No utilizar reemplazos globales que puedan afectar a otras ocurrencias o a etiquetas ya generadas.

### Comprobaciones obligatorias

1. Validar de nuevo revisión, confirmación, cobertura e intervalos.
2. Construir el texto esperado y comprobar todas las sustituciones y la conservación de los segmentos no seleccionados.
3. Buscar coincidencias residuales exactas de los valores seleccionados para eliminar o seudonimizar en el texto esperado, en todos sus lugares, no solo en los intervalos originales. Si una cadena persiste, bloquear y pedir revisar sus ocurrencias o la acción. No se aceptan excepciones implícitas aunque exista un candidato rechazado.
4. Reanalizar el texto esperado con el mismo detector y configuración. Se analizan también las etiquetas; un falso positivo se revisa, no se ignora automáticamente. Las detecciones nuevas o no justificadas por decisiones previas bloquean la exportación. Las decisiones anteriores solo se trasladan mediante la correspondencia exacta entre segmentos conservados y su procedencia, sin heredar decisiones por mera igualdad de texto.
5. Ante bloqueos de los pasos 3 o 4, mostrar hallazgos en una ronda residual y volver a exigir vista previa y confirmación. Permitir marcar un candidato residual como falso positivo de forma explícita. La comprobación de valores originales seleccionados del paso 3 sigue siendo obligatoria y no admite excepción: para conservarlos habría que cambiar la decisión original y revisar de nuevo. La resolución de posiciones y la vigencia de estas decisiones se definen a continuación.
6. Escribir el candidato, reabrirlo y exigir igualdad de bytes con el UTF-8 esperado. Registrar digest del contenido exportado, sin incluir el digest del original en el informe.
7. Publicar de forma exclusiva y volver a leer el destino final: comprobar identidad, contenido y digest antes de indicar éxito. Escribir y verificar con recursos acotados, sin abrir documentos en otra aplicación.

### Rondas residuales: una única transformación del original

El documento original sigue siendo la única base de transformación. No existe una cadena de ediciones del resultado ni se crean hallazgos del original con coordenadas del TXT generado. La construcción del resultado produce un mapa de segmentos: cada tramo conservado apunta a su intervalo original; cada sustituto apunta al hallazgo que lo generó.

Una detección residual se muestra sobre el resultado y tiene su propio tipo de registro. Si está íntegramente en texto conservado, el usuario puede marcarla como falso positivo o volver al intervalo original para añadir/corregir su selección. Si cae dentro de una etiqueta o marcador, puede rechazarla como falso positivo del texto generado o volver a la decisión que produjo ese sustituto para cambiar categoría o acción. Si atraviesa ambos tipos de segmentos, se muestran todas las procedencias implicadas: la corrección vuelve a las decisiones originales y, si hace falta, a una nueva selección que abarque los intervalos originales afectados. No se ofrece aceptar y reemplazar automáticamente el intervalo residual.

Todo cambio en esas decisiones reconstruye la salida desde cero, invalida su confirmación y exige repetir la pasada residual. Las etiquetas se recalculan según el orden definido. Si un sustituto contiene por coincidencia un valor que el paso 3 exige retirar, el usuario debe cambiar la acción o decisión original; el aviso no se puede rechazar como falso positivo. La redacción sin marcador permite retirar un fragmento cuando un marcador de redacción lo reintroduciría.

Un rechazo residual se vincula a la revisión del original, digest exacto del resultado esperado, identidad de modelo/reglas/configuración, intervalo residual, categoría y procedencia del detector. Solo vale para esa combinación. Cualquier reconstrucción causada por cambiar decisiones del original, reanálisis del original o cambio de configuración lo invalida, aunque vuelva a aparecer el mismo texto. Confirmar o rechazar únicamente un candidato residual no modifica el contenido, por lo que no invalida otros rechazos de esa misma combinación. Una pasada de verificación idéntica puede reutilizarlos únicamente si coinciden todos sus campos. Estos rechazos tampoco se persisten fuera de la sesión.

Una segunda pasada del mismo detector puede repetir falsos negativos. La comparación de bytes comprueba lo escrito, no el anonimato del contexto. Ambas limitaciones deben constar en el resultado.

Si algo falla o se cancela, no emitir éxito ni informe de comprobaciones superadas. Eliminar únicamente archivos creados por esta operación cuya identidad siga coincidiendo, nunca un archivo sustituido por un tercero. Si no se puede limpiar, mostrar al usuario la ubicación del archivo pendiente y el estado de error; no registrar esa ruta en logs. No es posible garantizar el borrado forense ni la eliminación de copias ajenas a la aplicación.

### Informe

El informe opcional es independiente del TXT y se guarda después de un resultado correcto, también sin sobrescritura. Incluye versión de aplicación y componentes, configuración no sensible, fecha, alcance de entrada/salida, conteos por categoría y decisión, resultado de comprobaciones y SHA-256 del TXT. Las listas de términos, texto original, sustituciones originales, fragmentos, nombres de archivo y rutas quedan excluidos.

La aplicación no genera informes de auditoría con valores originales en este MVP. Si falla el guardado del informe, se indicará «TXT verificado; informe no guardado»; no se elimina el TXT correcto ni se declara que ambos archivos se guardaron. Los conteos pueden ser sensibles: el informe es local y opcional, nunca se adjunta automáticamente.

## 8. Privacidad y amenazas

| Riesgo | Control previsto | Riesgo residual |
| --- | --- | --- |
| Envío de información | Sin funciones de subida, telemetría, actualizaciones automáticas ni recognizers remotos; modelos cargados por ruta local. | Debe comprobarse la conducta de dependencias; otros programas del equipo quedan fuera del control de la aplicación. |
| Modelo o configuración ausente | Bloquear el análisis con diagnóstico; no descargar ni pasar a un modo degradado silencioso. | La preparación del entorno necesita aprobación separada para dependencias y pesos. |
| Fuga por diagnóstico | Errores con códigos y mensajes sanitizados; sin texto, rutas, términos ni volcado de excepciones de terceros en logs. Sin logs persistentes por defecto. | No se pueden controlar íntegramente crash reports o swap del sistema operativo. |
| Falsos negativos | Revisión completa, marcado manual, vocabulario específico y evaluación por categorías. | Identificación por contexto y entidades nuevas permanecen posibles. |
| Consumo o caída del motor | Tamaño limitado, un trabajo activo, GUI separada del trabajo costoso y pruebas de errores. | La opción A no contiene una caída nativa ni impone aislamiento de seguridad. |
| Rastros y sincronización | Estado sensible solo en sesión, temporales mínimos y permisos restrictivos. | No se promete borrado físico en SSD, snapshots, copias o servicios que sincronicen el destino. |
| Archivo cambiado por otro proceso | Identidad y digest de la copia publicada, publicación exclusiva y limpieza condicionada a identidad. | La verificación describe los bytes observados en ese momento; cambios posteriores invalidan el resultado. |

La interfaz separará «texto procesado», «pendiente de revisión», «contenido no inspeccionable» y «riesgo contextual». Para TXT/Markdown, el alcance es la fuente textual admitida, no archivos enlazados ni recursos externos: estos no se abren. Un formato no soportado se bloquea; no se exporta parcialmente con sello de verificación.

## 9. Criterios de aceptación y pruebas

Se utilizarán exclusivamente fixtures sintéticos. Los resultados de estas pruebas no se extrapolan a documentos reales ni a todos los Mac M1 y posteriores.

| Área | Criterio verificable |
| --- | --- |
| Integridad | Bytes y hash de cada original intactos al terminar operaciones correctas, canceladas y fallidas. Rechazo de destinos existentes y alias; prueba de colisión durante la publicación. |
| Transformación | Resultado esperado exacto, intervalos no solapados y conservación de cada segmento no seleccionado. Cero valores seleccionados residuales antes de declarar éxito. |
| Coherencia | Repeticiones aceptadas del mismo grupo reciben idéntica etiqueta; alias y grupos separados respetan las decisiones; asignación reproducible por orden. |
| Revisión | Candidatos pendientes, cambios posteriores a la previsualización o resultados tardíos nunca habilitan exportación. Probar residuales en texto conservado, sustitutos y cruces; invalidación de rechazos al cambiar revisión o configuración, y reutilización solo sobre resultados idénticos con todos sus campos coincidentes. |
| Unicode y entrada | UTF-8, BOM, acentos, combinaciones, emoji, CRLF/LF, texto vacío, controles, límites y archivos de formato incorrecto; nada se trunca o transforma silenciosamente. |
| Identificadores | Corpus congelado separado del desarrollo, al menos 50 positivos y 50 negativos por correo, teléfono español, DNI/NIF personal, NIE e IBAN español. Cero falsos negativos y precisión mínima del 95 % en esos conjuntos. Pasaporte y fecha: mismo mínimo de ejemplos, métricas y fallos publicados; sin umbral de recall que se presente como garantía. |
| NER | Al menos 100 entidades anotadas por PERSONA, ORGANIZACION y UBICACION en contextos sintéticos variados; precisión y recall por categoría de al menos 90 %, con coincidencia exacta de intervalo y categoría. Publicar errores y resultados agregados. |
| Audiovisual | 100 % de coincidencias literales esperadas del diccionario según su política documentada y cero coincidencias indebidas en el conjunto de límites. Prueba separada de títulos/personajes no suministrados: informar que su detección automática no está cubierta. |
| Exportación | Reapertura y comparación exacta de candidato y destino final; manejar permisos, falta de espacio, lectura fallida, colisión, cancelación y limpieza fallida sin éxito aparente. |
| Privacidad | Inspeccionar logs, errores, informe y temporales con cadenas centinela. Flujo completo con red bloqueada y recursos ya locales; registrar cualquier intento de conexión observado. No modificar configuraciones de seguridad del usuario para probarlo. |
| GUI | Smoke test manual en macOS Apple Silicon: seleccionar, revisar, añadir/corregir, previsualizar, cancelar y exportar. La GUI permanece utilizable mientras trabaja el detector; seleccionar correctamente texto con emoji. |

Precisión = TP / (TP + FP), recall = TP / (TP + FN). Informar denominadores, tamaño y hash del corpus, versión de modelo/reglas, configuración, errores y falsos negativos por tipo. Congelar el conjunto de evaluación antes de ajustar detectores con sus resultados; si se utiliza para afinarlos, pasa a desarrollo y se necesita otro conjunto independiente.

Los umbrales son puertas de aceptación de esta entrega. Si la base no los alcanza, se entrega el resultado del experimento y una propuesta de ajuste; no se baja el objetivo ni se incorpora otro modelo sin revisar alcance. No se promete anonimato porque el corpus pase.

Medir tiempo en frío y caliente, tiempo de análisis de 20 000 y 100 000 caracteres y memoria máxima en el equipo de desarrollo. No fijar una promesa de latencia antes de la medición. Una limitación que haga impracticable el límite admitido debe resolverse o proponerse al usuario como cambio de alcance antes de dar el MVP por aceptado.

## 10. Preparación, documentación y evolución

La primera entrega prevista se ejecutará desde un entorno virtual local documentado. No incluye instalador, firma, notarización ni publicación. Fijar una versión de Python compatible y un lock de dependencias reproducible, así como revisión, licencia y checksum del modelo. El modelo se prepara mediante una acción explícitamente autorizada y luego se carga offline; nunca durante el análisis de un documento.

Mantener README de instalación/uso y límites, procedimiento de pruebas y un changelog breve. Las decisiones duraderas se incorporan a esta especificación o a su sucesora, evitando documentos duplicados.

**Regla de versionado autorizada por el usuario el 23/10/2026:** por cada cambio lógico completado y revisado, ejecutar las comprobaciones proporcionales, crear un commit descriptivo y hacer push a [GuerraMagica/Anonimizador](https://github.com/GuerraMagica/Anonimizador). Un cambio lógico puede agrupar varios archivos relacionados; no significa publicar cada pulsación ni estados intermedios sin revisar. Verificar que el SHA remoto coincide con el commit publicado. Si el push falla, informar del commit local pendiente y del motivo, sin declarar sincronización. No incluir secretos, materiales confidenciales, archivos originales, cachés o rutas internas de la máquina. No usar force push ni sobrescribir historia remota. Esta autorización de versionado no autoriza implementar funcionalidades fuera de la fase aprobada ni publicar materiales de producción.

Evolución prevista, con especificaciones propias: DOCX a TXT con inventario OOXML; PDF a TXT con cobertura explícita; después OCR o exportaciones visuales si se necesitan. Reevaluar proceso separado antes de añadir parsers complejos. La independencia del dominio permite ese cambio sin reescribir detección, revisión y transformación.

## 11. Estado de revisión

Esta especificación necesita aprobación expresa, conforme a la fase 3 solicitada por el usuario. Después se redactará un plan de tareas y pruebas; el usuario ha aprobado anticipadamente el plan que se considere adecuado, por lo que no se repetirá su aprobación si se ajusta a la especificación aceptada. Las instalaciones y descargas seguirán detallando artefactos, tamaños y accesos externos antes de solicitar la autorización correspondiente. La preaprobación del plan no se interpreta como aprobación de esta especificación ni como autorización para escribir producto durante la fase de diseño.

Se dejan al implementador nombres de clases/archivos, disposición concreta de widgets, primitivas de Qt, estrategia exacta de publicación exclusiva, herramientas de test y versiones compatibles del entorno, siempre que respeten estos contratos. Cambios de alcance, nuevos modelos, persistencia sensible, procesos adicionales o relajación de bloqueos requieren revisión con el usuario.

## 12. Revisión de la fase 3 con graphify — 24/10/2026

Se ha generado un [grafo documental](../../../graphify-out/graph.json) y un [informe de extracción](../../../graphify-out/GRAPH_REPORT.md) sobre los dos documentos existentes en el commit `74fe844efa5b982e8954d04a5972e42dd3c7bbdb`, anterior a esta revisión. Es una instantánea, no un índice actualizado automáticamente: esta sección y los cambios posteriores de autorización no están incorporados en sus nodos. El informe conserva los hashes de las fuentes para identificar exactamente su cobertura.

La extracción contiene 40 nodos, 54 relaciones explícitas y 6 comunidades; el diagnóstico no encuentra extremos ausentes, relaciones duplicadas, bucles ni colapsos entre pares. Estos resultados acreditan propiedades del grafo construido, no exhaustividad de la extracción ni corrección de la aplicación. El visor HTML de graphify usa una biblioteca JavaScript externa; esa dependencia del artefacto no forma parte del diseño offline del producto.

La consulta de revisión conecta controles ya definidos en esta especificación: revisión humana → bloqueos de estado → exportación; exportación → rondas residuales y publicación exclusiva; publicación exclusiva → criterios de aceptación. Es una relación entre requisitos del diseño. Se conserva su separación al planificar:

- **Detección:** medir precisión, recall y falsos negativos; no confundir un acierto del diccionario con detección de una producción desconocida.
- **Revisión:** exigir decisiones completas y vigentes, con procedencia y tratamiento explícito de conflictos.
- **Transformación:** comprobar los intervalos, la coherencia de etiquetas y los valores seleccionados que puedan persistir.
- **Archivo exportado:** comprobar ausencia de sobrescritura, igualdad de bytes y digest del destino final.
- **Privacidad:** comprobar procesamiento sin red y ausencia de contenido sensible en diagnósticos e informe, conservando la revisión del riesgo contextual.

No surge de esta revisión una necesidad demostrada de cambiar la opción A, añadir procesos, modelos o formatos. Se mantiene la propuesta TXT/Markdown → TXT y la evolución DOCX → PDF → OCR como ampliaciones separadas. Siguen pendientes la aprobación del diseño, la instalación autorizada, la evaluación real de detectores y rendimiento y las pruebas en macOS. No se han escrito ni probado funcionalidades de producto durante esta fase.
