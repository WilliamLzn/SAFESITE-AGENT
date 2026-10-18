"""Genera los assets de la demo estática (deploy/estatica/).

La demo estática corre el modelo EN EL NAVEGADOR del visitante (ONNX
Runtime Web); este script copia del repo todo lo que ella necesita y
deja datos.js con las métricas y la corrida oficial reales (nada
hardcodeado más allá de la fuente de cada número).

Ejecutar desde la RAIZ del proyecto:
    .venv\\Scripts\\python.exe deploy\\estatica\\generar.py
"""
import json
import os
import shutil

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
CORRIDA_OFICIAL = "20261014_170459"


def copiar(origen, destino):
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copy2(origen, destino)


def main():
    print("Generando assets de la demo estática…")

    # 1) el modelo exportado a ONNX (el validado contra best.pt en E52)
    origen = os.path.join(RAIZ, "runs", "safesite", "tuned_v2_s",
                          "weights", "best.onnx")
    destino = os.path.join(AQUI, "modelo", "best.onnx")
    if not os.path.exists(origen):
        raise SystemExit("Falta runs/safesite/tuned_v2_s/weights/best.onnx "
                         "(exportar primero con ultralytics)")
    copiar(origen, destino)
    print(f"  + modelo/best.onnx "
          f"({os.path.getsize(destino) / 1e6:.1f} MB)")

    # 2) fotos del set de test (para el sorteo con etiqueta oficial)
    carpeta = os.path.join(AQUI, "fotos")
    os.makedirs(carpeta, exist_ok=True)
    origen = os.path.join(RAIZ, "dataset_v2", "images", "test")
    n = 0
    for nombre in sorted(os.listdir(origen)):
        if nombre.endswith(".jpg"):
            copiar(os.path.join(origen, nombre), os.path.join(carpeta, nombre))
            n += 1
    print(f"  + fotos/ ({n} fotos de test)")

    # 3) etiquetas oficiales de test: nombre -> ids de clase presentes
    etiquetas = {}
    origen = os.path.join(RAIZ, "dataset_v2", "labels", "test")
    for nombre in sorted(os.listdir(origen)):
        if not nombre.endswith(".txt"):
            continue
        with open(os.path.join(origen, nombre), encoding="utf-8") as f:
            ids = sorted({int(line.split()[0]) for line in f if line.strip()})
        etiquetas[nombre[:-4] + ".jpg"] = ids
    print(f"  + etiquetas de {len(etiquetas)} fotos")

    # 4) figuras del EDA
    origen = os.path.join(RAIZ, "eda", "figuras")
    for nombre in sorted(os.listdir(origen)):
        if nombre.endswith(".png"):
            copiar(os.path.join(origen, nombre),
                   os.path.join(AQUI, "figuras", nombre))
    print("  + figuras/ (6 figuras del EDA)")

    # 5) métricas y corrida oficial, tal cual quedaron en el repo
    with open(os.path.join(RAIZ, "eda", "salidas", "metricas_e44.json"),
              encoding="utf-8") as f:
        metricas = json.load(f)
    ruta_json = os.path.join(RAIZ, "runs", "agente", "pruebas",
                             f"resultados_{CORRIDA_OFICIAL}.json")
    with open(ruta_json, encoding="utf-8") as f:
        corrida = json.load(f)
    # la tabla MD oficial (texto) para mostrarla íntegra
    with open(os.path.join(RAIZ, "runs", "agente", "pruebas",
                           f"tabla_resultados_{CORRIDA_OFICIAL}.md"),
              encoding="utf-8") as f:
        tabla_md = f.read()

    datos = {
        "corridaOficial": corrida,
        "tablaOficialMD": tabla_md,
        "metricasE44": metricas,
        "etiquetasTest": etiquetas,
    }
    ruta_datos = os.path.join(AQUI, "datos.js")
    with open(ruta_datos, "w", encoding="utf-8") as f:
        f.write("// Generado por deploy/estatica/generar.py — datos reales "
                "del repo (no editar a mano)\n")
        f.write("const DATOS = ")
        json.dump(datos, f, ensure_ascii=False)
        f.write(";\n")
    print(f"  + datos.js (corrida {CORRIDA_OFICIAL}, métricas E44, "
          f"{len(etiquetas)} etiquetas)")

    print("Listo.")


if __name__ == "__main__":
    main()
