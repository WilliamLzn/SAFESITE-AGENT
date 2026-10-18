/* SafeSite Agent — demo estática.
 *
 * Réplica fiel en JS del núcleo del agente (src/safesite/), con los
 * parámetros EXACTOS de src/safesite/config.py:
 *   - inferencia: conf 0.15, NMS IoU 0.5 por clase (igual que percepcion.py)
 *   - umbral por clase: no_* 0.15, positivas 0.35 (perfil evaluación)
 *   - confirmación K=3 frames, racha rota si la clase falta (razonamiento.py)
 *   - cooldown 30 s por (zona, clase)
 *   - dibujo: colores y re-anclaje de gafas de percepcion.py (E30/E34)
 * El modelo (best.onnx) se descarga una vez y corre EN EL NAVEGADOR.
 */
"use strict";

/* ---------- constantes (config.py) ---------- */
const CLASES = ["helmet", "gloves", "vest", "boots", "goggles", "none",
  "Person", "no_helmet", "no_goggle", "no_gloves", "no_boots"];
const NOMBRES_ES = { 0: "Casco", 1: "Guantes", 2: "Chaleco", 3: "Botas",
  4: "Gafas", 5: "None", 6: "Persona", 7: "SIN CASCO", 8: "SIN GAFAS",
  9: "SIN GUANTES", 10: "SIN BOTAS" };
const ES_INCUMPLIMIENTO = c => c >= 7 && c <= 10;
const UMBRAL_DEFECTO = 0.35;      // clases positivas
const UMBRAL_INC = 0.15;          // clases no_*
const K_FRAMES = 3;
const COOLDOWN_S = 30.0;
const IOU_NMS = 0.5;              // igual que percepcion.py
const FRAMES_DEMO = 4;            // la demo simula un video de 4 frames a 2 fps
const INTERVALO_S = 0.5;
const DESCRIPCION_NATURAL = {
  7: "un trabajador SIN CASCO", 8: "un trabajador SIN GAFAS de protección",
  9: "un trabajador SIN GUANTES", 10: "un trabajador SIN BOTAS de seguridad" };

/* ---------- estado de la sesión ---------- */
const ses = { verificaciones: 0, alertas: 0, framesFallidos: 0, log: [] };
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g, "&").replace(/</g, "<")
  .replace(/>/g, ">");

function log(texto) {
  const hora = new Date().toLocaleTimeString();
  ses.log.push(`[${hora}] ${texto}`);
  if (ses.log.length > 200) ses.log.shift();
}
function resumen() {
  return `Sesión: ${ses.verificaciones} imágenes procesadas, ` +
    `${ses.alertas} alertas, ${ses.framesFallidos} frames fallidos.`;
}

/* ---------- razonamiento (razonamiento.py) ---------- */
const rachas = {};          // `${zona}|${cls}` -> {n, tInicio, tUltimo, ...}
const cooldown = {};        // `${zona}|${cls}` -> t de la última alerta
const yaConfirmadas = new Set();   // claves ya confirmadas en la racha actual

function filtrarPorClase(detecciones) {
  return detecciones.filter(d =>
    d.conf >= (ES_INCUMPLIMIENTO(d.cls) ? UMBRAL_INC : UMBRAL_DEFECTO));
}

/* Devuelve los incidentes confirmados en este frame (lógica de
   razonamiento.py: racha que se rompe si la clase falta o tarda > 1 s). */
function evaluarRazonamiento(zona, t, filtradas) {
  const presentes = new Set(filtradas.filter(d => ES_INCUMPLIMIENTO(d.cls))
    .map(d => d.cls));
  const confirmados = [];
  for (const cls of presentes) {
    const clave = `${zona}|${cls}`;
    const conf = Math.max(...filtradas.filter(d => d.cls === cls).map(d => d.conf));
    let r = rachas[clave];
    if (!r || t - r.tUltimo > 1.0) {
      r = rachas[clave] = { n: 1, tInicio: t, tUltimo: t, confSuma: conf };
    } else {
      r.n += 1; r.tUltimo = t; r.confSuma += conf;
    }
    if (r.n === K_FRAMES && !yaConfirmadas.has(clave)) {
      yaConfirmadas.add(clave);
      confirmados.push({ zona, claseId: cls, clase: CLASES[cls],
        confMedia: r.confSuma / r.n, tConfirmacion: t });
    }
  }
  for (const clave of Object.keys(rachas)) {
    const [z, c] = clave.split("|");
    if (z === zona && !presentes.has(Number(c))) {
      delete rachas[clave];
      yaConfirmadas.delete(clave);
    }
  }
  return confirmados;
}

