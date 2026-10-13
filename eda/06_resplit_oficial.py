"""Fase 0 — Re-split OFICIAL del dataset Construction PPE (SafeSite-Agent).

Corrige los hallazgos F2/F3/F4 del EDA:
- F2: el split 80/20 propio ignoraba el campo `split` oficial del NDJSON
      (112 imagenes del test oficial habian quedado en train/).
- F3: no existia conjunto de validacion propio.
- F4: test/ estaba sin etiquetas aunque el NDJSON contiene sus anotaciones.

Reglas (AGENTS.md + skill exploratory-data-analysis):
- safesite_dataset/ y construction-ppe.ndjson permanecen INTOCADOS (solo lectura).
- Salida 100% derivada en dataset_v2/ (se regenera de cero en cada corrida).
- Etiquetas generadas desde el NDJSON con el mismo formato verificado del
  pipeline original (6 decimales; fidelidad confirmada por el EDA).
- Las 3 imagenes que faltan en disco se descargan del CDN oficial (url del NDJSON).
- Semilla/orden: determinista (recorrido por orden del NDJSON).
"""
import json
import os
import shutil
import sys
import time
import urllib.request

BASE = r"C:\Users\Lenovo\Documents\IA\SAFESITE-AGENT"
NDJSON = os.path.join(BASE, "construction-ppe.ndjson")
FUENTES = [os.path.join(BASE, "safesite_dataset", "train"),
           os.path.join(BASE, "safesite_dataset", "test")]
DESTINO = os.path.join(BASE, "dataset_v2")
YAML = os.path.join(DESTINO, "dataset.yaml")
TIMEOUT_DESCARGA = 30
REINTENTOS = 2

CLASES_EN_ORDEN = [
    "helmet", "gloves", "vest", "boots", "goggles", "none", "Person",
    "no_helmet", "no_goggle", "no_gloves", "no_boots",
]


def leer_ndjson():
    dataset_rec, imagenes = None, []
    with open(NDJSON, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") == "dataset":
                dataset_rec = rec
            elif rec.get("type") == "image":
                imagenes.append(rec)
    return dataset_rec, imagenes


def buscar_en_disco(nombre):
    for carpeta in FUENTES:
        ruta = os.path.join(carpeta, nombre)
        if os.path.exists(ruta):
            return ruta
    return None


def descargar(url, destino):
    for intento in range(1, REINTENTOS + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "SafeSite-Agent-Fase0/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_DESCARGA) as r:
                with open(destino, "wb") as f:
                    shutil.copyfileobj(r, f)
            return True
        except Exception as e:
            print(f"  descarga intento {intento} fallida ({e}); "
                  f"{'reintentando' if intento < REINTENTOS else 'se omite'}")
            time.sleep(2)
    return False


def main():
    dataset_rec, imagenes = leer_ndjson()

    # validar class_names del NDJSON contra la lista esperada del EDA
    nombres_ndjson = dataset_rec.get("class_names", {})
    nombres_ndjson = [nombres_ndjson[str(i)] for i in range(len(nombres_ndjson))]
    assert nombres_ndjson == CLASES_EN_ORDEN, (
        f"desacuerdo de clases: {nombres_ndjson}")

    # regenerar dataset_v2 desde cero (artefacto derivado)
    if os.path.exists(DESTINO):
        print(f"Eliminando dataset_v2 previo (artefacto derivado): {DESTINO}")
        shutil.rmtree(DESTINO)
    for split in ("train", "val", "test"):
        os.makedirs(os.path.join(DESTINO, "images", split))
        os.makedirs(os.path.join(DESTINO, "labels", split))

    conteo = {"train": 0, "val": 0, "test": 0}
    descargadas, fallidas = [], []
    etiquetas_escritas = 0

    for rec in imagenes:
        split = rec["split"]
        if split not in conteo:
            raise SystemExit(f"split inesperado: {split}")
        nombre = rec["file"]
        destino_img = os.path.join(DESTINO, "images", split, nombre)
        destino_lbl = os.path.join(
            DESTINO, "labels", split, os.path.splitext(nombre)[0] + ".txt")

        origen = buscar_en_disco(nombre)
        if origen:
            shutil.copy2(origen, destino_img)
        else:
            ok = descargar(rec["url"], destino_img)
            if ok:
                descargadas.append(nombre)
            else:
                fallidas.append(f"{nombre} (split oficial {split})")
                continue

        cajas = rec.get("annotations", {}).get("boxes", [])
        with open(destino_lbl, "w", encoding="utf-8") as f:
            for cls, x, y, w, h in cajas:
                f.write(f"{int(cls)} {float(x):.6f} {float(y):.6f} "
                        f"{float(w):.6f} {float(h):.6f}\n")
        etiquetas_escritas += len(cajas)
        conteo[split] += 1

    # ---------- dataset.yaml ----------
    yaml_text = (
        f"# Generado por eda/06_resplit_oficial.py — Fase 0 (13-oct-2026)\n"
        f"# Splits OFICIALES del NDJSON Ultralytics Construction PPE\n"
        f"path: {DESTINO.replace(os.sep, '/')}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"test: images/test\n"
        f"names:\n"
    )
    for i, nombre_clase in enumerate(CLASES_EN_ORDEN):
        yaml_text += f"  {i}: {nombre_clase}\n"
    with open(YAML, "w", encoding="utf-8") as f:
        f.write(yaml_text)

    # ---------- verificacion ----------
    en_disco = {"train": 0, "val": 0, "test": 0}
    etiquetas_disco = 0
    for split in ("train", "val", "test"):
        d_img = os.path.join(DESTINO, "images", split)
        d_lbl = os.path.join(DESTINO, "labels", split)
        jpgs = {f for f in os.listdir(d_img) if f.lower().endswith(".jpg")}
        txts = {os.path.splitext(f)[0] + ".jpg" for f in os.listdir(d_lbl)
                if f.endswith(".txt")}
        assert jpgs == txts, f"desalineacion imagen/etiqueta en {split}"
        en_disco[split] = len(jpgs)
        for t in os.listdir(d_lbl):
            with open(os.path.join(d_lbl, t), encoding="utf-8") as f:
                etiquetas_disco += sum(1 for ln in f if ln.strip())

    print("\n===== RESULTADO FASE 0 =====")
    print("imagenes por split:", en_disco, "| total:", sum(en_disco.values()))
    print("etiquetas .txt escritas: ", etiquetas_escritas, "lineas |",
          etiquetas_disco, "lineas verificadas en disco")
    print("descargadas del CDN:", len(descargadas), descargadas)
    print("descargas fallidas:", len(fallidas), fallidas)
    print("dataset.yaml:", YAML)

    # resumen JSON para la bitacora
    resumen = {
        "splits": en_disco,
        "total_imagenes": sum(en_disco.values()),
        "lineas_etiqueta": etiquetas_disco,
        "descargadas": descargadas,
        "fallidas": fallidas,
        "dataset_yaml": YAML,
    }
    with open(os.path.join(BASE, "eda", "salidas", "resumen_fase0.json"),
              "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print("resumen: eda/salidas/resumen_fase0.json")

    if fallidas:
        sys.exit(1)


if __name__ == "__main__":
    main()
