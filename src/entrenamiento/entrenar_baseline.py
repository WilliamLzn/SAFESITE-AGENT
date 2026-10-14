"""Fase 1 — Entrenamiento baseline YOLOv8n (SafeSite-Agent).

Practicas MLOps de la skill pytorch-lightning aplicadas al pipeline Ultralytics:
- semilla fija (42), config guardada por run (args.yaml del run dir),
- checkpoints best.pt/last.pt, early stopping (patience), tracking CSV por epoca
  (results.csv) y metricas por clase al finalizar.

Uso (desde la raiz del proyecto):
    .venv\\Scripts\\python.exe src\\entrenamiento\\entrenar_baseline.py
    .venv\\Scripts\\python.exe src\\entrenamiento\\entrenar_baseline.py --batch 16
"""
import argparse
import json
import os

from ultralytics import YOLO

BASE = r"C:\Users\Lenovo\Documents\IA\SAFESITE-AGENT"
DATASET_YAML = os.path.join(BASE, "dataset_v2", "dataset.yaml")
SALIDAS = os.path.join(BASE, "eda", "salidas")
SEED = 42


def extraer_metricas(metricas):
    """Serializa las metricas de validacion de ultralytics (global + por clase)."""
    box = metricas.box
    # Fix E29: antes se hacia `names.values()` y `i in nombres` (int entre strings)
    # -> siempre caia al fallback clase_{i}. Normalizar a dict {int: nombre}.
    nombres_raw = getattr(metricas, "names", None) or {}
    if hasattr(nombres_raw, "items"):
        nombres = {}
        for k, v in nombres_raw.items():
            try:
                nombres[int(k)] = v
            except (TypeError, ValueError):
                pass
    elif isinstance(nombres_raw, (list, tuple)):
        nombres = dict(enumerate(nombres_raw))
    else:
        nombres = {}
    por_clase = {}
    ap50 = list(box.ap50)
    ap5095 = list(box.ap)
    for idx_cls in box.ap_class_index:
        i = int(idx_cls)
        clave = nombres.get(i, f"clase_{i}")
        por_clase[clave] = {
            "AP50": round(ap50[i], 4) if i < len(ap50) else None,
            "AP50-95": round(ap5095[i], 4) if i < len(ap5095) else None,
        }
    return {
        "mAP50": round(float(metricas.box.map50), 4),
        "mAP50-95": round(float(metricas.box.map), 4),
        "precision": round(float(metricas.box.mp), 4),
        "recall": round(float(metricas.box.mr), 4),
        "por_clase": por_clase,
    }


def main():
    parser = argparse.ArgumentParser(description="Entrena el baseline de SafeSite")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--name", default="baseline_v1")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=0,
                        help="0 por defecto: en Windows los workers re-importan "
                             "torch/CUDA DLLs y pueden agotar el commit "
                             "(WinError 1455, ver BITACORA E15)")
    parser.add_argument("--data", default=DATASET_YAML,
                        help="ruta al dataset.yaml (default: dataset_v2; "
                             "Fase 2 usa dataset_v3/dataset.yaml con oversampling)")
    parser.add_argument("--hsv-v", type=float, default=0.4,
                        help="jitter de brillo (V) del HSV augmentation "
                             "(default ultralytics 0.4; Fase 2 usa 0.5 por "
                             "las imagenes oscuras del EDA F9)")
    args = parser.parse_args()

    run_dir = os.path.join(BASE, "runs", "safesite", args.name)
    if os.path.exists(run_dir):
        raise SystemExit(f"El run '{run_dir}' ya existe. Usa --name <nuevo_nombre>.")

    model = YOLO(args.model)
    model.train(
        data=args.data,
        hsv_v=args.hsv_v,
        epochs=args.epochs,
        patience=args.patience,
        imgsz=args.imgsz,
        batch=args.batch,
        seed=SEED,
        device=args.device,
        workers=args.workers,
        project=os.path.join(BASE, "runs", "safesite"),
        name=args.name,
        val=True,
        plots=True,
        verbose=True,
    )

    best = getattr(model.trainer, "best", None)
    print(f"\nCheckpoint best: {best}")

    # evaluacion con best.pt sobre val y test (metricas por clase incluidas)
    mejor = YOLO(best)
    resumen = {"run": args.name, "best_checkpoint": str(best),
               "config": vars(args)}
    for split in ("val", "test"):
        print(f"\n===== Evaluacion en split {split.upper()} =====")
        metricas = mejor.val(data=args.data, split=split, plots=False)
        resumen[split] = extraer_metricas(metricas)
        print(json.dumps(resumen[split], ensure_ascii=False, indent=2))

    salida = os.path.join(SALIDAS, f"metricas_{args.name}.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(f"\nResumen de metricas guardado en: {salida}")
    print(f"Historial por epoca: {os.path.join(run_dir, 'results.csv')}")


if __name__ == "__main__":
    main()
