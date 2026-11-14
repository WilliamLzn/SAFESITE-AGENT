#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de badges QR estilo tarjeta de identificacion para SAFESITE v2.

Lee data/nomina/empleados.csv y genera:
  - Una hoja PNG por lote de badges (varias tarjetas por hoja, lista para imprimir)
  - Cada tarjeta es vertical: encabezado SAFESITE, QR en lugar de foto,
    nombre grande, puesto/zona de trabajo, turno, ID de badge y estado.

El contenido de cada QR es un registro pipe-separado para que el lector de
la v2 pueda parsearlo facilmente:
    SAFESITE|BDG-001|EMP-001|supervisor_hse|MANANA|activo

Uso:
    .venv\Scripts\python.exe scripts\generar_qr_badges.py
"""

import csv
import math
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
EMPLEADOS_CSV = RAIZ / "data" / "nomina" / "empleados.csv"
BADGES_DIR = RAIZ / "badges"

# ---------- configuracion de diseno ----------
DPI = 200                                   # resolucion de impresion
INCH = DPI                                  # 1 pulgada en pixeles

# Tarjeta vertical (pulgadas) -> pixeles
CARD_W_IN = 2.5
CARD_H_IN = 3.5
CARD_W = int(CARD_W_IN * INCH)              # 500 px
CARD_H = int(CARD_H_IN * INCH)              # 700 px

# Hoja A4 vertical (pulgadas) -> pixeles
SHEET_W_IN = 8.27
SHEET_H_IN = 11.69
SHEET_W = int(SHEET_W_IN * INCH)            # 1654 px
SHEET_H = int(SHEET_H_IN * INCH)            # 2338 px

MARGEN = int(0.4 * INCH)                    # margen de la hoja
GAP = int(0.15 * INCH)                      # espacio entre tarjetas

# Colores SAFESITE
COLOR_PRIMARIO = (30, 58, 138)              # azul #1E3A8A
COLOR_PRIMARIO_CLARO = (74, 108, 182)       # #4A6CB6
COLOR_FONDO = (255, 255, 255)
COLOR_TEXTO = (20, 20, 20)
COLOR_TEXTO_SEC = (100, 100, 100)
COLOR_ACTIVO = (34, 197, 94)                # verde #22C55E
COLOR_BLOQUEADO = (239, 68, 68)             # rojo #EF4444


def leer_empleados(ruta_csv):
    """Lee empleados.csv y devuelve lista de dict."""
    with open(ruta_csv, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def generar_qr(contenido, size_px=420):
    """Genera una imagen PIL con el QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(contenido)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img_qr = img_qr.resize((size_px, size_px), Image.Resampling.LANCZOS)
    return img_qr


def _fuente(tamanio, negrita=False):
    """Intenta cargar una fuente TrueType; fallback a default si falla."""
    candidatos = [
        ("arialbd.ttf" if negrita else "arial.ttf", tamanio),
        ("calibri.ttf" if negrita else "calibri.ttf", tamanio),
        ("tahoma.ttf" if negrita else "tahoma.ttf", tamanio),
    ]
    for nombre, tam in candidatos:
        try:
            return ImageFont.truetype(nombre, tam)
        except Exception:
            continue
    return ImageFont.load_default()


