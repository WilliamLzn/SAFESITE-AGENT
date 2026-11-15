"""SafeSite-Agent — Panel web de supervisión con detección EN VIVO por webcam.

Fase 4 (final): conecta el agente al mundo físico. Arquitectura:

    webcam → hilo de captura → agente completo (percepción → razonamiento
    K frames → memoria/cooldown) ─┬→ MJPEG al navegador (video con cajas)
                                  └→ cola + worker → WhatsApp (asíncrono:
                                     el video NUNCA se congela por un envío)

El webhook INFO sigue funcionando durante la sesión en vivo (el historial
lo escribe la Memoria del agente).

Uso (desde la RAIZ del proyecto):
    .venv\\Scripts\\python.exe -m src.safesite.panel            # GPU, zona obra_cam1
    .venv\\Scripts\\python.exe -m src.safesite.panel --device cpu
    .venv\\Scripts\\python.exe -m src.safesite.panel --zona entrada_obra
Abre http://localhost:5000 en el navegador.
"""
import argparse
import collections
import queue
import threading
import time
from datetime import datetime

import cv2
from flask import Flask, Response, jsonify

from . import config
from .actuarios import ActuadorConsola, ActuadorWhatsApp
from .agente import SafeSiteAgent
from .percepcion import Percepcion
from .razonamiento import Incidente
from .badge_reader import LectorBadgeQR
from .asistencia import registro_asistencia

