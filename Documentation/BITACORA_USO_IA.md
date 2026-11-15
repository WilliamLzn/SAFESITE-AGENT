

## 4. Decisiones del Hito 2 (15-nov-2026)

| Decisión | Papel de la IA | Papel del equipo |
|---|---|---|
| Estados de cámara (Reconociendo -> Reconocido -> Escaneando EPP) + overlay dentro del video | Propuso y escribió el código de la máquina de estados | Validamos que aparezca correctamente dentro del cuadro de la cámara y no encima de otros elementos |
| Emojis por puesto en badges de trabajador | Propuso el mapeo puesto->emoji (supervisor 🦺, albañil 🧱, electricista ⚡, ayudante 🛠️, operario_grua 🏗️, soldador 🔥) y lo implementó | Validamos que se vean correctamente en las cards |
| Horas semanales + alerta de salida mal trazada | Propuso la lógica de acumulación semanal y el umbral de tolerancia de 30 min | Definimos los umbrales exactos y el comportamiento de la alerta |
| Fix deadlock en marcar_entrada/marcar_salida (lock reentrante) | Identificó la causa raíz (Lock de Python no es reentrante) y propuso la solución (acceso directo al estado sin llamar a esta_dentro()) | Validamos que el hilo ya no se muere |
| Fix endpoint /badge/estado para siempre devolver JSON válido | Propuso el try/except que devuelve [] ante cualquier error | Verificamos que el navegador ya no lanza Uncaught SyntaxError |
| Reducción de logs del bucle de captura | Propuso eliminar logs repetitivos por frame y dejar solo cambios de estado | Validamos que la consola sea legible |

