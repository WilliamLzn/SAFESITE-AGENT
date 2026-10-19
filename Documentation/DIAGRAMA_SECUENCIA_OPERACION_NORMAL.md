# Diagrama de secuencia: operación normal del agente en vivo

Flujo completo de una sesión de monitoreo con el panel web: el supervisor abre el panel, el agente percibe cada fotograma de la cámara, confirma una falta de casco tras verla en tres fotogramas seguidos (K=3), consulta la memoria de cooldown y envía la alerta consolidada con foto por WhatsApp.

```mermaid
sequenceDiagram
    participant Sup as Supervisor HSE
    participant Ent as Entorno (webcam)
    participant Panel as Panel web (panel.py)
    participant Agente as Agente (agente.py)
    participant Perc as Percepción (YOLOv8s)
    participant Raz as Razonamiento (razonamiento.py)
    participant Mem as Memoria (memoria.py)
    participant Act as Actuadores (actuarios.py)
    participant WA as WhatsApp Cloud API (Meta)

    Sup->>Panel: 1. Abre http://localhost:5000
    Panel-->>Sup: 2. Devuelve video anotado (MJPEG)

    loop Por cada fotograma capturado
        Ent->>Agente: 3. Envía frame BGR
        Agente->>Raz: 4. procesar_frame(frame, zona, t_stamp)
        Raz->>Perc: 5. detectar(frame)
        Perc-->>Raz: 6. detecciones [Person, no_helmet 0.42]
        Raz->>Raz: 7. filtrar_por_clase(detecciones) y evaluar(zona, t)

        alt racha de no_helmet alcanza K = 3 fotogramas
            Raz-->>Agente: 8. incidente confirmado
            Agente->>Mem: 9. debe_alertar(incidente, t)

            alt cooldown de 30 s vencido
                Mem-->>Agente: 10. true
                Agente->>Perc: 11. anotar(frame, filtradas)
                Agente->>Act: 12. alertar_lote(nuevos, frame_anotado)
                Act->>WA: 13. POST /media y /messages
                WA-->>Act: 14. wamid
                WA-->>Sup: 15. Alerta con foto
                Agente->>Mem: 16. registrar_alerta(incidente) -> historial JSONL
            else cooldown vigente
                Mem-->>Agente: 17. false (alerta suprimida)
            end

        else racha menor a K
            Raz-->>Agente: 18. sin incidente
        end

        Agente-->>Panel: 19. incidentes y detecciones
        Panel-->>Sup: 20. frame anotado + log de incidentes
    end
```