/* cooldown de la memoria (memoria.py): ¿pasa o queda suprimido? */
function permiteAlerta(incidente, t) {
  const clave = `${incidente.zona}|${incidente.claseId}`;
  if (cooldown[clave] !== undefined && t - cooldown[clave] < COOLDOWN_S)
    return false;
  cooldown[clave] = t;
  return true;
}

/* ---------- mensaje de WhatsApp (actuarios.py) ---------- */
function captionLote(incidentes) {
  const hora = new Date().toLocaleTimeString([], { hour: "numeric",
    minute: "2-digit" });
  const zona = incidentes[0].zona;
  const faltas = incidentes.map(i => DESCRIPCION_NATURAL[i.claseId] ||
    `incumplimiento de EPP (${i.clase})`);
  let resumenFaltas;
  if (incidentes.length === 1) {
    resumenFaltas = `Detectamos ${faltas[0]} en la zona ${zona}.`;
  } else {
    const lista = faltas.map(f => `• ${f.replace(/\b\w/g, m => m.toUpperCase())}`)
      .join("\n");
    resumenFaltas = `Detectamos varios incumplimientos de EPP en la zona ` +
      `${zona}:\n${lista}`;
  }
  return `🚨 Alerta SafeSite — ${hora}\n\n${resumenFaltas}\n\n` +
    `📸 Te adjuntamos la foto del momento.\n\n` +
    `_Responde_ **INFO** _si quieres ver el detalle técnico._`;
}

/* ---------- dibujo (percepcion.py: anotar) ---------- */
function iou(a, b) {
  const ix = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const iy = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const inter = ix * iy;
  const un = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
  return un > 0 ? inter / un : 0;
}

function deduplicarVisual(dets) {          // E42: solo presentación
  const conservadas = [], porClase = {};
  for (const d of [...dets].sort((a, b) => b.conf - a.conf)) {
    if (d.cls === 6) { conservadas.push(d); continue; }
    const dup = (porClase[d.cls] || []).some(o => iou(d.caja, o.caja) >= 0.3);
    if (!dup) {
      (porClase[d.cls] = porClase[d.cls] || []).push(d);
      conservadas.push(d);
    }
  }
  return conservadas;
}

function personaContenedora(det, personas) {
  const [x1, y1, x2, y2] = det.caja;
  const area = Math.max((x2 - x1) * (y2 - y1), 1e-6);
  let mejor = null, mejorFrac = 0;
  for (const p of personas) {
    const ix = Math.max(0, Math.min(x2, p.caja[2]) - Math.max(x1, p.caja[0]));
    const iy = Math.max(0, Math.min(y2, p.caja[3]) - Math.max(y1, p.caja[1]));
    const frac = ix * iy / area;
    if (frac > mejorFrac) { mejorFrac = frac; mejor = p; }
  }
  return mejorFrac >= 0.3 ? mejor : null;
}

function cascoDePersona(persona, cascos, refX) {   // E30: gafas a los ojos
  const [px1, py1, px2, py2] = persona.caja;
  let mejor = null, mejorD = Infinity;
  for (const c of cascos) {
    const cx = (c.caja[0] + c.caja[2]) / 2, cy = (c.caja[1] + c.caja[3]) / 2;
    const enCabeza = py1 <= cy && cy <= py1 + 0.35 * (py2 - py1);
    if (px1 <= cx && cx <= px2 && enCabeza && Math.abs(cx - refX) < mejorD) {
      mejorD = Math.abs(cx - refX); mejor = c;
    }
  }
  return mejor;
}

function reanclarAOjos(caja, persona, casco) {     // E34: por régimen
  const [x1, y1, x2, y2] = caja;
  const h = y2 - y1, cy = (y1 + y2) / 2;
  const [py1, , , py2] = persona.caja;
  const ph = py2 - py1;
  let objetivo;
  if (casco) {
    const ch = casco.caja[3] - casco.caja[1];
    if (casco.cls === 7) {
      objetivo = casco.caja[1] + 0.5 * ch;          // cabeza descubierta
    } else {
      const borde = (casco.caja[3] - py1) / ph;
      objetivo = borde <= 0.25
        ? (casco.caja[1] + casco.caja[3]) / 2 - 0.15 * ch   // full-body
        : casco.caja[3] + 0.20 * h;                          // primer plano
    }
  } else {
    objetivo = py1 + 0.08 * ph;
  }
  objetivo = Math.min(Math.max(objetivo, py1 + 0.06 * ph), py1 + 0.45 * ph);
  objetivo = Math.max(objetivo, py1 + h / 2 + 2);
  if (cy <= objetivo + 0.25 * h) return caja;      // zona muerta
  const delta = objetivo - cy;
  return [x1, y1 + delta, x2, y2 + delta];
}