PAGINA = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><title>SafeSite-Agent · Supervisión en vivo</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --fondo:#05050a;
    --tarjeta: rgba(20, 18, 32, 0.7);
    --borde: rgba(139, 92, 246, 0.3);
    --borde-suave: rgba(255,255,255,0.08);
    --texto:#f8fafc;
    --texto-sec:#94a3b8;
    --acento:#8b5cf6;
    --acento-2:#d946ef;
    --acento-3:#06b6d4;
    --ok:#10b981;
    --alerta:#ef4444;
    --sombra-color: 0 20px 40px -10px rgba(139, 92, 246, 0.25);
    --borde-qr: rgba(139,92,246,0.6);
  }
  * { box-sizing: border-box; }
  body { background:#05050a; color:var(--texto); font-family:'Inter',system-ui,sans-serif; margin:0; padding:0; min-height:100vh; }
  .wrap { max-width:1400px; margin:0 auto; width:100%; }
  h1 { font-size:1.15rem; margin:0 0 2px; font-weight:700; letter-spacing:-0.01em; display:flex; align-items:center; gap:8px; }
  .sub { color:var(--texto-sec); font-size:.8rem; margin-bottom:14px; font-weight:400; }
  .header { display:flex; align-items:center; gap:10px; margin-bottom:16px; padding:0 20px; }
  .layout { display:grid; grid-template-columns:60% 40%; gap:16px; grid-template-rows:auto; padding:0 24px 28px; }
  @media (max-width:900px){ .layout{grid-template-columns:1fr;} }
  .video-container { position:relative; width:100%; max-width:760px; border-radius:24px; background:#000; aspect-ratio:16/9; object-fit:cover; margin:0 auto; border:1px solid var(--borde-suave); box-shadow:var(--sombra-color); overflow:hidden; }
  .video { width:100%; height:100%; border-radius:24px; object-fit:cover; display:block; }
  .estado-camara-overlay { position:absolute; bottom:20px; left:50%; transform:translateX(-50%); z-index:50; background:rgba(10,8,18,0.75); backdrop-filter:blur(12px); color:var(--texto); padding:8px 18px; border-radius:30px; border:1px solid var(--borde); font-size:.82rem; font-weight:700; pointer-events:none; max-width:90%; text-align:center; box-shadow:0 12px 32px -6px rgba(0,0,0,0.5); }

  /* ---------- contenedor scrollable de badges ---------- */
  #badge-contenedor { overflow-y:auto; border-radius:20px; display:grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap:14px; padding:18px; border:1px solid var(--borde-suave); box-shadow:var(--sombra-color); }
  #badge-contenedor::-webkit-scrollbar { width: 5px; }
  #badge-contenedor::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
  #badge-contenedor::-webkit-scrollbar-thumb { background: var(--borde-suave); border-radius: 3px; }

  /* ---------- tarjeta de badge ---------- */
  .badge-none { color:var(--texto-sec); font-style:italic; text-align:center; padding:50px 20px; }
  .badge-card-compacta { background:var(--tarjeta); border-radius:18px; padding:16px; border:1px solid var(--borde-suave); display:flex; flex-direction:column; align-items:center; gap:10px; height:auto; min-height:260px; transition:all .25s ease; position:relative; overflow:hidden; }
  .badge-card-compacta::before { content:""; position:absolute; top:0; left:0; right:0; height:3px; background:linear-gradient(90deg, var(--acento), var(--acento-2)); opacity:0; transition:opacity .25s; }
  .badge-card-compacta:hover { border-color:var(--acento); transform:translateY(-4px); box-shadow:0 12px 32px -6px rgba(139,92,246,0.35); }
  .badge-card-compacta:hover::before { opacity:1; }
  .badge-card-compacta .qr-placeholder { width:64px; height:64px; border-radius:14px; margin:2px auto 0; display:flex; align-items:center; justify-content:center; font-size:1.4rem; border:2px solid var(--borde-qr); background:rgba(0,0,0,0.4); }
  .badge-card-compacta h2 { margin:0 0 2px; font-size:1rem; font-weight:700; letter-spacing:-0.01em; }
  .badge-card-compacta .sub { color:var(--texto-sec); font-size:.72rem; margin-bottom:1px; }
  .badge-card-compacta .chip { display:inline-block; padding:4px 12px; border-radius:24px; font-size:.72rem; font-weight:700; margin:2px 0; }
  .chip-activo { background:var(--ok); color:#fff; box-shadow:0 4px 12px -4px rgba(16,185,129,0.4); }
  .chip-bloqueado { background:var(--alerta); color:#fff; box-shadow:0 4px 12px -4px rgba(239,68,68,0.4); }
  .badge-card-compacta .badge-meta { font-size:.7rem; color:var(--texto-sec); text-align:center; margin-top:2px; width:100%; line-height:1.4; }
  .badge-card-compacta .epp-iconos { display:flex; gap:6px; justify-content:center; margin:6px 0; flex-wrap:wrap; }
  .badge-card-compacta .epp-icon { width:42px; height:42px; border-radius:12px; display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:1.1rem; border:2px solid; }
  .badge-card-compacta .epp-icon .nombre { font-size:.62rem; margin-top:2px; font-weight:700; letter-spacing:0.01em; text-transform:none; }
  .badge-card-compacta .badge-actions { margin-top:4px; display:flex; gap:6px; justify-content:center; width:100%; }
  .badge-card-compacta .boton { font-size:.72rem; padding:5px 10px; flex:1; }
  .badge-card-compacta .resumen-badge { background:rgba(255,255,255,0.03); border-radius:12px; padding:8px; margin-top:4px; text-align:center; font-size:.72rem; border:1px solid var(--borde-suave); width:100%; }
  .badge-card-compacta .resumen-badge .row { display:flex; justify-content:space-between; margin-bottom:1.5px; }
  .badge-card-compacta .resumen-badge .label { color:var(--texto-sec); }
  .badge-card-compacta .resumen-badge .valor { font-weight:700; color:var(--texto); }
  .badge-card-compacta .temporizador { margin-top:3px; padding:4px 8px; background:rgba(139,92,246,0.1); border-radius:8px; border:1px solid rgba(139,92,246,0.25); width:100%; }
  .badge-card-compacta .temporizador .label-temp { font-size:.66rem; color:var(--texto-sec); margin-right:3px; }
  .badge-card-compacta .temporizador .valor-temp { font-size:.8rem; font-weight:700; color:var(--texto); font-family:'Inter',monospace; }
  .tarjetas { display:grid; grid-template-columns:repeat(auto-fill,minmax(95px,1fr)); gap:8px; margin-top:12px; }
  .tarjeta { background:var(--tarjeta); border-radius:12px; padding:10px; text-align:center; border:1px solid var(--borde-suave); }
  .tarjeta .num { font-size:1.5rem; font-weight:700; }
  .tarjeta .etq { font-size:.7rem; color:var(--texto-sec); text-transform:none; }
  .ok { color:var(--ok); } .falta { color:var(--alerta); }
  .panel { padding:18px; }
  .panel h2 { font-size:.85rem; margin:0 0 12px; color:var(--texto-sec); font-weight:600; letter-spacing:0.02em; display:flex; align-items:center; gap:8px; }
  #log { max-height:380px; overflow-y:auto; font-size:.82rem; }
  .incidente { border-left:3px solid var(--alerta); padding:8px 12px; margin-bottom:8px; background:rgba(239,68,68,0.08); border-radius:8px; }
  .incidente .hora { color:var(--texto-sec); font-size:.72rem; }
  .vacio { color:var(--texto-sec); font-style:italic; }
  .estado-linea { font-size:.74rem; color:var(--texto-sec); margin-top:10px; }
  .punto { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--ok); margin-right:5px; }
  .controles { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:16px; padding:0 20px; }
  .boton { background:var(--tarjeta); color:var(--texto); border:1px solid var(--borde-suave); border-radius:10px; padding:8px 14px; cursor:pointer; font-size:.82rem; transition:all .2s; }
  .boton:hover { border-color:var(--acento); background:rgba(139,92,246,0.12); color:var(--texto); }
  .boton:disabled { opacity:.55; cursor:wait; }
  .boton.apagado { border-color:var(--alerta); color:var(--alerta); }
  .faltas-badge { font-size:.78rem; color:var(--alerta); align-self:center; margin-left:auto; }

  /* ---------- tarjeta de badge v2 ---------- */
  .badge-card { background:var(--tarjeta); border-radius:14px; padding:18px;
                margin:14px 0; text-align:center; border:2px solid var(--gris); }
  .badge-card .qr-placeholder { width:140px; height:140px; background:#000;
                border-radius:10px; margin:0 auto 12px; display:flex;
                align-items:center; justify-content:center; color:#666;
                font-size:.7rem; border:3px solid var(--primario-color); }
  .badge-card h2 { margin:0 0 6px; font-size:1.5rem; }
  .badge-card .sub { color:var(--gris); font-size:.9rem; margin-bottom:10px; }
  .badge-card .chip { display:inline-block; padding:4px 10px; border-radius:20px;
                font-size:.8rem; font-weight:700; margin:4px 2px; }
  .chip-activo { background:var(--verde); color:#fff; }
  .chip-bloqueado { background:var(--rojo); color:#fff; }
  .badge-actions { margin-top:14px; display:flex; gap:10px; justify-content:center;
                flex-wrap:wrap; }
  .badge-none { color:var(--gris); font-style:italic; text-align:center; padding:20px; }
  .resumen-badge { background:var(--tarjeta); border-radius:10px; padding:12px;
                margin-top:10px; text-align:left; font-size:.85rem; }
  .resumen-badge .row { display:flex; justify-content:space-between; margin-bottom:4px; }
  .resumen-badge .label { color:var(--gris); }
  .resumen-badge .valor { font-weight:700; }

  /* ---------- iconos EPP en tarjeta de badge (H4) ---------- */
  .epp-iconos { display:flex; gap:10px; justify-content:center; margin:12px 0 6px; flex-wrap:wrap; }
  .epp-icon { width:52px; height:52px; border-radius:12px; display:flex;
              flex-direction:column; align-items:center; justify-content:center;
              font-size:1.1rem; border:3px solid; }
  .epp-icon.tiene { border-color:var(--verde); background:#ecfdf5; }
  .epp-icon.falta { border-color:var(--rojo); background:#fef2f2; }
  .epp-icon.sin-detectar { border-color:var(--gris); background:#f1f5f9; color:var(--gris); }
  .epp-icon .nombre { font-size:.65rem; margin-top:4px; font-weight:700;
              text-transform:uppercase; letter-spacing:.05em; }

  /* ---------- columna derecha dividida: badge arriba, incidentes abajo ---------- */
  .derecha { display:grid; grid-template-rows: 1fr 1fr; gap:16px; height:100%; }
  .derecha > div { background:var(--tarjeta); border-radius:10px; overflow:auto; }
  .derecha .panel-incidentes { padding:14px; }
  .badge-card { background:var(--tarjeta); border-radius:14px; padding:16px;
                margin:0; text-align:center; border:2px solid var(--gris);
                height:100%; display:flex; flex-direction:column; }
  .badge-card .qr-placeholder { width:120px; height:120px; background:#000;
                border-radius:10px; margin:0 auto 10px; display:flex;
                align-items:center; justify-content:center; color:#666;
                font-size:.65rem; border:3px solid var(--primario-color); }
  .badge-card h2 { margin:0 0 5px; font-size:1.3rem; }

  /* ---------- múltiples cards de badge ---------- */
  #badge-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .badge-card-multiple { background:var(--tarjeta); border-radius:12px; padding:14px;
                text-align:center; border:2px solid var(--gris); display:flex;
                flex-direction:column; }
  .badge-card-multiple .chip-activo { border-color:var(--verde); background:#ecfdf5; color:var(--verde); }
  .badge-card-multiple .chip-bloqueado { border-color:var(--rojo); background:#fef2f2; color:var(--rojo); }
  .badge-card-multiple .qr-placeholder { width:100px; height:100px; background:#000;
                border-radius:8px; margin:0 auto 8px; display:flex;
                align-items:center; justify-content:center; color:#666;
                font-size:.6rem; border:2px solid var(--primario-color); }
  .badge-card-multiple h2 { margin:0 0 4px; font-size:1.15rem; }
  .badge-card-multiple .sub { color:var(--gris); font-size:.75rem; margin-bottom:6px; }
  .badge-card-multiple .chip { display:inline-block; padding:3px 8px; border-radius:16px;
                font-size:.7rem; font-weight:700; margin:2px 1px; border:1px solid currentColor; }
  .badge-card-multiple .epp-iconos { display:flex; gap:6px; justify-content:center; margin:8px 0 4px; flex-wrap:wrap; }
  .badge-card-multiple .epp-icon { width:44px; height:44px; border-radius:10px; display:flex;
                flex-direction:column; align-items:center; justify-content:center;
                font-size:1rem; border:2px solid; }
  .badge-card-multiple .epp-icon .nombre { font-size:.6rem; margin-top:3px; font-weight:700;
                text-transform:uppercase; letter-spacing:.04em; }
  .badge-card-multiple .badge-meta { font-size:.72rem; color:var(--gris); margin-top:6px; }
  .badge-card-multiple .badge-actions { margin-top:8px; display:flex; gap:6px; justify-content:center; flex-wrap:wrap; }
  .badge-card-multiple .resumen-badge { background:rgba(255,255,255,0.03); border-radius:8px;
                padding:8px; margin-top:6px; text-align:left; font-size:.7rem;
                border:1px solid rgba(255,255,255,0.08); }
  .badge-card-multiple .resumen-badge .row { display:flex; justify-content:space-between; margin-bottom:2px; }
  .badge-card-multiple .resumen-badge .label { color:var(--gris); }
  .badge-card-multiple .resumen-badge .valor { font-weight:700; }

  /* ---------- alertas de jornada ---------- */
  /* ---------- alertas de jornada ---------- */
  .alerta-jornada { border-left:3px solid var(--alerta); padding:8px 12px; margin-bottom:8px; background:rgba(239,68,68,0.08); border-radius:8px; }
  .alerta-jornada .hora { color:var(--alerta); font-size:.72rem; font-weight:700; }
  .alerta-jornada .nombre { font-weight:700; color:var(--texto); }
  .alerta-jornada .detalle { font-size:.76rem; color:var(--texto-sec); margin-top:4px; }
  .btn-forzar { background:linear-gradient(135deg, var(--alerta), #b91c1c); border:none; color:#fff; font-size:.74rem; padding:5px 12px; border-radius:7px; cursor:pointer; }
  .btn-forzar:hover { filter:brightness(1.1); }

  /* ---------- estados ---------- */
  .estado-adentro { color:var(--ok); font-weight:700; }
  .estado-afuera { color:var(--alerta); font-weight:700; }

  /* ---------- iconos EPP estados ---------- */
  .epp-icon.tiene { border-color:var(--ok); background:rgba(16,185,129,0.14); color:var(--ok); }
  .epp-icon.falta { border-color:var(--alerta); background:rgba(239,68,68,0.14); color:var(--alerta); }
  .epp-icon.sin-detectar { border-color:var(--borde-suave); background:rgba(255,255,255,0.04); color:var(--texto-sec); }

</style></head><body><div class="wrap">
<h1>👷 SafeSite-Agent — Supervisión en vivo</h1>
<div class="sub" id="sub">conectando con la cámara…</div>
<div class="controles">
  <button id="btn-wa" class="boton" onclick="toggleWA()">⏸️ Pausar WhatsApp</button>
  <button id="btn-alerta" class="boton" onclick="alertaManual()">📨 Enviar alerta ahora</button>
  <span class="faltas-badge" id="faltas-badge"></span>
</div>

<div class="layout">
  <div class="izquierda">
    <div class="video-container">
      <img class="video" src="/video" alt="video en vivo">
      <div class="estado-camara-overlay" id="estado-camara">Reconociendo…</div>
    </div>
    <div id="tarjetas-epp" style="display:none;">
      <div class="tarjetas" id="tarjetas"></div>
    </div>
  </div>

  <div class="derecha">
    <div id="badge-contenedor">
      <div class="badge-none" id="badge-none">
        ⏳ Esperando badge QR frente a la cámara…
      </div>
      <div id="badge-cards" style="display:none;"></div>
    </div>

    <div class="panel panel-incidentes">
      <h2>🚨 Incidentes confirmados</h2>
      <div id="log"><div class="vacio">sin incidentes todavía…</div></div>
      <div class="estado-linea" id="estado"></div>
    </div>

    <div class="panel panel-incidentes">
      <h2>⚠️ Alertas de jornada</h2>
      <div id="log-jornada"><div class="vacio">sin alertas de jornada…</div></div>
    </div>
  </div>
</div>
<script>
let ultimosIds = "";

function actualizarBotonWA(activo) {
  const b = document.getElementById('btn-wa');
  b.textContent = activo ? '⏸️ Pausar WhatsApp' : '▶️ Reanudar WhatsApp';
  b.classList.toggle('apagado', !activo);
}

async function toggleWA() {
  try {
    const r = await fetch('/whatsapp/toggle', {method:'POST'});
    const e = await r.json();
    actualizarBotonWA(e.whatsapp_activo);
  } catch (err) { /* el proximo refresco resincroniza */ }
}

async function alertaManual() {
  const b = document.getElementById('btn-alerta');
  b.disabled = true; b.textContent = '⏳ enviando…';
  try {
    const r = await fetch('/alerta/manual', {method:'POST'});
    const e = await r.json();
    b.textContent = e.ok ? (e.faltas && e.faltas.length
        ? '✅ Enviada (' + e.faltas.join(', ') + ')'
        : '✅ Enviada (sin faltas)')
      : '⚠️ ' + (e.detalle || 'sin enviar');
  } catch (err) { b.textContent = '⚠️ error de red'; }
  setTimeout(() => {
    b.disabled = false; b.textContent = '📨 Enviar alerta ahora';
  }, 2500);
}

async function refrescarBadge() {
  try {
    const r = await fetch('/badge/estado');
    const badges = await r.json();
    const contenedor = document.getElementById('badge-contenedor');
    const cardsGrid = document.getElementById('badge-cards');
    const none = document.getElementById('badge-none');
    const tarjetasEPP = document.getElementById('tarjetas-epp');

    if (!badges || badges.length === 0) {
      cardsGrid.style.display = 'none';
      none.style.display = 'block';
      tarjetasEPP.style.display = 'none';
      contenedor.style.display = 'block';
      return;
    }

    none.style.display = 'none';
    cardsGrid.style.display = 'grid';
    contenedor.style.display = 'block';

    // Construir HTML de TODAS las cards (30 empleados siempre visibles)
    let html = '';
    const mapeoEPP = {casco:'epp-casco', gafas:'epp-gafas', guantes:'epp-guantes', botas:'epp-botas'};
    const iconosEPP = {casco:'🪖', gafas:'👓', guantes:'🧤', botas:'🥾'};

    const emojiPorPuesto = {
      supervisor_hse: '🦺',
      albañil: '🧱',
      electricista: '⚡',
      ayudante: '🛠️',
      operario_grua: '🏗️',
      soldador: '🔥',
    };

    for (const b of badges) {
      const activo = b.activo === true;
      const chipClass = activo ? 'chip-activo' : 'chip-bloqueado';
      const chipText = activo ? 'ACTIVO' : 'BLOQUEADO';
      const dentro = b.dentro === true;
      const emoji = emojiPorPuesto[b.puesto] || '👷';

      // Estado Adentro/Afuera
      const estadoTexto = dentro ? 'ADENTRO' : 'AFUERA';

      // Temporizador: si está adentro, mostrar tiempo transcurrido
      let temporizadorHtml = '';
      if (dentro) {
        temporizadorHtml = `
          <div class="temporizador">
            <span class="label-temp">Tiempo:</span>
            <span class="valor-temp" id="temp-${b.badge_id}">0:00</span>
          </div>`;
      }

      // Iconos EPP: gris inicialmente, rojo/verde solo si detectado_recientemente
      const detectado = b.detectado_recientemente === true;
      const epp = detectado ? (b.epp || {}) : {};
      let eppHtml = '';
      Object.entries(mapeoEPP).forEach(([clave]) => {
        const val = epp[clave];
        const estadoCls = detectado
          ? (val === true ? 'tiene' : (val === false ? 'falta' : 'sin-detectar'))
          : 'sin-detectar';
        eppHtml += `<div class="epp-icon ${estadoCls}" id="epp-${clave}-${b.badge_id}">
          ${iconosEPP[clave]||'❓'}<span class="nombre">${clave}</span>
        </div>`;
      });

      // Resumen de horas/pago
      let resumenHtml = '';
      if (b.existe !== false) {
        resumenHtml = `
          <div class="resumen-badge">
            <div class="row"><span class="label">Hoy:</span><span class="valor" id="horas-${b.badge_id}">${b.horas_hoy||0}</span> h</div>
            <div class="row"><span class="label">Semana:</span><span class="valor" id="horas-semana-${b.badge_id}">${b.horas_semana||0}</span> h</div>
            <div class="row"><span class="label">Valor semana:</span><span class="valor" id="valor-semana-${b.badge_id}">$${(b.valor_semana||0).toLocaleString('es-CO')}</span></div>
            <div class="row"><span class="label">Estado:</span><span class="valor estado-${dentro?'adentro':'afuera'}">${estadoTexto}</span></div>
            ${temporizadorHtml}
          </div>`;
      }

      html += `
        <div class="badge-card-compacta">
          <div class="qr-placeholder" style="font-size:1.5rem;">${emoji}</div>
          <h2>${b.nombre || '—'}</h2>
          <div class="sub">${b.puesto || '—'}</div>
          <span class="chip ${chipClass}">${chipText}</span>
          <div class="epp-iconos">${eppHtml}</div>
          <div class="badge-meta">
            <div>Badge: ${b.badge_id || '—'}</div>
            <div>Turno: ${b.turno || '—'}</div>
          </div>
          <div class="badge-actions">
            <button class="boton btn-entrada" data-badge="${b.badge_id}">✅ Entrada</button>
            <button class="boton btn-salida" data-badge="${b.badge_id}">🚪 Salida</button>
          </div>
          ${resumenHtml}
        </div>`;
    }

    cardsGrid.innerHTML = html;

    // Vincular eventos de botones dinámicos
    document.querySelectorAll('.btn-entrada').forEach(btn => {
      btn.onclick = (e) => marcarBadge(e.target.dataset.badge, 'entrada');
    });
    document.querySelectorAll('.btn-salida').forEach(btn => {
      btn.onclick = (e) => marcarBadge(e.target.dataset.badge, 'salida');
    });

    // Actualizar resúmenes y temporizadores para cada badge
    for (const b of badges) {
      if (b.badge_id) {
        try {
          const r2 = await fetch('/badge/resumen/' + encodeURIComponent(b.badge_id));
          const s = await r2.json();
          if (s.existe) {
            const h = document.getElementById(`horas-${b.badge_id}`);
            const v = document.getElementById(`valor-${b.badge_id}`);
            const hs = document.getElementById(`horas-semana-${b.badge_id}`);
            const vs = document.getElementById(`valor-semana-${b.badge_id}`);
            const e = document.getElementById(`estado-${b.badge_id}`);
            const t = document.getElementById(`temp-${b.badge_id}`);
            if (h) h.textContent = s.horas_hoy || 0;
            if (v) v.textContent = '$' + (s.valor_pagar || 0).toLocaleString('es-CO');
            if (hs) hs.textContent = s.horas_semana || 0;
            if (vs) vs.textContent = '$' + (s.valor_semana || 0).toLocaleString('es-CO');
            if (e) e.textContent = s.dentro ? 'ADENTRO' : 'AFUERA';
            if (t && s.dentro && s.horas_dentro_ahora !== null) {
              const totalSegundos = Math.floor(s.horas_dentro_ahora * 3600);
              const hh = Math.floor(totalSegundos / 3600);
              const mm = Math.floor((totalSegundos % 3600) / 60);
              const ss = totalSegundos % 60;
              t.textContent = `${hh}:${mm.toString().padStart(2,'0')}:${ss.toString().padStart(2,'0')}`;
            }
          }
        } catch (err) { /* resumen opcional */ }
      }
    }

  } catch (err) { /* reintenta en el proximo tick */ }
}

async function marcarBadge(badgeId, accion) {
  if (!badgeId || badgeId === '—') return;
  const btn = event.target;
  btn.disabled = true; btn.textContent = '⏳…';
  try {
    const r = await fetch('/badge/marcar/' + encodeURIComponent(badgeId) + '/' + accion, {method:'POST'});
    const e = await r.json();
    if (e.ok) {
      btn.textContent = accion === 'entrada' ? '✅ Entrada' : '🚪 Salida';
      setTimeout(() => { btn.disabled = false; }, 1500);
      setTimeout(() => { refrescarBadge(); }, 800);
    } else {
      btn.textContent = '⚠️ ' + (e.motivo || 'error');
      setTimeout(() => { btn.disabled = false; btn.textContent = accion === 'entrada' ? '✅ Entrada' : '🚪 Salida'; }, 2000);
    }
  } catch (err) {
    btn.textContent = '⚠️ error de red';
    setTimeout(() => { btn.disabled = false; btn.textContent = accion === 'entrada' ? '✅ Entrada' : '🚪 Salida'; }, 2000);
  }
}

async function refrescar() {
  try {
    const r = await fetch('/estado');
    const e = await r.json();
    document.getElementById('sub').textContent =
      `zona: ${e.zona} · perfil: ${e.perfil} · modelo: ${e.modelo} · ${e.whatsapp_modo}`;
    document.getElementById('estado-camara').textContent =
      e.estado_camara_mensaje || 'Reconociendo…';
    const nombres = {'Person':'Personas','helmet':'Cascos','no_helmet':'SIN CASCO',
      'gloves':'Guantes','no_gloves':'SIN GUANTES','vest':'Chalecos',
      'boots':'Botas','no_boots':'SIN BOTAS','goggles':'Gafas',
      'no_goggle':'SIN GAFAS','none':'None'};
    document.getElementById('tarjetas').innerHTML = Object.entries(e.detecciones)
      .map(([k,v]) => `<div class="tarjeta"><div class="num ${k.startsWith('no_')&&v>0?'falta':'ok'}">${v}</div><div class="etq">${nombres[k]||k}</div></div>`)
      .join('');
    const ids = e.incidentes.map(i=>i.t).join(',');
    if (ids !== ultimosIds) {
      ultimosIds = ids;
      document.getElementById('log').innerHTML = e.incidentes.length
        ? e.incidentes.map(i=>`<div class="incidente"><div class="hora">${i.t} · zona ${i.zona}</div>${i.faltas}</div>`).join('')
        : '<div class="vacio">sin incidentes todavía…</div>';
    }
    actualizarBotonWA(e.whatsapp_activo);
    document.getElementById('faltas-badge').textContent =
      e.faltas_actuales.length
        ? '⚠️ faltas actuales: ' + e.faltas_actuales.map(f=>f.clase).join(', ')
        : '';
    document.getElementById('estado').innerHTML =
      `<span class="punto"></span>procesando a ${e.fps} FPS · latencia ${e.latencia_ms} ms/frame · ${e.frames} frames`;
    refrescarBadge();
    refrescarJornadaAlertas(e.alertas_jornada || []);
  } catch (err) { /* reintenta en el proximo tick */ }
}

async function refrescarJornadaAlertas(alertas) {
  const cont = document.getElementById('log-jornada');
  if (!alertas || alertas.length === 0) {
    cont.innerHTML = '<div class="vacio">sin alertas de jornada…</div>';
    return;
  }
  cont.innerHTML = alertas.map(a => {
    const esMalTrazada = a.tipo_alerta === 'salida_mal_trazada';
    const icono = esMalTrazada ? '🕒' : '⚠️';
    const colorTipo = esMalTrazada ? 'var(--azul)' : 'var(--rojo)';
    const excede = a.excede_jornada_maxima ? ' (EXCEDE JORNADA MÁXIMA)' : '';
    const motivo = a.motivo || '';
    return `
      <div class="alerta-jornada" style="border-left-color:${colorTipo};">
        <div class="hora" style="color:${colorTipo};">${icono} ${a.nombre || 'Desconocido'} (${a.badge || '—'})${excede}</div>
        <div class="detalle">
          ${esMalTrazada ? '<strong>Salida mal trazada:</strong> ' : ''}
          Entró: ${a.hora_entrada ? new Date(a.hora_entrada).toLocaleTimeString('es-CO') : '—'} ·
          Horas dentro: ${a.horas_dentro} h ·
          Turno: ${a.turno || '—'} ·
          Puesto: ${a.puesto || '—'}
        </div>
        <div class="detalle" style="font-size:.7rem; color:var(--gris); margin-top:4px;">${motivo}</div>
        ${a.excede_jornada_maxima
          ? `<button class="btn-forzar" onclick="forzarSalida('${a.badge_id}')">Forzar salida y cancelar nómina</button>`
          : '<span style="color:var(--gris); font-size:.7rem;">Requiere revisión del supervisor</span>'
        }
      </div>`;
  }).join('');
}

async function forzarSalida(badgeId) {
  if (!badgeId) return;
  if (!confirm(`¿Forzar salida y cancelar nómina del badge ${badgeId}?`)) return;
  try {
    const r = await fetch('/badge/salida-forzada/' + encodeURIComponent(badgeId), {method:'POST'});
    const e = await r.json();
    if (e.ok) {
      alert(`Salida forzada registrada para ${e.nombre || badgeId}`);
      refrescar();
    } else {
      alert('Error: ' + (e.motivo || 'desconocido'));
    }
  } catch (err) {
    alert('Error de red');
  }
}

setInterval(refrescar, 1500); refrescar();
</div></script></body></html>"""


class ActuadorWhatsAppAsync(ActuadorWhatsApp):
    """Encola los envíos: el worker los manda por HTTP sin congelar el video.

    E32: bandera `activo` (pausa desde el panel). En pausa, los incidentes
    se siguen confirmando y registrando en el panel/historial, pero NO se
    envían por WhatsApp.
    """

    def __init__(self, cola):
        super().__init__()
        self.cola = cola
        self.activo = True

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        if not self.activo:
            clases = ", ".join(i.clase for i in incidentes)
            print(f"🔕 WhatsApp PAUSADO: lote ({len(incidentes)} faltas: "
                  f"{clases}) registrado en panel/historial, NO enviado",
                  flush=True)
            return None
        import copy
        frame = frame_anotado.copy() if frame_anotado is not None else None
        self.cola.put((incidentes, frame))
        clases = ", ".join(i.clase for i in incidentes)
        print(f"📨 encolado para WhatsApp ({len(incidentes)} faltas): {clases}",
              flush=True)

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        self.alertar_lote([incidente], frame_anotado, ruta_frame)


class PanelSafeSite:
    def __init__(self, zona, device, usar_whatsapp=False, perfil="vivo"):
        self.zona = zona
        self.perfil = perfil
        self.cola = queue.Queue()
        actuadores = [ActuadorConsola()]
        self.whatsapp_real = ActuadorWhatsApp() if usar_whatsapp else None
        self.actuador_async = None
        if usar_whatsapp:
            self.actuador_async = ActuadorWhatsAppAsync(self.cola)
            actuadores.append(self.actuador_async)
        # E33/E35: el panel corre por defecto con el perfil VIVO (umbrales
        # por clase + regla de coherencia calibrados en el piloto);
        # --perfil evaluacion reproduce el umbral global 0.15 de la suite.
        perfil_umbrales = (config.UMBRALES_INCUMPLIMIENTO_VIVO
                           if perfil == "vivo" else None)
        coherencia = (config.REGLA_COHERENCIA_VIVO
                      if perfil == "vivo" else None)
        self.agente = SafeSiteAgent(device=device, actuadores=actuadores,
                                    perfil_umbrales=perfil_umbrales,
                                    coherencia=coherencia)
        self.lock = threading.Lock()
        self.ultimo_frame = None          # anotado, para el stream
        self._faltas = []                 # detecciones no_* del ultimo frame
        self.latencias = collections.deque(maxlen=30)
        self.frames = 0
        self.marca_fps = time.time()
        self.fps = 0.0
        self.incidentes = collections.deque(maxlen=50)
        # ---------- maquina de estados de la camara (Fase 1) ----------
        self.estado_camara = config.ESTADO_RECONOCIENDO
        self.estado_camara_ts = time.time()
        self.estado_camara_mensaje = "Reconociendo…"
        self._badge_en_proceso = None   # badge_id que esta siendo procesado ahora
        # ---------- lector de badges QR (hilo separado para >=30 FPS) ----------
        self.lector_qr = LectorBadgeQR(cooldown_segundos=2.0,
                                       detectar_cada_n_frames=10)
        self.lector_qr.iniciar()  # hilo separado: no bloquea el video
        self.ultima_lectura = None   # LecturaBadge más reciente
        self.badges_activos = {}     # badge_id -> {"datos": dict, "ultima_deteccion": float}
        self._ultima_marcacion = {}  # badge_id -> timestamp de última entrada/salida automática
        # Las cards de badge se mantienen visibles hasta que el trabajador
        # marque salida (no expiran por tiempo).

    # ---------- bucle de captura ----------
    def _capturar(self):
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cam.isOpened():
            raise RuntimeError("no se pudo abrir la webcam (¿la usa otra app?)")
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        print(f"🎥 webcam abierta ({int(cam.get(3))}x{int(cam.get(4))})", flush=True)
        while True:
            try:
                hay_badge_activo = False
                lectura = None
                ok, frame = cam.read()
                if not ok:
                    time.sleep(0.01)
                    continue

                print(f"🔄 [bucle] inicio iteración", flush=True)

                # ---------- lectura de badge QR (hilo separado, no bloquea) ----------
                self.lector_qr.encolar_frame(frame)
                lecturas = self.lector_qr.obtener_lecturas()
                print(f"📡 [bucle] lecturas QR obtenidas: {len(lecturas)}", flush=True)

                ahora_ts = time.time()

                # Determinar si hay un badge ACTIVO detectado
                # Prioridad: lecturas del frame actual, luego última lectura reciente como respaldo
                lectura = None
                if lecturas:
                    lectura = lecturas[0]
                    self.ultima_lectura = lectura
                elif self.ultima_lectura and self.ultima_lectura.badge \
                        and (ahora_ts - self.ultima_lectura.badge.timestamp) < 3.0:
                    lectura = self.ultima_lectura

                if lectura and lectura.badge and lectura.badge.valido:
                    hay_badge_activo = True
                    bid = lectura.badge.badge_id
                    nombre = lectura.badge.nombre or "trabajador"
                    pass  # log silencioso: badge activo detectado
                else:
                    bid = None
                    nombre = None

                # ---------- maquina de estados de la camara ----------
                if not hay_badge_activo:
                    self.estado_camara = config.ESTADO_RECONOCIENDO
                    self.estado_camara_mensaje = "Reconociendo…"
                    self._badge_en_proceso = None
                elif lectura and lectura.badge:
                    # Nuevo badge detectado o re-detección
                    if self._badge_en_proceso is None or self._badge_en_proceso != bid:
                        self._badge_en_proceso = bid
                        self.estado_camara = config.ESTADO_RECONOCIDO
                        self.estado_camara_mensaje = (
                            f"Miembro de personal reconocido: {nombre}")
                        print(f"🟢 [bucle] estado → RECONOCIDO para {bid}", flush=True)
                    else:
                        self.estado_camara = config.ESTADO_ESCANEANDO_EPP
                        self.estado_camara_mensaje = "Escaneando EPP apropiado…"
                        print(f"🔍 [bucle] estado → ESCANEANDO_EPP para {bid}", flush=True)

                if hay_badge_activo:
                    try:
                        print(f"⚙️ [bucle] llamando a procesar_frame…", flush=True)
                        incidentes, filtradas = self.agente.procesar_frame(
                            frame, zona=self.zona, t_stamp=time.time())
                        anotado = self.agente.percepcion.anotar(frame, filtradas)
                        self._conteos = self._contar(filtradas)
                        self._faltas = [d for d in filtradas
                                        if d.cls_id in config.CLASES_INCUMPLIMIENTO]
                    except Exception as e:
                        print(f"❌ error procesando frame YOLO: {e}", flush=True)
                        incidentes = []
                        filtradas = []
                        anotado = frame.copy()
                        self._conteos = {}
                        self._faltas = []
                else:
                    incidentes = []
                    filtradas = []
                    anotado = frame.copy()
                    self._conteos = {}
                    self._faltas = []
                print(f"✅ [bucle] procesar_frame completado, incidentes={len(incidentes)}, filtradas={len(filtradas)}", flush=True)

                # ---------- recuadro del QR (persiste mientras haya lectura reciente) ----------
                lectura_dibujar = lecturas[0] if lecturas else self.ultima_lectura
                if lectura_dibujar and lectura_dibujar.caja \
                        and lectura_dibujar.badge \
                        and (ahora_ts - lectura_dibujar.badge.timestamp) < 3.0:
                    print(f"📐 [bucle] dibujando recuadro QR", flush=True)
                    x1, y1, x2, y2 = [int(v) for v in lectura_dibujar.caja]
                    es_valido = (lectura_dibujar.badge is not None
                                 and lectura_dibujar.badge.valido)
                    color = (0, 200, 0) if es_valido else (0, 0, 200)
                    cv2.rectangle(anotado, (x1, y1), (x2, y2), color, 3)
                    etiqueta = "QR VALIDO" if es_valido else "QR"
                    cv2.putText(anotado, etiqueta, (x1, max(y1 - 10, 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                with self.lock:
                    self.ultimo_frame = anotado
                    print(f"🖼️ [bucle] frame anotado guardado en ultimo_frame", flush=True)

                    # ---------- gestionar badge activo ----------
                    if hay_badge_activo and lectura and lectura.badge:
                        bid = lectura.badge.badge_id

                        # Construir datos del badge para el frontend
                        if lectura.badge.valido:
                            epp = self._estado_epp(filtradas) \
                                if lectura.badge.estado_badge == "activo" else None
                            datos = {
                                "badge_id": lectura.badge.badge_id,
                                "id_empleado": lectura.badge.id_empleado,
                                "nombre": lectura.badge.nombre,
                                "puesto": lectura.badge.puesto,
                                "turno": lectura.badge.turno,
                                "estado_badge": lectura.badge.estado_badge,
                                "timestamp": lectura.badge.timestamp,
                                "activo": lectura.badge.estado_badge == "activo",
                                "epp": epp,
                            }
                        else:
                            datos = {
                                "badge_id": lectura.badge.badge_id or "?",
                                "id_empleado": "",
                                "nombre": "DESCONOCIDO",
                                "puesto": "",
                                "turno": "",
                                "estado_badge": lectura.badge.estado_badge or "desconocido",
                                "timestamp": lectura.badge.timestamp or ahora_ts,
                                "activo": False,
                                "epp": None,
                            }

                        # Guardar o actualizar el badge activo (se mantiene hasta salida)
                        self.badges_activos[bid] = {
                            "datos": datos,
                            "ultima_deteccion": ahora_ts,
                        }
                        print(f"💾 [bucle] badge guardado en badges_activos: {bid}", flush=True)

                        # ---------- entrada/salida automática al reconocer el QR ----------
                        if lectura.badge.valido and lectura.badge.estado_badge == "activo":
                            ultima = self._ultima_marcacion.get(bid, 0)
                            print(f"⏱️ [bucle] cooldown check: ahora_ts={ahora_ts:.1f}, ultima={ultima:.1f}, diff={ahora_ts-ultima:.1f}s", flush=True)
                            if ahora_ts - ultima >= 5.0:  # cooldown de 5s entre marcaciones
                                try:
                                    dentro = registro_asistencia.esta_dentro(bid)
                                    print(f"🚪 [bucle] esta_dentro({bid})={dentro}", flush=True)
                                    if dentro:
                                        print(f"🚪 [bucle] llamando a marcar_salida({bid})…", flush=True)
                                        registro_asistencia.marcar_salida(bid)
                                        print(f"🚪 [bucle] SALIDA automática: {bid} ({nombre})", flush=True)
                                    else:
                                        print(f"✅ [bucle] llamando a marcar_entrada({bid})…", flush=True)
                                        registro_asistencia.marcar_entrada(bid)
                                        print(f"✅ [bucle] ENTRADA automática completada: {bid} ({nombre})", flush=True)
                                    self._ultima_marcacion[bid] = ahora_ts
                                    print(f"💾 [bucle] _ultima_marcacion[{bid}]={ahora_ts:.1f}", flush=True)
                                except Exception as e:
                                    print(f"❌ [bucle] Error marcando badge {bid}: {type(e).__name__}: {e}", flush=True)
                                    self._ultima_marcacion[bid] = ahora_ts  # evitar reintento inmediato
                self.frames += 1
                ahora = time.time()
                if ahora - self.marca_fps >= 1.0:
                    self.fps = round(self.frames / (ahora - self.marca_fps), 1)
                    self.frames = 0
                    self.marca_fps = ahora
                for inc in incidentes:
                    self.incidentes.append({
                        "t": time.strftime("%H:%M:%S"),
                        "zona": inc.zona,
                        "faltas": f"<b>{inc.clase}</b> (conf {inc.conf_media:.0%}, "
                                  f"{inc.frames_consecutivos} frames)",
                    })
                print(f"🏁 [bucle] fin de iteración, fps={self.fps}", flush=True)
            except Exception as e:
                print(f"❌ error en bucle de captura: {e}", flush=True)
                time.sleep(0.1)
                continue

    @staticmethod
    def _contar(filtradas):
        conteos = {nombre: 0 for nombre in config.NOMBRES_CLASES.values()}
        for d in filtradas:
            conteos[d.nombre] = conteos.get(d.nombre, 0) + 1
        return conteos

    # ---------- estado EPP asociado al badge (H4) ----------
    @staticmethod
    def _estado_epp(filtradas):
        """Determina si la persona tiene o le falta cada EPP.

        Devuelve dict: {casco, gafas, guantes, botas} con valores
        True (tiene), False (falta) o None (no detectado en el frame).
        Prioridad: si hay detección positiva y negativa para la misma parte,
        se gana la positiva (coherencia).
        """
        nombres = {d.nombre for d in filtradas}
        return {
            "casco": True if "helmet" in nombres else (False if "no_helmet" in nombres else None),
            "gafas": True if "goggles" in nombres else (False if "no_goggle" in nombres else None),
            "guantes": True if "gloves" in nombres else (False if "no_gloves" in nombres else None),
            "botas": True if "boots" in nombres else (False if "no_boots" in nombres else None),
        }

    # ---------- worker de WhatsApp ----------
    def _enviar_whatsapp(self):
        while True:
            incidentes, frame = self.cola.get()
            if self.whatsapp_real is None:
                continue
            try:
                self.whatsapp_real.alertar_lote(incidentes, frame_anotado=frame)
            except Exception as e:
                print(f"❌ worker WhatsApp: {e}", flush=True)

    def iniciar(self):
        threading.Thread(target=self._capturar, daemon=True).start()
        if self.whatsapp_real is not None:
            threading.Thread(target=self._enviar_whatsapp, daemon=True).start()

    # ---------- endpoints ----------
    def frame_jpeg(self):
        with self.lock:
            frame = self.ultimo_frame
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if ok else None

    # ---------- control del canal WhatsApp (E32) ----------

    def toggle_whatsapp(self):
        """Alterna la pausa del envío de WhatsApp.

        En pausa: los incidentes se confirman y quedan en el log del panel
        y en el historial, pero no llegan al teléfono. El botón 'Enviar
        alerta ahora' sigue funcionando (petición explícita)."""
        if self.actuador_async is None:
            return None
        self.actuador_async.activo = not self.actuador_async.activo
        estado = "REANUDADO" if self.actuador_async.activo else "PAUSADO"
        print(f"🔔 WhatsApp {estado} desde el panel", flush=True)
        return self.actuador_async.activo

    def enviar_alerta_manual(self):
        """Envía por WhatsApp el estado actual de la zona bajo petición
        explícita (forzar=True: bypass de pausa y de límites anti-spam)."""
        if self.whatsapp_real is None:
            return {"ok": False,
                    "detalle": "panel iniciado con --sin-whatsapp"}
        with self.lock:
            faltas = list(self._faltas)
            frame = self.ultimo_frame
        frame = frame.copy() if frame is not None else None
        ahora = time.time()
        # deduplicar por clase (dos personas sin casco = 1 falta en el msg)
        por_clase = {}
        for d in faltas:
            if d.cls_id not in por_clase or d.conf > por_clase[d.cls_id].conf:
                por_clase[d.cls_id] = d
        incidentes = [
            Incidente(zona=self.zona, clase_id=d.cls_id, clase=d.nombre,
                      conf_media=d.conf, frames_consecutivos=0,
                      t_confirmacion=ahora, t_inicio_deteccion=ahora,
                      origen_ultimo_frame="manual")
            for d in sorted(por_clase.values(), key=lambda x: x.cls_id)]
        if incidentes:
            wamid = self.whatsapp_real.alertar_lote(
                incidentes, frame_anotado=frame, forzar=True)
            return {"ok": bool(wamid),
                    "faltas": [i.clase for i in incidentes],
                    "detalle": None if wamid else "envío falló (ver consola)"}
        # sin faltas actuales: mensaje de estado de prueba del canal
        if self.whatsapp_real.modo != "ENVIO-REAL":
            print("📲 WhatsApp[DRY-RUN] manual: zona sin incumplimientos",
                  flush=True)
            return {"ok": True, "faltas": [], "detalle": "dry-run"}
        try:
            hora = datetime.now().strftime("%I:%M %p").lstrip("0")
            self.whatsapp_real.enviar_texto(
                f"✅ SafeSite — {hora}\n\nZona {self.zona}: sin "
                f"incumplimientos en el último fotograma (prueba manual "
                f"del canal desde el panel).")
            return {"ok": True, "faltas": [], "detalle": None}
        except Exception as e:
            print(f"❌ WhatsApp manual: {e}", flush=True)
            return {"ok": False, "faltas": [], "detalle": str(e)[:80]}

    def estado(self):
        with self.lock:
            conteos = dict(getattr(self, "_conteos", {}))
            faltas = [{"clase": d.nombre, "conf": round(d.conf, 2)}
                      for d in getattr(self, "_faltas", [])]
            # Solo badges detectados (cards dinámicas - aparecen al escanear QR)
            badges_lista = []
            for bid, d in self.badges_activos.items():
                datos = d["datos"].copy()
                ahora_ts = time.time()
                # EPP activo solo por 8 segundos después de detectar el badge
                datos["detectado_recientemente"] = (ahora_ts - d["ultima_deteccion"]) < 8.0
                datos["tiempo_deteccion"] = d["ultima_deteccion"]
                badges_lista.append(datos)
        # Alertas de jornada sin salida
        alertas_jornada = registro_asistencia.obtener_jornadas_sin_salida()
        return {
            "zona": self.zona,
            "perfil": self.perfil,
            "modelo": config.RUTA_MODELO.split("/")[-3] if "/" in config.RUTA_MODELO else config.RUTA_MODELO,
            "fps": self.fps,
            "latencia_ms": round(self.agente.latencia_media_ms, 1),
            "detecciones": conteos,
            "incidentes": list(self.incidentes),
            "whatsapp_activo": (self.actuador_async.activo
                                if self.actuador_async else False),
            "whatsapp_modo": (self.whatsapp_real.modo
                              if self.whatsapp_real else "DESHABILITADO"),
            "faltas_actuales": faltas,
            "badges": badges_lista,
            "badge": badges_lista[0] if badges_lista else None,
            "alertas_jornada": alertas_jornada,
            # ---------- maquina de estados de la camara ----------
            "estado_camara": self.estado_camara,
            "estado_camara_mensaje": self.estado_camara_mensaje,
        }

    # ---------- endpoints de badges v2 ----------
    def badge_estado(self):
        """Devuelve solo badges detectados recientemente (cards dinámicas).
        Aparecen al escanear QR, desaparecen al marcar salida."""
        try:
            badges_lista = []
            ahora_ts = time.time()
            with self.lock:
                for bid, d in self.badges_activos.items():
                    datos = d["datos"].copy()
                    datos["detectado_recientemente"] = (ahora_ts - d["ultima_deteccion"]) < 8.0
                    datos["tiempo_deteccion"] = d["ultima_deteccion"]
                    badges_lista.append(datos)
            print(f"📡 [estado] badge_estado devolviendo {len(badges_lista)} badges: {[b.get('badge_id') for b in badges_lista]}", flush=True)
            return badges_lista
        except Exception as e:
            print(f"❌ [estado] error en badge_estado: {e}", flush=True)
            return []

    def badge_jornada_alertas(self):
        """Devuelve alertas de empleados que excedieron la jornada sin salir."""
        return registro_asistencia.obtener_jornadas_sin_salida()

    def badge_salida_forzada(self, badge_id):
        """El administrador forza la salida de un empleado que excedió la jornada."""
        return registro_asistencia.cancelar_nomina_por_olvido_salida(badge_id)

    def badge_marcar(self, badge_id, accion):
        """Marca entrada o salida de un badge (acción explícita desde el panel)."""
        if accion == "entrada":
            return registro_asistencia.marcar_entrada(badge_id)
        if accion == "salida":
            return registro_asistencia.marcar_salida(badge_id)
        return {"ok": False, "detalle": "acción inválida"}

    def badge_resumen(self, badge_id):
        """Resumen completo de un badge (estado, horas, valor a pagar)."""
        return registro_asistencia.resumen_empleado(badge_id)

    def badge_todos(self):
        """Listado de todos los empleados con su estado actual."""
        return registro_asistencia.listar_todos()


def main():
    parser = argparse.ArgumentParser(
        description="Panel web de SafeSite-Agent con detección en vivo")
    parser.add_argument("--zona", default="obra_cam1")
    parser.add_argument("--device", default="0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--perfil", default="vivo",
                        choices=("vivo", "evaluacion"),
                        help="umbrales por clase: vivo (calibrado en piloto) "
                             "o evaluacion (umbral global 0.15 de la suite)")
    parser.add_argument("--con-whatsapp", action="store_true",
                        help="activa el envío real de WhatsApp (desactivado por defecto)")
    args = parser.parse_args()

    panel = PanelSafeSite(args.zona, args.device,
                          usar_whatsapp=args.con_whatsapp,
                          perfil=args.perfil)
    app = Flask(__name__)

    @app.route("/")
    def indice():
        return PAGINA

    @app.route("/video")
    def video():
        def flujo():
            while True:
                jpeg = panel.frame_jpeg()
                if jpeg:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                           + jpeg + b"\r\n")
                time.sleep(1 / 30)
        return Response(flujo(),
                        mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/estado")
    def estado():
        return jsonify(panel.estado())

    @app.route("/whatsapp/toggle", methods=["POST"])
    def whatsapp_toggle():
        nuevo = panel.toggle_whatsapp()
        return jsonify({
            "whatsapp_activo": nuevo,
            "whatsapp_modo": (panel.whatsapp_real.modo
                              if panel.whatsapp_real else "DESHABILITADO"),
        })

    @app.route("/alerta/manual", methods=["POST"])
    def alerta_manual():
        return jsonify(panel.enviar_alerta_manual())

    # ---------- rutas de badges v2 ----------
    @app.route("/badge/estado")
    def badge_estado():
        return jsonify(panel.badge_estado())

    @app.route("/badge/marcar/<badge_id>/<accion>", methods=["POST"])
    def badge_marcar(badge_id, accion):
        return jsonify(panel.badge_marcar(badge_id, accion))

    @app.route("/badge/resumen/<badge_id>")
    def badge_resumen(badge_id):
        return jsonify(panel.badge_resumen(badge_id))

    @app.route("/badge/todos")
    def badge_todos():
        return jsonify(panel.badge_todos())

    # ---------- rutas de jornada y salida forzada ----------
    @app.route("/badge/jornada-alertas")
    def badge_jornada_alertas():
        return jsonify(panel.badge_jornada_alertas())

    @app.route("/badge/salida-forzada/<badge_id>", methods=["POST"])
    def badge_salida_forzada(badge_id):
        return jsonify(panel.badge_salida_forzada(badge_id))

    panel.iniciar()
    modo_wa = (panel.whatsapp_real.modo if panel.whatsapp_real
               else "DESHABILITADO")
    print(f"🖥️  panel en http://localhost:{args.port} | zona: {args.zona} | "
          f"perfil: {args.perfil} | device: {args.device} | "
          f"WhatsApp: {modo_wa}", flush=True)
    app.run(host="127.0.0.1", port=args.port, threaded=True,
            use_reloader=False, debug=False)


if __name__ == "__main__":
    main()
