# Implementación y pruebas de un agente inteligente

En parejas, cada equipo implementa uno de los dos agentes inteligentes que diseñó en la entrega anterior y demuestra, con pruebas, que cumple las medidas de desempeño que el mismo equipo definió.

La actividad tiene tres fases:

1. **Selección justificada.** El equipo compara sus dos agentes asignados con una matriz de decisión y elige uno con argumentos medibles.
2. **Desarrollo.** El equipo construye el agente, corrige el documento de diseño y le agrega un apartado nuevo que describe la implementación.
3. **Evidencia y pruebas.** El equipo muestra el agente funcionando (plataforma desplegada o video de máximo 20 minutos) y reporta las pruebas contra las medidas de desempeño.

**Modalidad:** parejas. Una sola entrega por pareja.

**Punto de partida:** el documento de la Tarea 2 — Diseño inicial de un agente inteligente (Plantilla_Diseño_Agente): tipo de agente, tipos de ambiente, entorno, entradas y sensores, salidas y actuadores, medidas de desempeño SMART y los siete componentes de la arquitectura de IA agéntica de IBM. Ese documento no se reemplaza: se corrige y se amplía.

---

## Fase 1 — Selección justificada del agente

La pareja elige uno de sus dos agentes asignados mediante una matriz de decisión ponderada. La elección debe poder reconstruirse a partir de la matriz: si otra persona aplica los mismos pesos y puntajes, debe llegar al mismo agente.

### Paso 1. Criterios y pesos

Definan los criterios y sus pesos **antes** de puntuar. Usen como mínimo estos seis criterios; pueden agregar otros si los justifican. Los pesos deben sumar 100 %.

| Criterio | Qué evalúa | Cómo se mide (ejemplo) | Peso sugerido |
|---|---|---|---|
| Viabilidad técnica | Si pueden construirlo con sus conocimientos y el tiempo disponible | Número de componentes que ya saben implementar / total | 25 % |
| Disponibilidad de datos o entorno | Si existe o pueden simular el entorno, los sensores y los datos | Fuente identificada, simulador o dataset concreto | 20 % |
| Medibilidad del desempeño | Si sus medidas de desempeño se pueden probar de forma objetiva | Medidas con fórmula y umbral / total de medidas | 20 % |
| Complejidad de IA | Si el agente exige razonamiento real (búsqueda, reglas, aprendizaje, planificación), no solo condicionales | Tipo de agente según Russell y Norvig (reflejo simple → basado en utilidad / de aprendizaje) | 15 % |
| Costo y recursos | Dinero, hardware, APIs pagas o cuotas que requiere | Costo estimado en COP o en llamadas de API | 10 % |
| Valor del problema | Utilidad real de la solución para un usuario identificable | Usuario y beneficio concreto descritos | 10 % |

### Paso 2. Puntuación

Puntúen cada agente de 1 a 5 en cada criterio. Cada puntaje lleva una frase de evidencia (“3: el simulador existe pero no modela la batería”). **Un puntaje sin evidencia no cuenta.**

### Paso 3. Puntaje ponderado

```
S(agente) = Σ (wᵢ × pᵢ)
```

Donde `wᵢ` es el peso del criterio *i* expresado como fracción (25 % = 0,25), `pᵢ` su puntaje de 1 a 5, y `Σ wᵢ = 1`. El puntaje máximo posible es 5.

### Paso 4. Análisis de sensibilidad

Cambien el peso del criterio más influyente en ±10 puntos y verifiquen si la decisión se mantiene. Si cambia, expliquen por qué se quedan con su elección.

### Paso 5. Justificación (máximo una página)

Incluir: agente elegido, puntajes finales, resultado de la sensibilidad y qué pierden al descartar el otro agente.

### Plantilla de la matriz

| Criterio | Peso (w) | Agente A: puntaje (1–5) | Agente A: evidencia | Agente B: puntaje (1–5) | Agente B: evidencia |
|---|---|---|---|---|---|
| Viabilidad técnica | | | | | |
| Disponibilidad de datos o entorno | | | | | |
| Medibilidad del desempeño | | | | | |
| Complejidad de IA | | | | | |
| Costo y recursos | | | | | |
| Valor del problema | | | | | |
| **Puntaje ponderado S** | **100 %** | | | | |

---

## Fase 2 — Desarrollo del agente

El agente implementado debe corresponder al diseño: mismo entorno, mismos sensores y actuadores, mismo tipo de agente. Si algo cambió al implementarlo, se permite, pero se documenta y se justifica.