function anotar(ctx, detecciones, grueso) {
  const dets = deduplicarVisual(detecciones);
  const personas = dets.filter(d => d.cls === 6);
  const cascos = dets.filter(d => d.cls === 0 || d.cls === 7);
  for (const p of personas) {
    ctx.lineWidth = grueso + 1;
    ctx.strokeStyle = "rgb(100,200,255)";
    trazarCaja(ctx, p.caja);
    etiqueta(ctx, `Persona ${p.conf.toFixed(2)}`, p.caja[0], p.caja[1] - 2,
      "rgb(40,120,180)");
  }
  for (const d of dets) {
    if (d.cls === 5 || d.cls === 6) continue;      // none no se dibuja
    const color = ES_INCUMPLIMIENTO(d.cls) ? "rgb(255,0,0)" : "rgb(0,200,0)";
    let caja = d.caja;
    if (d.cls === 4 || d.cls === 8) {              // gafas: re-anclaje
      const per = personaContenedora(d, personas);
      if (per) {
        const casco = cascoDePersona(per, cascos, (caja[0] + caja[2]) / 2);
        caja = reanclarAOjos(caja, per, casco);
      }
    }
    ctx.lineWidth = grueso;
    ctx.strokeStyle = color;
    trazarCaja(ctx, caja);
    etiqueta(ctx, `${NOMBRES_ES[d.cls]} ${d.conf.toFixed(2)}`,
      caja[0], caja[1] - 2, color);
  }
}

function trazarCaja(ctx, [x1, y1, x2, y2]) {
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
}

function etiqueta(ctx, texto, x, y, fondo) {
  const fs = Math.max(12, Math.round(ctx.canvas.height / 40));
  ctx.font = `${fs}px "Segoe UI", sans-serif`;
  const w = ctx.measureText(texto).width + 6;
  const h = fs + 4;
  const yTxt = Math.max(h, y);
  ctx.fillStyle = fondo;
  ctx.fillRect(x - 1, yTxt - h, w, h);
  ctx.fillStyle = "#fff";
  ctx.fillText(texto, x + 2, yTxt - 3);
}

/* ---------- inferencia ONNX en el navegador ---------- */
let sesion = null;
let cargando = null;

function cargarModelo() {
  if (sesion) return Promise.resolve(sesion);
  if (cargando) return cargando;
  const texto = $("estado-modelo-texto");
  const extra = $("estado-modelo-extra");
  ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web/dist/";
  cargando = (async () => {
    try {
      try {
        sesion = await ort.InferenceSession.create("modelo/best.onnx",
          { executionProviders: ["webgpu", "wasm"] });
        extra.textContent = " (acelerado por WebGPU)";
      } catch (e) {
        sesion = await ort.InferenceSession.create("modelo/best.onnx",
          { executionProviders: ["wasm"] });
        extra.textContent = " (procesador del navegador, sin WebGPU)";
      }
      texto.innerHTML = "✅ Modelo listo — corre en tu navegador; ninguna imagen sale de tu equipo.";
      $("btn-procesar").disabled = !$("lienzo").dataset.lista;
      return sesion;
    } catch (e) {
      texto.textContent = "❌ No se pudo cargar el modelo: " + e;
      throw e;
    }
  })();
  return cargando;
}

/* letterbox 640 igual que ultralytics: escala y bordes grises (114) */
function letterbox(imgCanvas) {
  const L = 640, c = document.createElement("canvas");
  c.width = L; c.height = L;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "rgb(114,114,114)";
  ctx.fillRect(0, 0, L, L);
  const esc = Math.min(L / imgCanvas.width, L / imgCanvas.height);
  const w = Math.round(imgCanvas.width * esc);
  const h = Math.round(imgCanvas.height * esc);
  const dw = Math.round((L - w) / 2), dh = Math.round((L - h) / 2);
  ctx.drawImage(imgCanvas, dw, dh, w, h);
  return { canvas: c, esc, dw, dh };
}

