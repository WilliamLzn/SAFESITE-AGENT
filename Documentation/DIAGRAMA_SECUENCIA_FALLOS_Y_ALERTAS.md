# Diagrama de secuencia: fallas del sensor y degradación del canal de alertas

Comportamiento del agente ante entradas inválidas de la cámara (frame nulo, de un solo canal o corrupto) y ante fallas del canal de WhatsApp (imagen que no sube, API caída, límites anti-spam globales). El sistema nunca se detiene por una falla: registra lo ocurrido, degrada la alerta (con foto, solo texto, o solo en el historial) y continúa su ciclo.

```mermaid
sequenceDiagram
    participant Sup as Supervisor HSE
    participant Ent as Entorno (cámara)
    participant Panel as Panel web / suite de pruebas
    participant Agente as SafeSiteAgent
    participant Perc as Percepción (YOLOv8s)
    participant Raz as Razonamiento
    participant Mem as Memoria
    participant Act as ActuadorWhatsApp
    participant WA as WhatsApp Cloud API (Meta)

    loop cada fotograma
        Ent->>Panel: 1. frame (None, 1 canal, corrupto o negro)
        Panel->>Agente: 2. procesar_frame(frame, zona, t)

        alt frame inválido (None, ndim<3, size==0)
            Agente->>Agente: 3. frames_fallidos += 1 (registra, no actúa)
            Agente-->>Panel: 4. [], [] (el ciclo continúa)

        else percepción lanza excepción
            Agente->>Perc: 5. detectar(frame)
            Perc-->>Agente: 6. Exception
            Agente->>Agente: 7. frames_fallidos += 1
            Agente-->>Panel: 8. [], []

        else frame válido con incumplimiento confirmado
            Agente->>Perc: 9. detectar(frame)
            Perc-->>Agente: 10. detecciones
            Agente->>Raz: 11. evaluar(...)
            Raz-->>Agente: 12. incidente confirmado (K=3)
            Agente->>Mem: 13. debe_alertar(incidente, t)
            Mem-->>Agente: 14. true
            Agente->>Act: 15. alertar_lote(incidentes, frame_anotado)

            alt límite global del canal (60 s o 20/hora)
                Act-->>Agente: 16. suprimida (queda en historial y panel)
            else envío real
                Act->>WA: 17. POST /media (imagen)

                alt falla la subida de imagen
                    WA-->>Act: 18. error HTTP
                    Act->>WA: 19. POST /messages (solo texto)

                    alt falla también el texto (API caída)
                        WA-->>Act: 20. error HTTP
                        Act-->>Agente: 21. None (sin excepción)
                    else texto entregado
                        WA-->>Sup: 22. alerta sin foto
                    end
                else imagen subida
                    WA-->>Sup: 23. alerta con foto
                end
            end

            Agente->>Mem: 24. registrar_alerta(incidente) -> historial JSONL
            Note over Agente,Mem: la alerta nunca se pierde: queda persistida aunque el canal falle
        end
    end
```