### Requisitos mínimos de la implementación

- **Función del agente explícita.** En el código debe identificarse dónde el agente recibe la percepción, dónde decide y dónde actúa (ciclo percepción → decisión → acción).
- **Coherencia con el tipo de agente.** Un agente basado en modelo mantiene estado interno; uno basado en metas busca o planifica; uno basado en utilidad compara alternativas con una función de utilidad; uno de aprendizaje mejora con la experiencia.
- **Entorno real o simulado.** Si no tienen acceso al entorno real, construyan un simulador mínimo que genere las percepciones descritas en la sección 5 (Entradas y sensores) y respete las propiedades de ambiente de la sección 3 (por ejemplo, si declararon el ambiente estocástico, el simulador debe introducir aleatoriedad).
- **Registro (log) de ejecución.** Cada ejecución guarda percepciones, decisiones y acciones con marca de tiempo. Este log es la base de las pruebas de la Fase 3.
- **Reproducibilidad.** Repositorio (GitHub, GitLab o similar) con README, dependencias (`requirements.txt` o equivalente) e instrucciones para ejecutarlo en otro equipo.
- **Tecnologías.** Pueden usar cualquier lenguaje y plataforma (Python, notebooks, frameworks de agentes, APIs de modelos de lenguaje, microcontroladores, herramientas no-code). Condición: deben explicar qué parte del razonamiento hace su código y qué parte hace cada herramienta externa. Si usan un LLM, deben indicar el modelo, el prompt de sistema y qué decisiones del agente dependen de él.

---

## Fase 3 — Pruebas basadas en las medidas de desempeño

Cada medida de desempeño SMART de la sección 7 del diseño se convierte en al menos una prueba con resultado numérico. Si una medida no se pudo probar tal como estaba escrita, se reformula en el documento ajustado y se explica por qué.

Para cada medida, definan:

- **Fórmula o regla de cálculo** (por ejemplo, tasa de éxito = tareas completadas / tareas intentadas).
- **Umbral de aceptación** (por ejemplo, ≥ 90 %), fijado **antes** de ejecutar las pruebas.
- **Escenarios de prueba:** mínimo 10 casos, que incluyan casos normales, casos límite y al menos 2 casos de falla esperada (entradas inválidas, entorno adverso, sensor sin dato).
- **Repeticiones:** si el agente o el entorno tienen aleatoriedad, mínimo 5 ejecuciones por escenario, y se reporta media y desviación estándar.

### Tabla de resultados (obligatoria)

| Medida de desempeño | Fórmula | Umbral | Casos ejecutados | Resultado obtenido | ¿Cumple? | Evidencia (log, captura, minuto del video) |
|---|---|---|---|---|---|---|
| | | | | | | |
| | | | | | | |

### Análisis de resultados (máximo una página)

Qué medidas se cumplieron, cuáles no, la causa probable de cada falla y qué cambiarían en el agente para corregirla. Una medida incumplida bien analizada vale más que una cumplida sin evidencia.

---

## Entregables

Cada pareja entrega tres productos.

### 1. Documento de diseño ajustado (PDF)

El mismo documento de la entrega anterior, con:

- Todas las correcciones señaladas en la retroalimentación del docente.
- **Tabla de cambios al inicio:** sección, qué decía, qué dice ahora y por qué cambió.
- **Matriz de decisión y justificación** de la Fase 1, como sección nueva antes del diseño.

### 2. Desarrollo del agente

Se inserta como **sección 9** de la plantilla, antes de Conclusiones (que pasa a ser la sección 10), con estas subsecciones:

1. **Arquitectura.** Diagrama de componentes del agente (sensores, modelo o estado interno, módulo de decisión, actuadores, servicios externos) y cómo se conectan. Indiquen qué módulo del código implementa cada uno de los siete componentes IBM descritos en la sección 8 del diseño, y cuáles quedaron sin implementar y por qué.
2. **Tecnologías.** Tabla con cada tecnología usada, su versión, para qué se usó y por qué se eligió frente a una alternativa.
3. **Entradas (inputs).** Cada percepción que recibe el agente: nombre, tipo de dato, rango o formato, origen (sensor, usuario, API, archivo) y un ejemplo real.
4. **Salidas y acciones.** Cada acción que ejecuta el agente y su efecto en el entorno.
5. **Diagrama de secuencia UML.** Muestra la interacción completa en al menos un escenario típico y uno de excepción. Debe incluir como participantes: usuario o actor externo, interfaz, agente (separando percepción, decisión y acción si aplica), entorno y servicios externos. Mensajes con nombre, en orden temporal, con respuestas y al menos un fragmento `alt` o `loop`. Herramientas sugeridas: PlantUML, Mermaid, draw.io o Lucidchart.
6. **Diferencias entre diseño e implementación.** Qué se implementó distinto a lo diseñado y por qué.
7. **Pruebas.** Tabla de resultados y análisis de la Fase 3.
8. **Limitaciones y trabajo futuro.**
9. **Enlaces:** repositorio, plataforma de despliegue o video.

