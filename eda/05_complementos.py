"""EDA SafeSite-Agent — Paso 5: numeros complementarios para el informe."""
import json
import os
import random

BASE = r"C:\Users\Lenovo\Documents\IA\SAFESITE-AGENT"

with open(os.path.join(BASE, "eda", "salidas", "resumen_eda.json"),
          encoding="utf-8") as f:
    eda = json.load(f)

total = eda["ndjson"]["total_cajas"]
print("--- Porcentaje por clase (NDJSON, n=11,521) ---")
for k, v in sorted(eda["ndjson"]["cajas_por_clase"].items(),
                   key=lambda kv: -kv[1]):
    print(f"  {k:<12} {v:>5}  {100 * v / total:5.2f}%")
no_total = sum(v for k, v in eda["ndjson"]["cajas_por_clase"].items()
               if k.startswith("no_"))
print(f"  TOTAL no_*    {no_total:>5}  {100 * no_total / total:5.2f}%")

print()
print("--- Train en disco: porcentaje por clase (n=9,175) ---")
tdisco = eda["etiquetas_disco_train"]
for k, v in sorted(tdisco["clases"].items(), key=lambda kv: -kv[1]):
    print(f"  {k:<12} {v:>5}  {100 * v / tdisco['cajas_totales']:5.2f}%")

# imagenes sin ninguna clase no_* en train (no aportan al objetivo del agente)
sin_no = 0
con_no = 0
train_dir = os.path.join(BASE, "safesite_dataset", "train")
for fname in os.listdir(train_dir):
    if not fname.endswith(".txt"):
        continue
    with open(os.path.join(train_dir, fname), encoding="utf-8") as f:
        cls_ids = {int(ln.split()[0]) for ln in f if ln.strip()}
    if cls_ids & {7, 8, 9, 10}:
        con_no += 1
    else:
        sin_no += 1
print(f"\n--- Imagenes train con/sin clases no_* ---")
print(f"  con al menos una clase no_*: {con_no}")
print(f"  sin ninguna clase no_*:      {sin_no}")

# conteo exacto de imagenes oscuras en la muestra (misma semilla que paso 3)
from PIL import Image
random.seed(42)
jpgs = []
for carpeta in ("train", "test"):
    d = os.path.join(BASE, "safesite_dataset", carpeta)
    jpgs += [os.path.join(d, f) for f in os.listdir(d)
             if f.lower().endswith(".jpg")]
muestra = random.sample(jpgs, 200)
brillos = []
for ruta in muestra:
    with Image.open(ruta) as im:
        h = im.convert("L").histogram()
    n_pix = sum(h)
    brillos.append(sum(i * c for i, c in enumerate(h)) / n_pix)
oscuras = [b for b in brillos if b < 60]
print(f"\n--- Muestra brillo (n={len(brillos)}, seed 42) ---")
print(f"  imagenes con brillo < 60: {len(oscuras)} "
      f"({100 * len(oscuras) / len(brillos):.1f}%)")
print(f"  imagenes con brillo < 100: "
      f"{sum(1 for b in brillos if b < 100)}")