def hacer_tarjeta(empleado, card_w=CARD_W, card_h=CARD_H):
    """Crea una tarjeta vertical estilo business card con QR."""
    badge = empleado["badge"]
    nombre = empleado.get("nombre", empleado["id_empleado"])
    puesto = empleado.get("puesto", "")
    turno = empleado.get("id_turno", "")
    estado = empleado.get("estado_badge", "").lower()

    # Contenido del QR (formato pipe para parsear facil en la v2)
    contenido = f"SAFESITE|{badge}|{empleado['id_empleado']}|{nombre}|{puesto}|{turno}|{estado}"

    qr_img = generar_qr(contenido, size_px=400)

    tarjeta = Image.new("RGB", (card_w, card_h), COLOR_FONDO)
    draw = ImageDraw.Draw(tarjeta)

    # --- banda superior (encabezado) ---
    alto_banda = int(card_h * 0.18)
    draw.rectangle([0, 0, card_w, alto_banda], fill=COLOR_PRIMARIO)
    draw.rectangle([0, alto_banda, card_w, alto_banda + 6], fill=COLOR_PRIMARIO_CLARO)

    try:
        font_logo = _fuente(44, negrita=True)
    except Exception:
        font_logo = ImageFont.load_default()
    draw.text((card_w // 2, alto_banda // 2 - 10), "SAFESITE", fill="white",
              font=font_logo, anchor="mm")

    # --- QR centrado ---
    qr_w, qr_h = qr_img.size
    qr_x = (card_w - qr_w) // 2
    qr_y = alto_banda + int(card_h * 0.06)
    tarjeta.paste(qr_img, (qr_x, qr_y))

    # --- texto debajo del QR ---
    texto_y = qr_y + qr_h + int(card_h * 0.03)

    font_nombre = _fuente(40, negrita=True)
    font_puesto = _fuente(26)
    font_detalle = _fuente(22)

    draw.text((card_w // 2, texto_y), nombre, fill=COLOR_TEXTO,
              font=font_nombre, anchor="mm")

    draw.text((card_w // 2, texto_y + 60), puesto, fill=COLOR_TEXTO_SEC,
              font=font_puesto, anchor="mm")

    draw.text((card_w // 2, texto_y + 100), f"Turno: {turno}", fill=COLOR_TEXTO_SEC,
              font=font_detalle, anchor="mm")

    draw.text((card_w // 2, texto_y + 140), f"Badge: {badge}", fill=COLOR_TEXTO,
              font=font_detalle, anchor="mm")

    # --- banda inferior con estado ---
    alto_estado = int(card_h * 0.12)
    y_estado = card_h - alto_estado

    color_estado = COLOR_ACTIVO if estado == "activo" else COLOR_BLOQUEADO
    draw.rectangle([0, y_estado, card_w, card_h], fill=color_estado)

    font_estado = _fuente(30, negrita=True)
    estado_texto = "ACTIVO" if estado == "activo" else "BLOQUEADO"
    draw.text((card_w // 2, y_estado + alto_estado // 2), estado_texto,
              fill="white", font=font_estado, anchor="mm")

    return tarjeta, contenido


def calcular_grid(sheet_w, sheet_h, card_w, card_h, margen, gap):
    """Calcula cuantas tarjetas caben por hoja y sus posiciones."""
    cols = max(1, (sheet_w - 2 * margen + gap) // (card_w + gap))
    rows = max(1, (sheet_h - 2 * margen + gap) // (card_h + gap))
    return cols, rows


def generar_hoja(tarjetas, indice_hoja, sheet_w=SHEET_W, sheet_h=SHEET_H,
                 margen=MARGEN, gap=GAP):
    """Genera una hoja PNG con un grid de tarjetas."""
    cols, rows = calcular_grid(sheet_w, sheet_h, CARD_W, CARD_H, margen, gap)
    capacidad = cols * rows

    lote = tarjetas[indice_hoja * capacidad:(indice_hoja + 1) * capacidad]
    if not lote:
        return None, 0, 0

    sheet = Image.new("RGB", (sheet_w, sheet_h), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)

    # Titulo de la hoja
    try:
        font_titulo = _fuente(48, negrita=True)
        font_sub = _fuente(28)
    except Exception:
        font_titulo = font_sub = ImageFont.load_default()

    draw.text((margen, margen // 2), f"SAFESITE v2 - Badges QR (Hoja {indice_hoja + 1})",
              fill=COLOR_PRIMARIO, font=font_titulo)
    draw.text((margen, margen // 2 + 60), "Recortar cada tarjeta y plastificar. Escanear con la camara del sistema.",
              fill=COLOR_TEXTO_SEC, font=font_sub)

    y_inicio = margen + 140

    for i, tarjeta in enumerate(lote):
        fila = i // cols
        col = i % cols
        x = margen + col * (CARD_W + gap)
        y = y_inicio + fila * (CARD_H + gap)
        sheet.paste(tarjeta, (x, y))

    return sheet, cols, rows


def main():
    empleados = leer_empleados(EMPLEADOS_CSV)
    print(f"[INFO] {len(empleados)} empleados leídos de {EMPLEADOS_CSV}")

    BADGES_DIR.mkdir(parents=True, exist_ok=True)

    # Generar tarjetas individuales (opcional, para referencia)
    tarjetas = []
    contenidos = []
    for emp in empleados:
        tarjeta, contenido = hacer_tarjeta(emp)
        tarjetas.append(tarjeta)
        contenidos.append(contenido)
        nombre_archivo = f"badge_{emp['badge']}.png"
        ruta_png = BADGES_DIR / nombre_archivo
        tarjeta.save(ruta_png, dpi=(DPI, DPI))
        print(f"[OK] {nombre_archivo} <- {contenido}")

    # Calcular grid y cantidad de hojas
    cols, rows = calcular_grid(SHEET_W, SHEET_H, CARD_W, CARD_H, MARGEN, GAP)
    capacidad = cols * rows
    total_hojas = math.ceil(len(tarjetas) / capacidad)

    print(f"[INFO] Grid por hoja: {cols} columnas x {rows} filas = {capacidad} tarjetas/hoja")
    print(f"[INFO] Total de hojas a generar: {total_hojas}")

    hojas_generadas = []
    for i in range(total_hojas):
        sheet, c, r = generar_hoja(tarjetas, i)
        if sheet is None:
            break
        nombre_hoja = f"hoja_badges_{i + 1:02d}.png"
        ruta_hoja = BADGES_DIR / nombre_hoja
        sheet.save(ruta_hoja, dpi=(DPI, DPI))
        hojas_generadas.append(ruta_hoja)
        print(f"[OK] {nombre_hoja} ({sheet.size[0]}x{sheet.size[1]} px, {c}x{r} grid)")

    print(f"\n[INFO] Proceso completado:")
    print(f"       - {len(tarjetas)} tarjetas individuales en {BADGES_DIR}")
    print(f"       - {len(hojas_generadas)} hojas para imprimir en {BADGES_DIR}")


if __name__ == "__main__":
    main()