### 3. Evidencia de funcionamiento

Elijan una de dos opciones:

- **Opción A — Plataforma de despliegue.** Enlace público al agente funcionando (Streamlit Cloud, Hugging Face Spaces, Render, Vercel o similar), disponible hasta la fecha de calificación, con instrucciones de uso y casos de prueba sugeridos.
- **Opción B — Video.** Máximo 20 minutos, con cámara y voz de ambos integrantes, publicado como enlace (YouTube no listado, OneDrive o Drive con acceso habilitado).

En cualquiera de las dos opciones, la evidencia debe mostrar:

- El agente ejecutándose **desde cero** (no solo resultados guardados).
- Al menos un escenario típico y uno de falla esperada.
- La ejecución de las pruebas y la obtención de los valores de la tabla de resultados.
- En el video: índice con minutos al inicio (por ejemplo, 00:00 introducción, 03:00 arquitectura, 08:00 demo, 14:00 pruebas).

> Un video que supere 20 minutos solo se evalúa hasta el minuto 20.

---

## Rúbrica de evaluación (100 puntos)

| Criterio | Pts | Excelente (100 %) | Aceptable (60 %) | Insuficiente (0–30 %) |
|---|---|---|---|---|
| 1. Matriz de decisión y justificación | 15 | ≥ 6 criterios con pesos justificados, cada puntaje con evidencia, sensibilidad hecha y la decisión se sigue de la matriz | Matriz completa pero con evidencia parcial o sin análisis de sensibilidad | Elección por preferencia, sin pesos o sin evidencia |
| 2. Documento ajustado | 10 | Atiende toda la retroalimentación e incluye tabla de cambios | Atiende la mayoría; tabla de cambios incompleta | Repite el documento anterior sin cambios |
| 3. Implementación del agente | 25 | Funciona, es coherente con el diseño (tipo de agente, ambiente, sensores y actuadores), ciclo percepción→decisión→acción identificable, repositorio reproducible | Funciona con fallas menores o con incoherencias parciales frente al diseño | No funciona, o no corresponde al agente diseñado |
| 4. Apartado de desarrollo: tecnologías, inputs y arquitectura | 10 | Tecnologías justificadas; inputs con tipo, rango, origen y ejemplo; arquitectura clara | Descripción incompleta de inputs o tecnologías sin justificar | Ausente o genérico |
| 5. Diagrama de secuencia | 10 | UML correcto, participantes completos, escenario típico y de excepción, fragmento alt o loop, coincide con el código | Correcto pero con un solo escenario o participantes faltantes | Ausente, no es de secuencia, o no corresponde al agente |
| 6. Pruebas contra medidas de desempeño | 20 | Todas las medidas probadas con fórmula, umbral previo, ≥ 10 casos, repeticiones y evidencia trazable; análisis de fallas | Pruebas incompletas, sin umbral previo o sin evidencia trazable | Sin pruebas, o pruebas que no corresponden a las medidas |
| 7. Evidencia de funcionamiento | 10 | Despliegue estable o video ≤ 20 min con demo en vivo, caso de falla y pruebas; ambos integrantes participan | Evidencia parcial (sin caso de falla o sin mostrar las pruebas) | Sin evidencia, enlace caído o solo capturas |
| **Total** | **100** | | | |

**Escala:** Sobresaliente 90–100 · Bueno 75–89 · Aceptable 60–74 · Insuficiente 0–59.

Para la escala institucional 0.0–5.0, se divide cada puntaje entre 20 (por ejemplo, el criterio 3 vale 1.25 y el total 5.0).

---

## Condiciones de entrega

Qué se sube (una entrega por pareja):

- [ ] Documento ajustado en PDF, con la matriz de decisión y el apartado “Desarrollo del agente”.
- [ ] Enlace al repositorio con README e instrucciones de ejecución.
- [ ] Enlace a la plataforma de despliegue o al video (≤ 20 min).
- [ ] Logs de las pruebas (archivo CSV, JSON o TXT) referenciados en la tabla de resultados.
- [ ] Bitácora de uso de IA.
