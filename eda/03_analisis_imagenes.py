"""EDA SafeSite-Agent — Paso 3: metadatos de imagenes + muestra acotada de pixeles.

Metodologia: skill `exploratory-data-analysis` (K-Dense).
- La inspeccion de imagenes de la skill es SOLO metadatos de contenedor (Pillow).
  La muestra de brillo/contraste va MAS ALLA de ese limite y se marca como
  exploratoria, con tamano acotado y semilla determinista (42).
- Datos crudos: SOLO LECTURA. Salidas derivadas en eda/salidas/.
- Alcance metadatos: TODAS las imagenes en disco (train + test).
  Alcance pixeles: muestra determinista de 200 imagenes (~14%).
"""
import json
import os
import random
import warnings

from PIL import Image

BASE = r"C:\Users\Lenovo\Documents\IA\SAFESITE-AGENT"
NDJSON = os.path.join(BASE, "construction-ppe.ndjson")
TRAIN_DIR = os.path.join(BASE, "safesite_dataset", "train")
TEST_DIR = os.path.join(BASE, "safesite_dataset", "test")
OUT_DIR = os.path.join(BASE, "eda", "salidas")
MUESTRA_N = 200
SEED = 42


def stats(vals):
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)

    def pct(p):
        idx = min(n - 1, max(0, int(round(p / 100 * (n - 1)))))
        return s[idx]

    mean = sum(s) / n
    var = sum((v - mean) ** 2 for v in s) / n
    return {
        "n": n, "min": round(s[0], 3), "p25": round(pct(25), 3),
        "mediana": round(pct(50), 3), "p75": round(pct(75), 3),
        "max": round(s[-1], 3), "media": round(mean, 3),
        "sd": round(var ** 0.5, 3),
    }


def main():
    # dimensiones declaradas en NDJSON
    declaradas = {}
    with open(NDJSON, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") == "image":
                declaradas[rec["file"]] = (rec["width"], rec["height"])

    resultados = {"train": [], "test": []}
    mismatch_dimension = 0
    no_abre = 0
    jpg_train, jpg_test = [], []
    for split, carpeta in (("train", TRAIN_DIR), ("test", TEST_DIR)):
        for fname in sorted(os.listdir(carpeta)):
            if not fname.lower().endswith(".jpg"):
                continue
            ruta = os.path.join(carpeta, fname)
            kb = round(os.path.getsize(ruta) / 1024, 1)
            try:
                with Image.open(ruta) as im:
                    ancho, alto = im.size
                    modo, formato = im.mode, im.format
            except Exception:
                no_abre += 1
                continue
            if declaradas.get(fname) != (ancho, alto):
                mismatch_dimension += 1
            resultados[split].append({
                "archivo": fname, "ancho": ancho, "alto": alto,
                "kb": kb, "modo": modo, "formato": formato,
            })
            (jpg_train if split == "train" else jpg_test).append(ruta)

    # ---------- muestra acotada de pixeles (exploratoria) ----------
    print(f"Calculando brillo/contraste en muestra determinista de {MUESTRA_N} imagenes...")
    random.seed(SEED)
    muestra = random.sample(jpg_train + jpg_test, MUESTRA_N)
    brillos, contrastes, saturaciones = [], [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for ruta in muestra:
            try:
                with Image.open(ruta) as im:
                    gris = im.convert("L")
                    hist = gris.histogram()
                n_pix = sum(hist)
                media = sum(i * c for i, c in enumerate(hist)) / n_pix
                var = sum((i - media) ** 2 * c for i, c in enumerate(hist)) / n_pix
                brillos.append(round(media, 1))
                contrastes.append(round(var ** 0.5, 1))
            except Exception:
                continue

    todos = resultados["train"] + resultados["test"]
    resumen = {
        "alcance_metadatos": f"TODAS las imagenes en disco (train={len(resultados['train'])}, test={len(resultados['test'])})",
        "alcance_pixeles": f"MUESTRA determinista seed={SEED}, n={MUESTRA_N} (~14%) - EXPLORATORIO",
        "imagenes_que_no_abren": no_abre,
        "formato": dict(sorted(
            (f"{r['formato']}", sum(1 for x in todos if x["formato"] == r["formato"]))
            for r in todos)) if todos else {},
        "modo_color": dict(sorted(
            (f"{r['modo']}", sum(1 for x in todos if x["modo"] == r["modo"]))
            for r in todos)) if todos else {},
        "mismatch_dimension_vs_ndjson": mismatch_dimension,
        "dimensiones_mas_comunes": {},
        "tamanos_kb": stats([r["kb"] for r in todos]),
        "resolucion_ancho_px": stats([r["ancho"] for r in todos]),
        "resolucion_alto_px": stats([r["alto"] for r in todos]),
        "relaciones_aspecto": {},
        "muestra_brillo_0_255": stats(brillos),
        "muestra_contraste_sd_gris": stats(contrastes),
    }
    from collections import Counter
    dims = Counter(f"{r['ancho']}x{r['alto']}" for r in todos)
    resumen["dimensiones_mas_comunes"] = dict(dims.most_common(10))
    ar = Counter(round(r["ancho"] / r["alto"], 2) for r in todos)
    resumen["relaciones_aspecto"] = dict(ar.most_common(8))

    salida = os.path.join(OUT_DIR, "resumen_imagenes.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nResumen guardado en: {salida}")


if __name__ == "__main__":
    main()
