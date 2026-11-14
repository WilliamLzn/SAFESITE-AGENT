#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de badges QR para SAFESITE v2.

Lee data/nomina/empleados.csv y genera un PNG de QR por cada badge,
listo para imprimir y recortar. También genera una hoja de contacto
(contact sheet) con todos los QRs en una sola pagina A4 para imprimir
de una sola vez.

El contenido de cada QR es un registro simple con pipe (|) para que el
lector de la v2 pueda parsearlo facilmente:
    SAFESITE|BDG-001|EMP-001|supervisor_hse|MANANA|activo

Uso:
    .venv\Scripts\python.exe scripts\generar_qr_badges.py
"""

import csv
import json
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
EMPLEADOS_CSV = RAIZ / "data" / "nomina" / "empleados.csv"
BADGES_DIR = RAIZ / "badges"
CONTACT_SHEET = RAIZ / "badges" / "hoja_contacto_badges.png"

# ---- configuracion de impresion ----
QR_SIZE_PX = 700            # tamaño de cada QR en pixeles (buena resolucion para imprimir)
BORDER_PX = 40              # borde blanco alrededor del QR
LABEL_HEIGHT_PX = 90        # alto del area de texto debajo de cada QR
SHEET_COLS = 3              # columnas en la hoja de contacto
SHEET_ROWS = 10             # filas en la hoja de contacto (ajustable)


def leer_empleados(ruta_csv):
    """Lee empleados.csv y devuelve lista de dict."""
    with open(ruta_csv, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def generar_qr(contenido, size_px=QR_SIZE_PX):
    """Genera una imagen PIL con el QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # alta tolerancia a daños
        box_size=10,
        border=4,
    )
    qr.add_data(contenido)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img_qr = img_qr.resize((size_px, size_px), Image.Resampling.LANCZOS)
    return img_qr


def hacer_tarjeta(empleado, size_px=QR_SIZE_PX):
    """Crea una tarjeta individual: QR + datos del empleado impresos."""
    badge = empleado["badge"]
    nombre = empleado.get("nombre", empleado["id_empleado"])
    puesto = empleado.get("puesto", "")
    turno = empleado.get("id_turno", "")
    estado = empleado.get("estado_badge", "")

    contenido = f"SAFESITE|{badge}|{empleado['id_empleado']}|{nombre}|{puesto}|{turno}|{estado}"

    qr_img = generar_qr(contenido, size_px)

    # Tarjeta: QR arriba, texto abajo
    tarjeta_w = size_px + 2 * BORDER_PX
    tarjeta_h = size_px + 2 * BORDER_PX + LABEL_HEIGHT_PX
    tarjeta = Image.new("RGB", (tarjeta_w, tarjeta_h), "white")
    draw = ImageDraw.Draw(tarjeta)

    # Pegar QR centrado
    qr_x = BORDER_PX
    qr_y = BORDER_PX
    tarjeta.paste(qr_img, (qr_x, qr_y))

    # Texto: badge grande
    try:
        font_bold = ImageFont.truetype("arialbd.ttf", 36)
        font_normal = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font_bold = ImageFont.load_default()
        font_normal = ImageFont.load_default()

    draw.text((BORDER_PX, size_px + 2 * BORDER_PX + 10), badge, fill="black", font=font_bold)
    draw.text((BORDER_PX, size_px + 2 * BORDER_PX + 50), f"{empleado['id_empleado']} - {nombre}", fill="black", font=font_normal)
    draw.text((BORDER_PX, size_px + 2 * BORDER_PX + 85), f"{puesto} | Turno: {turno} | {estado}", fill="gray", font=font_normal)

    return tarjeta, contenido


def generar_hoja_contacto(tarjetas, ruta_salida, cols=SHEET_COLS, filas=SHEET_ROWS):
    """Genera una hoja con todas las tarjetas para imprimir de una vez."""
    if not tarjetas:
        return

    # Usar el tamaño de la primera tarjeta
    tarjeta_w, tarjeta_h = tarjetas[0].size
    gap = 30  # espacio entre tarjetas
    margen = 40

    filas_necesarias = (len(tarjetas) + cols - 1) // cols
    sheet_w = margen * 2 + tarjeta_w * cols + gap * (cols - 1)
    sheet_h = margen * 2 + tarjeta_h * filas_necesarias + gap * (filas_necesarias - 1)

    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)

    try:
        font_titulo = ImageFont.truetype("arialbd.ttf", 40)
    except Exception:
        font_titulo = ImageFont.load_default()

    draw.text((margen, 20), "SAFESITE v2 - Badges QR para imprimir", fill="black", font=font_titulo)
    draw.text((margen, 70), "Recortar cada tarjeta y plastificar. Escanear con la camara del sistema.", fill="gray", font=ImageFont.load_default())

    for i, tarjeta in enumerate(tarjetas):
        fila = i // cols
        col = i % cols
        x = margen + col * (tarjeta_w + gap)
        y = 120 + fila * (tarjeta_h + gap)
        sheet.paste(tarjeta, (x, y))

    sheet.save(ruta_salida, dpi=(300, 300))
    print(f"[OK] Hoja de contacto guardada en: {ruta_salida} ({sheet_w}x{sheet_h} px)")


def main():
    empleados = leer_empleados(EMPLEADOS_CSV)
    print(f"[INFO] {len(empleados)} empleados leídos de {EMPLEADOS_CSV}")

    BADGES_DIR.mkdir(parents=True, exist_ok=True)

    tarjetas = []
    for emp in empleados:
        badge = emp["badge"]
        tarjeta, contenido = hacer_tarjeta(emp)
        nombre_archivo = f"badge_{badge}.png"
        ruta_png = BADGES_DIR / nombre_archivo
        tarjeta.save(ruta_png, dpi=(300, 300))
        tarjetas.append(tarjeta)
        print(f"[OK] {nombre_archivo} <- {contenido}")

    # Hoja de contacto para imprimir todo de una vez
    generar_hoja_contacto(tarjetas, CONTACT_SHEET)

    print(f"\n[INFO] Total: {len(tarjetas)} badges generados en {BADGES_DIR}")
    print(f"[INFO] Hoja de contacto: {CONTACT_SHEET}")


if __name__ == "__main__":
    main()
