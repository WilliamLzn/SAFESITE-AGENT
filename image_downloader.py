import json
import os
import random
import requests

# 1. Configuración de rutas
archivo_ndjson = 'construction-ppe.ndjson'
carpeta_base = 'safesite_dataset'
carpeta_train = os.path.join(carpeta_base, 'train')
carpeta_test = os.path.join(carpeta_base, 'test')

os.makedirs(carpeta_train, exist_ok=True)
os.makedirs(carpeta_test, exist_ok=True)

imagenes = []

# 2. Leer registros
with open(archivo_ndjson, 'r', encoding='utf-8') as f:
    for linea in f:
        datos = json.loads(linea.strip())
        if datos.get('type') == 'image':
            imagenes.append(datos)

# 3. Mezclar y particionar (80/20)
random.seed(42)
random.shuffle(imagenes)
corte = int(len(imagenes) * 0.8)

# 4. Función de descarga y generación de etiquetas YOLO
def procesar_lote(lista_imgs, ruta_destino, generar_labels, nombre_lote):
    print(f"\n--- Procesando {nombre_lote} ({len(lista_imgs)} imágenes) ---")
    for img in lista_imgs:
        url = img.get('url')
        nombre_archivo = img.get('file')
        nombre_base = os.path.splitext(nombre_archivo)[0]
        ruta_img = os.path.join(ruta_destino, nombre_archivo)
        ruta_txt = os.path.join(ruta_destino, f"{nombre_base}.txt")
        
        if url:
            try:
                # Descargar imagen
                respuesta = requests.get(url, stream=True, timeout=10)
                if respuesta.status_code == 200:
                    with open(ruta_img, 'wb') as img_file:
                        for chunk in respuesta.iter_content(1024):
                            img_file.write(chunk)
                    
                    # Generar archivo .txt solo si generar_labels es True (Train)
                    if generar_labels:
                        cajas = img.get('annotations', {}).get('boxes', [])
                        with open(ruta_txt, 'w', encoding='utf-8') as txt_file:
                            for caja in cajas:
                                # caja = [clase, x, y, width, height]
                                linea = f"{caja[0]} {caja[1]:.6f} {caja[2]:.6f} {caja[3]:.6f} {caja[4]:.6f}\n"
                                txt_file.write(linea)
                                
                    print(f"[{nombre_lote}] OK: {nombre_archivo}")
            except Exception as e:
                print(f"[{nombre_lote}] Error en {nombre_archivo}: {e}")

# 5. Ejecutar: Train CON etiquetas, Test SIN etiquetas
procesar_lote(imagenes[:corte], carpeta_train, generar_labels=True, nombre_lote="TRAIN")
procesar_lote(imagenes[corte:], carpeta_test, generar_labels=False, nombre_lote="TEST")