async function inferir(imgCanvas) {
  await cargarModelo();
  const { canvas: lb, esc, dw, dh } = letterbox(imgCanvas);
  const d = lb.getContext("2d").getImageData(0, 0, 640, 640).data;
  const entrada = new Float32Array(3 * 640 * 640);
  // HWC RGB -> CHW /255
  for (let i = 0, j = 0; i < d.length; i += 4, j++) {
    entrada[j] = d[i] / 255;                       // canal R
    entrada[640 * 640 + j] = d[i + 1] / 255;       // G
    entrada[2 * 640 * 640 + j] = d[i + 2] / 255;   // B
  }
  const tensor = new ort.Tensor("float32", entrada, [1, 3, 640, 640]);
  const salida = await sesion.run({ [sesion.inputNames[0]]: tensor });
  const out = salida[sesion.outputNames[0]].data;  // [1, 15, 8400]
  const n = out.length / 15;

  // YOLOv8 crudo: filas 0-3 = cx,cy,w,h (px del 640); 4-14 = scores
  const crudas = [];
  for (let i = 0; i < n; i++) {
    let mejor = 0, conf = -1;
    for (let c = 0; c < 11; c++) {
      const s = out[(4 + c) * n + i];
      if (s > conf) { conf = s; mejor = c; }
    }
    if (conf < UMBRAL_INC) continue;
    const cx = out[i], cy = out[n + i];
    const w = out[2 * n + i], h = out[3 * n + i];
    crudas.push({
      cls: mejor, conf,
      caja: [(cx - w / 2 - dw) / esc, (cy - h / 2 - dh) / esc,
             (cx + w / 2 - dw) / esc, (cy + h / 2 - dh) / esc],
    });
  }
  // NMS por clase (IoU 0.5, igual que ultralytics con agnostic=False)
  const finales = [];
  for (let c = 0; c < 11; c++) {
    let deCla = crudas.filter(d => d.cls === c)
      .sort((a, b) => b.conf - a.conf);
    while (deCla.length) {
      const mejor = deCla.shift();
      finales.push(mejor);
      deCla = deCla.filter(o => iou(o.caja, mejor.caja) <= IOU_NMS);
    }
  }
  return finales;
}

/* ---------- la sesión de demo (imagen o webcam) ---------- */
let imgBase = null;        // canvas con la imagen en su tamaño original
let gtFoto = null;         // etiqueta oficial de la foto sorteada

function lienzoADimension(canvasImg) {
  const c = $("lienzo");
  c.width = canvasImg.width; c.height = canvasImg.height;
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  ctx.drawImage(canvasImg, 0, 0);
}

