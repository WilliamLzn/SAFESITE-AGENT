# Imagen de la demo de SafeSite-Agent (CPU) — sirve en Claw Cloud o en
# cualquier otro contenedor (Docker, Fly, un VPS...).
#
# Se construye DESDE LA RAÍZ del repo (el .dockerignore limita lo que
# entra al contexto):
#   docker build -f deploy/Dockerfile -t safesite-demo .
#   docker run --rm -p 7899:8788 safesite-demo   -> http://localhost:7899
FROM python:3.12-slim

# cv2 (que trae ultralytics) necesita libGL y glib en Linux
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# primero solo las dependencias: esta capa es la gorda y queda cacheada
COPY deploy/requirements.txt deploy/requirements.txt
RUN pip install --no-cache-dir -r deploy/requirements.txt

# el código de la página y del agente
COPY deploy/app.py deploy/app.py
COPY src/ src/

# artefactos que lee la página en vivo (modelo, dataset de val/test,
# figuras del EDA, métricas y corrida oficial de la suite)
COPY dataset_v2/dataset.yaml dataset_v2/dataset.yaml
COPY dataset_v2/images/val dataset_v2/images/val
COPY dataset_v2/images/test dataset_v2/images/test
COPY dataset_v2/labels/val dataset_v2/labels/val
COPY dataset_v2/labels/test dataset_v2/labels/test
COPY eda/figuras eda/figuras
COPY eda/salidas/metricas_e44.json eda/salidas/metricas_e44.json
COPY runs/safesite/tuned_v2_s/weights/best.pt runs/safesite/tuned_v2_s/weights/best.pt
COPY runs/agente/pruebas runs/agente/pruebas

# sin GPU en estos hosts: inferencia en CPU y escucha pública. El puerto
# va en PORT (estándar de contenedores): Modal usa el 8788 que trae la
# imagen, y Cloud Run pisa PORT con el suyo (8080) en su runtime.
ENV SAFESITE_DEVICE=cpu \
    SAFESITE_SERVIDOR=publico \
    PORT=8788

EXPOSE 8788
CMD ["python", "deploy/app.py"]
