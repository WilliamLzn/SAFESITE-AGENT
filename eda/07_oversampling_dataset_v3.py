"""Fase 2 — Oversampling de imagenes con incumplimiento (dataset_v3).

Ataca el hallazgo F5 del EDA: solo 229/1,129 imagenes de train (20.3%)
contienen clases de incumplimiento (`no_*`, ids 7-10), y `no_boots` (id 10)
tiene apenas 87 cajas en train. El baseline_v1 mostro exactamente esa
debilidad (recall no_helmet 0.47 val / 0.15 test).

Politica de replicacion (determinista, documentada):
- TODAS las imagenes de train de dataset_v2 se copian a dataset_v3.
- Las que contienen >=1 caja de clases {7,8,9,10} reciben +1 copia (`__rep1`).
- Las que contienen alguna caja de clase 10 (no_boots) reciben +1 copia mas (`__rep2`).
- val y test NO se duplican ni alteran: dataset_v3/dataset.yaml los apunta a
  dataset_v2 para que la comparacion con baseline_v1 sea justa.

Reglas: dataset_v2/ y crudos en solo lectura; salida 100% derivada en dataset_v3/.
"""
import collections
import json
import os
import shutil

BASE = r"C:\Users\Lenovo\Documents\IA\SAFESITE-AGENT"
V2 = os.path.join(BASE, "dataset_v2")
V3 = os.path.join(BASE, "dataset_v3")
V2_TRAIN_IMG = os.path.join(V2, "images", "train")
V2_TRAIN_LBL = os.path.join(V2, "labels", "train")
V3_TRAIN_IMG = os.path.join(V3, "images", "train")
V3_TRAIN_LBL = os.path.join(V3, "labels", "train")
OUT_JSON = os.path.join(BASE, "eda", "salidas", "resumen_fase2_oversampling.json")

NO_IDS = {7, 8, 9, 10}       # no_helmet, no_goggle, no_gloves, no_boots
NO_BOOTS_ID = 10
NOMBRES = {0: "helmet", 1: "gloves", 2: "vest", 3: "boots", 4: "goggles",
           5: "none", 6: "Person", 7: "no_helmet", 8: "no_goggle",
           9: "no_gloves", 10: "no_boots"}


def clases_de(ruta_txt):
    ids = set()
    with open(ruta_txt, encoding="utf-8") as f:
        for ln in f:
            partes = ln.split()
            if len(partes) == 5:
                ids.add(int(partes[0]))
    return ids


def cajas_por_clase(carpeta_lbls):
    conteo = collections.Counter()
    for nombre in os.listdir(carpeta_lbls):
        if not nombre.endswith(".txt"):
            continue
        with open(os.path.join(carpeta_lbls, nombre), encoding="utf-8") as f:
            for ln in f:
                partes = ln.split()
                if len(partes) == 5:
                    conteo[int(partes[0])] += 1
    return conteo


def main():
    # regenerar dataset_v3 (artefacto derivado)
    if os.path.exists(V3):
        shutil.rmtree(V3)
    os.makedirs(V3_TRAIN_IMG)
    os.makedirs(V3_TRAIN_LBL)

    stats = {"originales": 0, "rep1": 0, "rep2": 0}
    for nombre_jpg in sorted(os.listdir(V2_TRAIN_IMG)):
        if not nombre_jpg.lower().endswith(".jpg"):
            continue
        base = os.path.splitext(nombre_jpg)[0]
        ruta_lbl = os.path.join(V2_TRAIN_LBL, base + ".txt")
        ids = clases_de(ruta_lbl)

        # copia original (siempre)
        shutil.copy2(os.path.join(V2_TRAIN_IMG, nombre_jpg),
                     os.path.join(V3_TRAIN_IMG, nombre_jpg))
        shutil.copy2(ruta_lbl, os.path.join(V3_TRAIN_LBL, base + ".txt"))
        stats["originales"] += 1

        # replicacion por contenido
        copias_extra = 0
        if ids & NO_IDS:
            copias_extra += 1
        if NO_BOOTS_ID in ids:
            copias_extra += 1
        for k in range(1, copias_extra + 1):
            sufijo = f"__rep{k}"
            shutil.copy2(os.path.join(V2_TRAIN_IMG, nombre_jpg),
                         os.path.join(V3_TRAIN_IMG, base + sufijo + ".jpg"))
            shutil.copy2(ruta_lbl,
                         os.path.join(V3_TRAIN_LBL, base + sufijo + ".txt"))
            stats[f"rep{k}"] += 1

    # verificacion: alineacion imagen<->etiqueta en dataset_v3
    jpgs = {os.path.splitext(f)[0] for f in os.listdir(V3_TRAIN_IMG)}
    txts = {os.path.splitext(f)[0] for f in os.listdir(V3_TRAIN_LBL)}
    assert jpgs == txts, "desalineacion imagen/etiqueta en dataset_v3"

    # cajas por clase antes (v2) y despues (v3)
    antes = cajas_por_clase(V2_TRAIN_LBL)
    despues = cajas_por_clase(V3_TRAIN_LBL)

    # dataset.yaml: train apunta a dataset_v3; val/test a dataset_v2 (intactos)
    yaml_text = (
        f"# Generado por eda/07_oversampling_dataset_v3.py — Fase 2 (13-oct-2026)\n"
        f"# train OVERSAMPLEADO (+1 copia por img con no_*, +1 extra por no_boots)\n"
        f"# val y test = dataset_v2 oficiales, INTACTOS (comparacion justa)\n"
        f"path: {BASE.replace(os.sep, '/')}\n"
        f"train: dataset_v3/images/train\n"
        f"val: dataset_v2/images/val\n"
        f"test: dataset_v2/images/test\n"
        f"names:\n"
    )
    for i in range(11):
        yaml_text += f"  {i}: {NOMBRES[i]}\n"
    with open(os.path.join(V3, "dataset.yaml"), "w", encoding="utf-8") as f:
        f.write(yaml_text)

    resumen = {
        "politica": "imagenes con clases no_* (ids 7-10) reciben +1 copia; "
                    "con no_boots (id 10) +1 copia adicional; val/test intactos",
        "imagenes_train": stats,
        "total_train_v3": sum(stats.values()),
        "cajas_por_clase_v2_train": {NOMBRES[i]: antes.get(i, 0) for i in range(11)},
        "cajas_por_clase_v3_train": {NOMBRES[i]: despues.get(i, 0) for i in range(11)},
        "factor_por_clase": {
            NOMBRES[i]: round(despues.get(i, 0) / antes.get(i, 1), 3)
            for i in range(11)
        },
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nResumen guardado en: {OUT_JSON}")
    print(f"dataset.yaml v3: {os.path.join(V3, 'dataset.yaml')}")


if __name__ == "__main__":
    main()
