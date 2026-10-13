"""EDA SafeSite-Agent — Paso 2: analisis de etiquetas, splits e integridad.

Metodologia: skill `exploratory-data-analysis` (K-Dense).
- Datos crudos: SOLO LECTURA (NDJSON, .txt de train/, .jpg listados).
- Salidas derivadas: JSON de resumen en eda/salidas/ (se crean, no se sobreescriben datos crudos).
- Alcance: totalidad de los registros NDJSON y de los archivos .txt de train/.
"""
import collections
import json
import os

BASE = r"C:\Users\Lenovo\Documents\IA\SAFESITE-AGENT"
NDJSON = os.path.join(BASE, "construction-ppe.ndjson")
TRAIN_DIR = os.path.join(BASE, "safesite_dataset", "train")
TEST_DIR = os.path.join(BASE, "safesite_dataset", "test")
OUT_DIR = os.path.join(BASE, "eda", "salidas")
TOL = 1e-4  # tolerancia numerica para validacion de rangos


def stats(vals):
    """Estadisticos de resumen para una lista de numeros."""
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
        "n": n,
        "min": s[0],
        "p25": pct(25),
        "mediana": pct(50),
        "p75": pct(75),
        "max": s[-1],
        "media": round(mean, 6),
        "sd": round(var ** 0.5, 6),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---------- 1. Perfil del NDJSON ----------
    dataset_rec = None
    images = []
    with open(NDJSON, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") == "dataset":
                dataset_rec = rec
            elif rec.get("type") == "image":
                images.append(rec)

    raw_names = dataset_rec.get("class_names", {}) if dataset_rec else {}
    if isinstance(raw_names, dict):
        class_names = [raw_names[str(i)] for i in range(len(raw_names))]
    else:
        class_names = list(raw_names)

    def nombre_clase(i):
        return class_names[i] if 0 <= i < len(class_names) else f"clase_{i}"
    split_oficial = collections.Counter(r.get("split") for r in images)
    dims = collections.Counter((r.get("width"), r.get("height")) for r in images)

    # Cajas en NDJSON
    total_boxes = 0
    boxes_por_clase = collections.Counter()
    boxes_por_imagen = []
    fuera_rango_centro = 0  # x-w/2<0, y-h/2<0, x+w/2>1, y+h/2>1 (formato YOLO centro)
    fuera_rango_esquina = 0  # x+w>1, y+h>1 (formato esquina) -> distinguir formato
    valores_negativos = 0
    ancho_cero = 0
    areas = []
    anchos = []
    altos = []
    contencion_casco_persona = {"dentro": 0, "fuera": 0}
    for r in images:
        boxes = r.get("annotations", {}).get("boxes", [])
        boxes_por_imagen.append(len(boxes))
        idx_persona = None
        for b in boxes:
            cls, x, y, w, h = b
            total_boxes += 1
            boxes_por_clase[int(cls)] += 1
            if x < 0 or y < 0 or w < 0 or h < 0:
                valores_negativos += 1
            if w == 0 or h == 0:
                ancho_cero += 1
            if (x - w / 2 < -TOL or y - h / 2 < -TOL
                    or x + w / 2 > 1 + TOL or y + h / 2 > 1 + TOL):
                fuera_rango_centro += 1
            if x + w > 1 + TOL or y + h > 1 + TOL:
                fuera_rango_esquina += 1
            areas.append(w * h)
            anchos.append(w)
            altos.append(h)
            if int(cls) == 6:
                idx_persona = (x, y, w, h)
        # prueba de contencion: casco dentro de la caja Persona (formato centro)
        if idx_persona is not None:
            px, py, pw, ph = idx_persona
            for b in boxes:
                if int(b[0]) == 0:  # helmet
                    hx, hy = b[1], b[2]
                    if (px - pw / 2 - TOL <= hx <= px + pw / 2 + TOL
                            and py - ph / 2 - TOL <= hy <= py + ph / 2 + TOL):
                        contencion_casco_persona["dentro"] += 1
                    else:
                        contencion_casco_persona["fuera"] += 1

    # ---------- 2. Split del proyecto (carpetas) vs split oficial ----------
    ndjson_por_archivo = {r["file"]: r for r in images}
    train_files = {f for f in os.listdir(TRAIN_DIR) if f.lower().endswith(".jpg")}
    test_files = {f for f in os.listdir(TEST_DIR) if f.lower().endswith(".jpg")}
    cruzado = collections.Counter()
    for fname in train_files:
        cruzado[("proyecto_train", ndjson_por_archivo.get(fname, {}).get("split", "ausente"))] += 1
    for fname in test_files:
        cruzado[("proyecto_test", ndjson_por_archivo.get(fname, {}).get("split", "ausente"))] += 1
    duplicados_entre_carpetas = len(train_files & test_files)
    archivos_ndjson = set(ndjson_por_archivo)
    faltantes_descarga = len(archivos_ndjson - train_files - test_files)
    extra_en_disco = len((train_files | test_files) - archivos_ndjson)

    # ---------- 3. Etiquetas YOLO en disco (train/) ----------
    train_txt = {f[:-4] for f in os.listdir(TRAIN_DIR) if f.lower().endswith(".txt")}
    train_bases = {f[:-4] for f in train_files}
    imgs_sin_label = train_bases - train_txt
    labels_sin_img = train_txt - train_bases

    clases_disco = collections.Counter()
    cajas_disco_total = 0
    cajas_por_img_disco = []
    areas_disco = []
    tamano_disco = []
    lineas_mal_formadas = 0
    fuera_rango_disco = 0
    discrepancias_ndjson = 0
    for base in sorted(train_txt):
        ruta = os.path.join(TRAIN_DIR, base + ".txt")
        with open(ruta, encoding="utf-8") as f:
            lineas = [ln for ln in f.read().splitlines() if ln.strip()]
        cajas_por_img_disco.append(len(lineas))
        cajas_disco_total += len(lineas)
        tamano_disco.append(os.path.getsize(ruta))
        cajas_ndjson = ndjson_por_archivo.get(base + ".jpg", {}).get(
            "annotations", {}).get("boxes", [])
        filas_disco = []
        for ln in lineas:
            partes = ln.split()
            if len(partes) != 5:
                lineas_mal_formadas += 1
                continue
            try:
                cls = int(partes[0])
                x, y, w, h = (float(partes[1]), float(partes[2]),
                              float(partes[3]), float(partes[4]))
            except ValueError:
                lineas_mal_formadas += 1
                continue
            filas_disco.append([cls, x, y, w, h])
            clases_disco[cls] += 1
            areas_disco.append(w * h)
            if (x < -TOL or y < -TOL or x > 1 + TOL or y > 1 + TOL
                    or w < -TOL or h < -TOL or w > 1 + TOL or h > 1 + TOL
                    or x - w / 2 < -TOL or y - h / 2 < -TOL
                    or x + w / 2 > 1 + TOL or y + h / 2 > 1 + TOL):
                fuera_rango_disco += 1
        # verificacion 1:1 contra NDJSON (con redondeo a 6 decimales del script)
        ref = [[int(b[0]), round(float(b[1]), 6), round(float(b[2]), 6),
                round(float(b[3]), 6), round(float(b[4]), 6)]
               for b in cajas_ndjson]
        if sorted(map(str, filas_disco)) != sorted(map(str, ref)):
            discrepancias_ndjson += 1

    resumen = {
        "dataset": {
            "nombre": dataset_rec.get("name") if dataset_rec else None,
            "version": dataset_rec.get("version") if dataset_rec else None,
            "tarea": dataset_rec.get("task") if dataset_rec else None,
            "class_names": class_names,
            "creado": dataset_rec.get("created_at") if dataset_rec else None,
        },
        "ndjson": {
            "registros_imagen": len(images),
            "split_oficial": dict(split_oficial),
            "dimensiones_unicas": {f"{w}x{h}": c for (w, h), c in dims.items()},
            "total_cajas": total_boxes,
            "cajas_por_clase": {nombre_clase(i): c
                                for i, c in sorted(boxes_por_clase.items())},
            "cajas_por_imagen": stats(boxes_por_imagen),
            "cajas_por_imagen_histograma": dict(collections.Counter(
                min(v, 20) for v in boxes_por_imagen)),
            "area_normalizada": stats(areas),
            "ancho_normalizado": stats(anchos),
            "alto_normalizado": stats(altos),
            "valores_negativos": valores_negativos,
            "cajas_dimension_cero": ancho_cero,
            "violaciones_formato_centro": fuera_rango_centro,
            "violaciones_formato_esquina": fuera_rango_esquina,
            "contencion_casco_en_persona": contencion_casco_persona,
        },
        "splits": {
            "proyecto_train_jpg": len(train_files),
            "proyecto_test_jpg": len(test_files),
            "cruzado_proyecto_vs_oficial": {
                f"{a}|oficial_{b}": c for (a, b), c in sorted(cruzado.items())},
            "duplicados_entre_carpetas": duplicados_entre_carpetas,
            "registros_ndjson_sin_descargar": faltantes_descarga,
            "jpg_en_disco_sin_registro_ndjson": extra_en_disco,
        },
        "etiquetas_disco_train": {
            "txt_totales": len(train_txt),
            "imagenes_sin_label": len(imgs_sin_label),
            "labels_sin_imagen": len(labels_sin_img),
            "cajas_totales": cajas_disco_total,
            "clases": {nombre_clase(i): c
                       for i, c in sorted(clases_disco.items())},
            "cajas_por_imagen": stats(cajas_por_img_disco),
            "area_normalizada": stats(areas_disco),
            "lineas_mal_formadas": lineas_mal_formadas,
            "valores_fuera_de_rango": fuera_rango_disco,
            "archivos_discrepantes_con_ndjson": discrepancias_ndjson,
        },
    }

    salida = os.path.join(OUT_DIR, "resumen_eda.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nResumen guardado en: {salida}")


if __name__ == "__main__":
    main()