function tablaDetecciones(dets) {
  const cuerpo = $("tabla-detecciones").querySelector("tbody");
  cuerpo.innerHTML = "";
  for (const d of [...dets].sort((a, b) => b.conf - a.conf)) {
    if (d.cls === 5) continue;
    const tipo = ES_INCUMPLIMIENTO(d.cls) ? "⚠️ Incumplimiento"
      : d.cls === 6 ? "👤 Persona" : "✅ EPP presente";
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${NOMBRES_ES[d.cls]}</td><td>${d.conf.toFixed(2)}</td>` +
      `<td>${tipo}</td>`;
    cuerpo.appendChild(tr);
  }
}

function veredictoGT(incidentes) {
  if (!gtFoto) return "";
  const esperadas = new Set(gtFoto.ids.filter(ES_INCUMPLIMIENTO));
  const alertadas = new Set(incidentes.map(i => i.claseId));
  const nombres = ids => [...ids].map(c => NOMBRES_ES[c]).join(", ") || "nada";
  if (gtFoto.tipo === "incidente") {
    const ok = [...esperadas].some(c => alertadas.has(c));
    return `<p class="gt">Comparado con la etiqueta oficial: ` +
      `<strong>${ok ? "✅ acierta" : "❌ falla"}</strong> — debía alertar ` +
      `${esc(nombres(esperadas))} y alertó ${esc(nombres(alertadas))}.</p>`;
  }
  const bien = alertadas.size === 0;
  return `<p class="gt">Escena de control (sin faltas etiquetadas): ` +
    `<strong>${bien ? "✅ se comporta bien: sin faltas, no alerta"
      : "❌ falsa alarma: alertó " + esc(nombres(alertadas))}</strong>.</p>`;
}

/* procesa una imagen como el video corto de 4 frames de la demo */
async function procesarBurst() {
  if (!imgBase) return;
  $("btn-procesar").disabled = true;
  ses.verificaciones += 1;
  const zona = "web";
  const t0 = performance.now() / 1000;
  const pasos = [];
  let tInf = 0;
  for (let k = 0; k < FRAMES_DEMO; k++) {
    const a = performance.now();
    const crudas = await inferir(imgBase);
    tInf += performance.now() - a;
    const filtradas = filtrarPorClase(crudas);
    const incidentes = evaluarRazonamiento(zona, t0 + k * INTERVALO_S, filtradas)
      .filter(i => permiteAlerta(i, t0 + k * INTERVALO_S));
    pasos.push({ filtradas, incidentes });
  }
  ses.alertas += pasos.reduce((s, p) => s + p.incidentes.length, 0);
  const total = pasos.reduce((s, p) => s + p.incidentes.length, 0);

  lienzoADimension(imgBase);
  anotar($("lienzo").getContext("2d"), pasos[FRAMES_DEMO - 1].filtradas, 2);
  tablaDetecciones(pasos[FRAMES_DEMO - 1].filtradas);
  $("linea-tiempo").innerHTML = lineaTiempo(pasos, tInf);
  const incidentes = pasos.flatMap(p => p.incidentes);
  $("payload").innerHTML = incidentes.length
    ? `<strong>Mensaje que recibiría el supervisor</strong> (aquí solo se ` +
      `muestra, no se envía):\n\n` + esc(captionLote(incidentes))
    : `<span class="sin-alerta">Sin faltas confirmadas, no se envía nada.</span>`;
  const gtEl = $("gt");
  gtEl.innerHTML = (gtFoto ? gtFoto.texto : "") + veredictoGT(incidentes);
  log(`verificación ${ses.verificaciones} zona=${zona} → ${total} ` +
    `incidente(s): ${incidentes.map(i => i.clase).join(", ") || "ninguno"}`);
  $("resumen").textContent = resumen() +
    ` Detector: ~${(tInf / FRAMES_DEMO).toFixed(0)} ms/frame en tu navegador.`;
  $("btn-procesar").disabled = false;
}

function lineaTiempo(pasos, tInfMs) {
  const rachasLocales = {};
  let html = `<table class="tabla"><thead><tr><th>Frame</th><th>Tiempo` +
    `</th><th>Qué decide el agente</th></tr></thead><tbody>`;
  for (let k = 0; k < pasos.length; k++) {
    const { filtradas, incidentes } = pasos[k];
    const presentes = new Set(filtradas.filter(d => ES_INCUMPLIMIENTO(d.cls))
      .map(d => d.cls));
    const confirmadas = new Set(incidentes.map(i => i.claseId));
    const frag = [];
    for (const c of Object.keys(rachasLocales))
      if (!presentes.has(Number(c))) delete rachasLocales[c];
    for (const c of presentes) {
      const conf = Math.max(...filtradas.filter(d => d.cls === c)
        .map(d => d.conf));
      rachasLocales[c] = (rachasLocales[c] || 0) + 1;
      if (confirmadas.has(c)) {
        frag.push(`<span class="ok">${NOMBRES_ES[c]} confirmado</span> ` +
          `(confianza ${conf.toFixed(2)}): se alerta al supervisor`);
      } else if (rachasLocales[c] < K_FRAMES) {
        frag.push(`${NOMBRES_ES[c]} visto (confianza ${conf.toFixed(2)}), ` +
          `racha ${rachasLocales[c]} de ${K_FRAMES}`);
      } else {
        frag.push(`${NOMBRES_ES[c]} sigue presente, pero ya se alertó ` +
          `(pasa el cooldown de ${COOLDOWN_S.toFixed(0)} s)`);
      }
    }
    html += `<tr><td>${k + 1}</td><td>t+${(k * INTERVALO_S).toFixed(1)} s` +
      `</td><td>${frag.join(" · ") || "no se ve ningún incumplimiento"}` +
      `</td></tr>`;
  }
  html += `</tbody></table><p class="pie">El detector tardó unos ` +
    `${(tInfMs / FRAMES_DEMO).toFixed(0)} ms por frame en tu navegador. ` +
    `Las reglas: confirmar tras ${K_FRAMES} frames seguidos y no repetir la ` +
    `misma alerta antes de ${COOLDOWN_S.toFixed(0)} s.</p>`;
  return html;
}

/* ---------- entrada de imagen ---------- */
$("archivo").addEventListener("change", ev => {
  const archivo = ev.target.files[0];
  if (!archivo) return;
  cargarEnLienzo(URL.createObjectURL(archivo), null);
});

function cargarEnLienzo(url, gt) {
  const img = new Image();
  img.onload = () => {
    const c = document.createElement("canvas");
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    c.getContext("2d").drawImage(img, 0, 0);
    imgBase = c;
    gtFoto = gt;
    $("gt").innerHTML = gt ? gt.texto : "";
    lienzoADimension(c);
    $("btn-procesar").disabled = false;
    cargarModelo();
  };
  img.src = url;
}

/* ---------- sorteo de foto de test con etiqueta oficial ---------- */
$("btn-foto").addEventListener("click", () => {
  const nombres = Object.keys(DATOS.etiquetasTest);
  const incidentes = nombres.filter(n =>
    DATOS.etiquetasTest[n].some(ES_INCUMPLIMIENTO));
  const esIncidente = Math.random() < incidentes.length / nombres.length;
  const nombre = esIncidente
    ? incidentes[Math.floor(Math.random() * incidentes.length)]
    : nombres[Math.floor(Math.random() * nombres.length)];
  const ids = DATOS.etiquetasTest[nombre];
  const nombresDe = lista => lista.map(c => NOMBRES_ES[c]).join(", ");
  const tipo = ids.some(ES_INCUMPLIMIENTO) ? "incidente" : "control";
  const faltas = ids.filter(ES_INCUMPLIMIENTO);
  const texto = `<strong>Etiqueta oficial</strong> de <code>${nombre}</code>: ` +
    `en la escena hay ${esc(nombresDe(ids)) || "—"}. ` +
    (tipo === "incidente"
      ? `Faltas que debería detectar: <strong>${esc(nombresDe(faltas))}</strong>. Procesa la imagen y compara.`
      : `Ninguna falta: el agente debería quedarse callado.`);
  cargarEnLienzo(`fotos/${nombre}`, { ids, tipo, texto });
  log(`foto sorteada: ${nombre} (tipo ${tipo})`);
});

/* ---------- webcam en vivo (K=3 y cooldown reales) ---------- */
let camStream = null, camTimer = null;

$("btn-webcam").addEventListener("click", async () => {
  if (camStream) {   // detener
    camStream.getTracks().forEach(t => t.stop());
    camStream = null; clearInterval(camTimer);
    $("btn-webcam").textContent = "🎥 Usar la webcam (en vivo, K=3 real)";
    return;
  }
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true });
  } catch (e) {
    $("resumen").textContent = "No se pudo abrir la webcam (¿permiso denegado?)";
    return;
  }
  const video = document.createElement("video");
  video.srcObject = camStream; video.play();
  $("btn-webcam").textContent = "⏹️ Detener la webcam";
  await cargarModelo();
  $("resumen").textContent = "Webcam activa: cada captura cuenta para la " +
    "racha; 3 seguidas confirman la alerta (cooldown real de 30 s).";
  ses.verificaciones += 1;
  let n = 0;
  camTimer = setInterval(async () => {
    if (video.readyState < 2) return;
    const c = document.createElement("canvas");
    c.width = video.videoWidth; c.height = video.videoHeight;
    c.getContext("2d").drawImage(video, 0, 0);
    imgBase = c; gtFoto = null;
    const t = performance.now() / 1000;
    const crudas = await inferir(c);
    const filtradas = filtrarPorClase(crudas);
    const incidentes = evaluarRazonamiento("webcam", t, filtradas)
      .filter(i => permiteAlerta(i, t));
    lienzoADimension(c);
    anotar($("lienzo").getContext("2d"), filtradas, 2);
    tablaDetecciones(filtradas);
    if (incidentes.length) {
      ses.alertas += incidentes.length;
      $("payload").innerHTML = `<strong>🚨 Alerta en vivo</strong>:\n\n` +
        esc(captionLote(incidentes));
      log(`webcam → alerta: ${incidentes.map(i => i.clase).join(", ")}`);
    } else if (n % 8 === 0) {
      $("resumen").textContent = resumen();
    }
    n++;
  }, 700);
});

/* ---------- fallas del sensor ---------- */
$("btn-falla").addEventListener("click", async () => {
  const opcion = document.querySelector("input[name=falla]:checked").value;
  const c = $("lienzo-falla");
  c.width = 640; c.height = 480;
  const ctx = c.getContext("2d");
  let titulo, causa, fallidos;
  if (opcion === "none") {
    ctx.fillStyle = "#10161d"; ctx.fillRect(0, 0, 640, 480);
    titulo = "SIN DATO (frame None)"; causa = "el sensor no entregó datos"; fallidos = 4;
  } else if (opcion === "negro") {
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, 640, 480);
    titulo = "frame negro"; fallidos = 0;
  } else {
    ctx.fillStyle = "#808080"; ctx.fillRect(0, 0, 640, 480);
    titulo = "frame de 1 canal"; causa = "la entrada no es una imagen a color válida"; fallidos = 4;
  }
  ctx.fillStyle = "#fff"; ctx.font = "22px sans-serif";
  ctx.fillText(titulo, 40, 230);
  ctx.fillStyle = "#aaa"; ctx.font = "14px sans-serif";
  ctx.fillText("lo que recibió el agente", 40, 255);

  ses.framesFallidos += fallidos;
  let reaccion;
  if (opcion === "negro") {
    await cargarModelo();
    const crudas = await inferir(c);        // un frame negro ES válido
    reaccion = crudas.length === 0
      ? "El frame negro es un frame válido: el agente lo mira, no encuentra nada y por eso no alerta. No cuenta como falla del sensor."
      : "El frame negro es válido; el agente no encontró faltas.";
  } else {
    reaccion = `Falla del sensor: ${causa}. El agente anotó ${fallidos} frames fallidos y siguió trabajando normal: no se cayó y no inventó alertas.`;
  }
  let filas = "";
  for (let k = 1; k <= FRAMES_DEMO; k++)
    filas += `<tr><td>${k}</td><td>${fallidos ? "percepción fallida registrada" : "sin detecciones"}</td></tr>`;
  $("salida-falla").innerHTML = `<table class="tabla"><thead><tr><th>Frame` +
    `</th><th>Qué hizo el agente</th></tr></thead><tbody>${filas}</tbody>` +
    `</table><p>${reaccion}</p>`;
  log(`falla simulada (${titulo}) -> frames fallidos +${fallidos}`);
});

/* ---------- pestañas ---------- */
function activarTab(id) {
  document.querySelectorAll("nav#tabs button").forEach(b =>
    b.classList.toggle("activo", b.dataset.tab === id));
  document.querySelectorAll("section.tab").forEach(s =>
    s.classList.toggle("activo", s.id === id));
  window.scrollTo({ top: 0 });
}
document.querySelectorAll("nav#tabs button, [data-tab]").forEach(el =>
  el.addEventListener("click", ev => {
    ev.preventDefault();
    activarTab(el.dataset.tab);
  }));

/* ---------- secciones estáticas desde los datos del repo ---------- */
function tablaM1M4() {
  const c = DATOS.corridaOficial;
  const m1 = c.M1_recall_incidente;
  const fila = (medida, split, formula, umbral, casos, valor, ok) =>
    `<tr><td><strong>${medida}</strong></td><td>${split}</td><td>${formula}` +
    `</td><td>${umbral}</td><td>${casos}</td><td><strong>${valor}</strong>` +
    `</td><td class="${ok ? "cumple" : "fallo"}">${ok ? "✅" : "❌"}</td></tr>`;
  let html = `<table class="tabla"><thead><tr><th>Medida</th><th>Split</th>` +
    `<th>Fórmula</th><th>Umbral</th><th>Casos</th><th>Resultado</th>` +
    `<th>¿Cumple?</th></tr></thead><tbody>`;
  for (const s of ["val", "test"]) {
    html += fila("M1 Recall de incidente", s, "escenas con alerta / escenas incidente",
      `≥ ${m1[s].umbral_M1}`, `${m1[s].casos_M1} escenas`,
      m1[s].recall_media.toFixed(3), m1[s].cumple_M1);
    html += fila("M2 Falsas alarmas", s, "escenas control con alerta / escenas control",
      `≤ ${m1[s].umbral_M2}`, `${m1[s].casos_M2} escenas`,
      m1[s].falsas_media.toFixed(3), m1[s].cumple_M2);
  }
  html += fila("M3 Tiempo de notificación", "val+test",
    "confirmación + procesamiento + envío WhatsApp", "< 10 s", "5 escenarios × 5 reps",
    "2.99 s", true);
  html += fila("M4 Cooldown anti-spam", "S6 + S7",
    "duplicadas dentro de la ventana", "= 0", "S6 + S7 × 5 reps",
    "S6 = 1 alerta, S7 = 2", true);
  return html + "</tbody></table>";
}

function tablaMetricasDetector(split) {
  const s = DATOS.metricasE44.splits[split];
  const f1g = (2 * s.precision_media * s.recall_media /
    (s.precision_media + s.recall_media)).toFixed(3);
  let html = `<h4>Split ${split} — mAP50 = ${s.mAP50.toFixed(3)}</h4>` +
    `<table class="tabla"><thead><tr><th>Clase</th><th>Precisión</th>` +
    `<th>Recall</th><th>F1</th><th>AP50</th></tr></thead><tbody>` +
    `<tr><td><strong>TODAS (media)</strong></td><td>${s.precision_media.toFixed(3)}` +
    `</td><td>${s.recall_media.toFixed(3)}</td><td>${f1g}</td>` +
    `<td>${s.mAP50.toFixed(3)}</td></tr>`;
  for (const c of s.por_clase) {
    html += `<tr><td>${c.clase}</td><td>${c.P.toFixed(3)}</td>` +
      `<td>${c.R.toFixed(3)}</td><td>${c.F1.toFixed(3)}</td>` +
      `<td>${c.AP50.toFixed(3)}</td></tr>`;
  }
  return html + "</tbody></table>";
}

function tablaAgenteEscena() {
  const ag = DATOS.metricasE44.agente_escena;
  let html = `<table class="tabla"><thead><tr><th>Split</th><th>Escenas con ` +
    `falta</th><th>Escenas control</th><th>TP</th><th>FN</th><th>FP</th>` +
    `<th>TN</th><th>Accuracy</th><th>Precisión</th><th>Recall (M1)</th>` +
    `<th>F1</th></tr></thead><tbody>`;
  for (const [sp, a] of Object.entries(ag)) {
    html += `<tr><td>${sp}</td><td>${a.escenas_incidente}</td>` +
      `<td>${a.escenas_control}</td><td>${a.TP}</td><td>${a.FN}</td>` +
      `<td>${a.FP}</td><td>${a.TN}</td><td>${a.accuracy_escena.toFixed(3)}</td>` +
      `<td>${a.precision_escena.toFixed(3)}</td>` +
      `<td>${a.recall_escena_M1.toFixed(3)}</td><td>${a.f1_escena.toFixed(3)}</td></tr>`;
  }
  return html + "</tbody></table>";
}

/* mini parser MD->HTML para la tabla oficial (encabezados y tablas) */
function mdAHtml(md) {
  const lineas = md.split(/\r?\n/);
  let html = "", enTabla = false;
  const celda = t => esc(t.trim()).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
  for (const ln of lineas) {
    if (ln.startsWith("|")) {
      const celdas = ln.split("|").slice(1, -1);
      if (/^\s*:?-+/.test(celdas[0] || "")) continue;    // separador
      if (!enTabla) { html += "<table><tbody>"; enTabla = true; }
      html += "<tr>" + celdas.map(c => `<td>${celda(c)}</td>`).join("") + "</tr>";
      continue;
    }
    if (enTabla) { html += "</tbody></table>"; enTabla = false; }
    if (ln.startsWith("# ")) html += `<h3>${esc(ln.slice(2))}</h3>`;
    else if (ln.startsWith("## ")) html += `<h4>${esc(ln.slice(3))}</h4>`;
    else if (ln.trim()) html += `<p>${celda(ln)}</p>`;
  }
  if (enTabla) html += "</tbody></table>";
  return html;
}

const FIGURAS = [
  ["fig1_clases.png", "Distribución de clases: las faltas no_* son minoría",
    "Cajas por clase en el dataset completo (11,521). Las barras rojas son las faltas no_* que el agente debe detectar: apenas el 13.6% del total, y no_boots (115 cajas, 1%) casi no se distingue. Es la evidencia detrás de los umbrales bajos y de medir el éxito por escena y no por caja."],
  ["fig2_cajas_por_imagen.png", "Cajas por imagen: escenas densas",
    "Objetos etiquetados por imagen: mediana de 7, máximo de 58. En una obra hay varias personas a la vez, así que el agente no puede razonar sobre «la foto» en bloque: decide detección por detección."],
  ["fig3_splits.png", "La contaminación de splits que obligó a rehacerlos",
    "Cruce entre las carpetas del proyecto y el split oficial del dataset: 112 imágenes que el oficial reservaba para test estaban dentro de train. Entrenar con ellas infla cualquier métrica; por eso el primer paso del proyecto fue rehacer el split (dataset_v2) antes de entrenar."],
  ["fig4_areas.png", "Área de las cajas: objetos pequeños",
    "Área que ocupa cada caja respecto a la imagen (mediana 1.85%, escala logarítmica). En planos abiertos los EPP son pocos píxeles, y los que menos alcanzan a ver son justamente los más pequeños del cuerpo — botas y gafas. Es la causa geométrica del mal resultado del detector en no_boots y no_goggle (sección 3)."],
  ["fig5_dimensiones.png", "Resoluciones: no todo es 640×640",
    "Resoluciones en disco: 78.8% son 640×640 y el 21.2% restante no, mezclando horizontal y vertical. YOLO re-escala todo (letterbox), pero explica por qué la resolución de inferencia se mantiene en 640 o más: achicar la imagen castiga primero a los objetos pequeños de la figura anterior."],
  ["fig6_brillo.png", "Brillo: el 4.5% de la muestra es muy oscura",
    "Brillo medio de una muestra determinista (n=200, semilla 42; la línea roja marca el umbral de «oscuro»). 9 imágenes (4.5%) caen por debajo: hay condiciones de noche e interior en el dataset. Para una cámara 24/7 esto pesa más: de noche el detector ve menos, y el aumento nocturno quedó como mejora futura."],
];

function renderEstatico() {
  $("tabla-m1m4").innerHTML = tablaM1M4();
  $("metricas-m1m4").innerHTML = tablaM1M4();
  $("tabla-oficial").innerHTML = mdAHtml(DATOS.tablaOficialMD);
  $("metricas-detector").innerHTML = tablaMetricasDetector("val") +
    tablaMetricasDetector("test");
  $("metricas-agente").innerHTML = tablaAgenteEscena();
  const gal = $("galeria-eda");
  for (const [archivo, titulo, caption] of FIGURAS) {
    gal.insertAdjacentHTML("beforeend",
      `<figure><img src="figuras/${archivo}" alt="${esc(titulo)}" loading="lazy">` +
      `<figcaption><strong>${esc(titulo)}.</strong> ${esc(caption)}</figcaption></figure>`);
  }
}

/* ---------- arranque ---------- */
renderEstatico();
cargarModelo();
