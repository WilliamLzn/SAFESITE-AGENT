"""EDA SafeSite-Agent — Paso 1: perfil del NDJSON (solo lectura).

Metodologia: skill `exploratory-data-analysis` (K-Dense).
- Datos crudos: SOLO LECTURA. No se modifica el NDJSON.
- Salidas: agregados acotados a consola (identificadores sanitizados).
- Alcance: TODOS los registros del archivo (sin truncamiento).
"""
import collections
import json

PATH = r"C:\Users\Lenovo\Documents\IA\SAFESITE-AGENT\construction-ppe.ndjson"
MAX_LIST = 3  # limite de elementos mostrados por lista


def show(obj, indent=0):
    """Representacion acotada de la estructura de un registro."""
    pad = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                print(f"{pad}{k}:")
                show(v, indent + 1)
            else:
                s = str(v)
                trunc = s[:60] + "..." if len(s) > 60 else s
                print(f"{pad}{k}: {trunc}")
    elif isinstance(obj, list):
        print(f"{pad}[{len(obj)} elementos]")
        for item in obj[:MAX_LIST]:
            show(item, indent + 1)
        if len(obj) > MAX_LIST:
            print(f"{pad}  ... (+{len(obj) - MAX_LIST} mas)")
    else:
        print(f"{pad}{obj}")


def main():
    n = 0
    types = collections.Counter()
    keys_seen = collections.Counter()
    first_image = None
    with open(PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n += 1
            types[rec.get("type")] += 1
            for k in rec:
                keys_seen[k] += 1
            if first_image is None and rec.get("type") == "image":
                first_image = rec

    print("registros totales:", n)
    print("por tipo:", dict(types))
    print("campos vistos:", dict(keys_seen))
    print()
    print("--- estructura del primer registro type=image (valores truncados) ---")
    show(first_image)


if __name__ == "__main__":
    main()
