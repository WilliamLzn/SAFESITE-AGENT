"""EDA SafeSite-Agent — Paso 4: generacion de figuras (matplotlib).

Metodologia: skill `exploratory-data-analysis` (K-Dense) — los hallazgos
post-hoc se marcan como EXPLORATORIOS; las figuras muestran agregados.
Entradas: eda/salidas/resumen_eda.json y resumen_imagenes.json (derivados).
Salidas: eda/figuras/*.png (no se tocan los datos crudos).
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = r"C:\Users\Lenovo\Documents\IA\SAFESITE-AGENT"
SALIDAS = os.path.join(BASE, "eda", "salidas")
FIGURAS = os.path.join(BASE, "eda", "figuras")

plt.rcParams.update({
    "figure.dpi": 130, "font.size": 9, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
})
AZUL = "#2563eb"
ROJO = "#dc2626"
GRIS = "#9ca3af"
VERDE = "#16a34a"


def main():
    os.makedirs(FIGURAS, exist_ok=True)
    with open(os.path.join(SALIDAS, "resumen_eda.json"), encoding="utf-8") as f:
        eda = json.load(f)
    with open(os.path.join(SALIDAS, "resumen_imagenes.json"), encoding="utf-8") as f:
        imgs = json.load(f)

    # ---- Figura 1: distribucion de clases (NDJSON completo) ----
    clases = eda["ndjson"]["cajas_por_clase"]
    nombres = list(clases)
    valores = [clases[k] for k in nombres]
    colores = [ROJO if k.startswith("no_") else
               (GRIS if k in ("none",) else AZUL) for k in nombres]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    barras = ax.bar(nombres, valores, color=colores)
    ax.bar_label(barras, fmt="%d", padding=2, fontsize=8)
    ax.set_title("Fig 1. Cajas por clase — dataset completo NDJSON (n=11,521)")
    ax.set_ylabel("cajas")
    ax.tick_params(axis="x", rotation=30)
    ax.annotate("clases no_* (incumplimiento)", xy=(0.01, 0.92),
                xycoords="axes fraction", color=ROJO, fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURAS, "fig1_clases.png"))
    plt.close(fig)

    # ---- Figura 2: cajas por imagen ----
    hist = eda["ndjson"]["cajas_por_imagen_histograma"]
    ks = sorted(int(k) for k in hist)
    vs = [hist[str(k)] if str(k) in hist else hist[k] for k in ks]
    etiquetas = [">=20" if k == 20 else str(k) for k in ks]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(etiquetas, vs, color=AZUL)
    ax.set_title("Fig 2. Numero de objetos por imagen (1,416 imagenes)")
    ax.set_ylabel("imagenes")
    ax.set_xlabel("objetos por imagen (mediana = 7, max = 58)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURAS, "fig2_cajas_por_imagen.png"))
    plt.close(fig)

    # ---- Figura 3: split proyecto vs oficial ----
    cruzado = eda["splits"]["cruzado_proyecto_vs_oficial"]
    grupos = {"proyecto_train": {}, "proyecto_test": {}}
    for k, v in cruzado.items():
        a, b = k.split("|oficial_")
        grupos[a][b] = v
    splits_of = ["train", "val", "test"]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ancho = 0.35
    xs = range(len(splits_of))
    train_vals = [grupos["proyecto_train"].get(s, 0) for s in splits_of]
    test_vals = [grupos["proyecto_test"].get(s, 0) for s in splits_of]
    b1 = ax.bar([x - ancho / 2 for x in xs], train_vals, ancho,
                label="carpeta train/ (1,129)", color=AZUL)
    b2 = ax.bar([x + ancho / 2 for x in xs], test_vals, ancho,
                label="carpeta test/ (284)", color=GRIS)
    ax.bar_label(b1, fmt="%d", fontsize=8, padding=2)
    ax.bar_label(b2, fmt="%d", fontsize=8, padding=2)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([f"oficial {s}" for s in splits_of])
    ax.set_title("Fig 3. Contaminacion del split: carpeta del proyecto vs split oficial NDJSON")
    ax.set_ylabel("imagenes")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURAS, "fig3_splits.png"))
    plt.close(fig)

    # ---- Figura 4: areas normalizadas de cajas (train en disco) ----
    # reutilizamos percentiles del JSON: reconstruimos aproximacion por cuantiles
    a = eda["etiquetas_disco_train"]["area_normalizada"]
    import numpy as np
    cuantiles = np.linspace(0, 100, 101)
    valores = np.percentile(
        np.random.default_rng(42).beta(2, 10, 100000) * 0 + 0, [0])  # placeholder
    # mejor: leer las areas reales desde los .txt de train
    areas = []
    train_dir = os.path.join(BASE, "safesite_dataset", "train")
    for fname in os.listdir(train_dir):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(train_dir, fname), encoding="utf-8") as f:
            for ln in f:
                p = ln.split()
                if len(p) == 5:
                    w, h = float(p[3]), float(p[4])
                    areas.append(w * h)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.hist(areas, bins=60, color=AZUL, edgecolor="white", linewidth=0.3)
    ax.set_yscale("log")
    ax.set_title("Fig 4. Distribucion del area de las cajas (train/, 9,175 cajas)")
    ax.set_xlabel("area normalizada (w x h)")
    ax.set_ylabel("cajas (escala log)")
    ax.axvline(a["mediana"], color=ROJO, linestyle="--", linewidth=1.2,
               label=f"mediana = {a['mediana']:.4f}")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURAS, "fig4_areas.png"))
    plt.close(fig)

    # ---- Figura 5: dimensiones de imagen en disco ----
    dims = imgs["dimensiones_mas_comunes"]
    nombres_d = list(dims)[:6]
    otros = sum(v for k, v in dims.items() if k not in nombres_d)
    etiquetas_d = nombres_d + ["otras"]
    valores_d = [dims[k] for k in nombres_d] + [otros]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    barras = ax.bar(etiquetas_d, valores_d, color=VERDE)
    ax.bar_label(barras, fmt="%d", fontsize=8, padding=2)
    ax.set_title("Fig 5. Resoluciones mas comunes en disco (1,413 imagenes)")
    ax.set_ylabel("imagenes")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURAS, "fig5_dimensiones.png"))
    plt.close(fig)

    # ---- Figura 6: brillo de la muestra (exploratorio) ----
    b = imgs["muestra_brillo_0_255"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    rng = np.random.default_rng(42)
    # aproximacion no parametrica no disponible: releer muestra para histograma
    import random as _r
    from PIL import Image
    _r.seed(42)
    jpgs = []
    for carpeta in ("train", "test"):
        d = os.path.join(BASE, "safesite_dataset", carpeta)
        jpgs += [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jpg")]
    muestra = _r.sample(jpgs, 200)
    brillos = []
    for ruta in muestra:
        try:
            with Image.open(ruta) as im:
                gris = im.convert("L")
                hist_ = gris.histogram()
            n_pix = sum(hist_)
            brillos.append(sum(i * c for i, c in enumerate(hist_)) / n_pix)
        except Exception:
            continue
    ax.hist(brillos, bins=25, color=AZUL, edgecolor="white", linewidth=0.3)
    ax.axvline(60, color=ROJO, linestyle="--", linewidth=1.2,
               label="umbral ~ oscuro (60)")
    ax.set_title("Fig 6. Brillo medio por imagen — MUESTRA n=200 (EXPLORATORIO)")
    ax.set_xlabel("brillo medio (0-255)")
    ax.set_ylabel("imagenes")
    ax.legend(frameon=False)
    oscuras = sum(1 for v in brillos if v < 60)
    ax.annotate(f"{oscuras}/{len(brillos)} imagenes oscuras (<60)",
                xy=(0.02, 0.9), xycoords="axes fraction", color=ROJO, fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURAS, "fig6_brillo.png"))
    plt.close(fig)

    print("Figuras generadas en:", FIGURAS)
    for f in sorted(os.listdir(FIGURAS)):
        print("  -", f)


if __name__ == "__main__":
    main()
