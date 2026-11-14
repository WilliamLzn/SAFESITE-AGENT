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
  :root { --fondo:#0f172a; --tarjeta:#1e293b; --texto:#f8fafc; --verde:#10b981;
          --rojo:#ef4444; --azul:#3b82f6; --gris:#64748b; --sombra:0 4px 6px -1px rgba(0,0,0,0.1);
          --sombra-lg:0 10px 15px -3px rgba(0,0,0,0.1); }
  body { background:var(--fondo); color:var(--texto); font-family:'Inter',system-ui,
         sans-serif; margin:0; padding:0; }
  h1 { font-size:1.5rem; margin:0 0 2px; font-weight:700; letter-spacing:-0.02em; }
  .sub { color:var(--gris); font-size:.85rem; margin-bottom:16px; font-weight:400; }
  .header { display:flex; align-items:center; gap:12px; margin-bottom:20px; padding:0 20px; }
  .layout { display:grid; grid-template-columns:45% 55%; gap:20px;
            grid-template-rows: auto; padding:0 20px 20px; }
  @media (max-width:900px){ .layout{grid-template-columns:1fr;} }
  .video-container { position:relative; width:100%; max-width:640px; border-radius:16px;
             background:#000; aspect-ratio:16/9; object-fit:contain; margin:0 auto;
             box-shadow:var(--sombra-lg); border:1px solid rgba(255,255,255,0.08); }
  .video { width:100%; height:100%; border-radius:16px; object-fit:cover; }
  .video-overlay { position:absolute; top:12px; left:12px; right:12px; bottom:12px;
             border:2px solid rgba(255,255,255,0.1); border-radius:16px;
             pointer-events:none; }

  /* ---------- contenedor scrollable de badges (Material Design) ---------- */
  #badge-contenedor { height: 520px; overflow-y: auto; border-radius: 16px;
             background: rgba(30,41,59,0.4); display: grid;
             grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; padding: 20px;
             width: 100%; border: 1px solid rgba(255,255,255,0.06);
             box-shadow: var(--sombra); }
  #badge-contenedor::-webkit-scrollbar { width: 6px; }
  #badge-contenedor::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); }
  #badge-contenedor::-webkit-scrollbar-thumb { background: var(--gris); border-radius: 4px; }

  /* ---------- tarjeta de badge Material Design ---------- */
  .badge-card-compacta { background: var(--tarjeta); border-radius: 12px; padding: 16px;
             margin: 0; border: 1px solid rgba(255,255,255,0.08);
             display: flex; flex-direction: column; align-items: center; gap: 10px;
             height: auto; min-height: 220px; width: 100%;
             box-shadow: var(--sombra); transition: all 0.2s ease; }
  .badge-card-compacta:hover { transform: translateY(-2px); box-shadow: var(--sombra-lg);
             border-color: rgba(255,255,255,0.15); }
  .badge-card-compacta .qr-placeholder { width: 70px; height: 70px; background: #000;
             border-radius: 10px; margin: 4px auto 2px; display: flex;
             align-items: center; justify-content: center; color: #666;
             font-size: 0.5rem; border: 2px solid var(--azul); }
  .badge-card-compacta h2 { margin: 0 0 2px; font-size: 1rem; font-weight: 600; }
  .badge-card-compacta .sub { color: var(--gris); font-size: 0.7rem; margin-bottom: 2px; }
  .badge-card-compacta .chip { display: inline-block; padding: 4px 10px; border-radius: 20px;
             font-size: 0.65rem; font-weight: 600; margin: 2px 0; }
  .chip-activo { background: var(--verde); color: #fff; }
  .chip-bloqueado { background: var(--rojo); color: #fff; }
  .badge-card-compacta .badge-meta { font-size: 0.65rem; color: var(--gris);
             text-align: center; margin-top: 4px; width: 100%; }
  .badge-card-compacta .epp-iconos { display: flex; gap: 6px; justify-content: center;
             margin: 6px 0; flex-wrap: wrap; }
  .badge-card-compacta .epp-icon { width: 40px; height: 40px; border-radius: 10px; display: flex;
             flex-direction: column; align-items: center; justify-content: center;
             font-size: 1rem; border: 2px solid; }
  .badge-card-compacta .epp-icon .nombre { font-size: 0.55rem; margin-top: 2px; font-weight: 600;
             text-transform: uppercase; letter-spacing: 0.02em; }
  .badge-card-compacta .badge-actions { margin-top: 4px; display: flex; gap: 6px;
             justify-content: center; width: 100%; }
  .badge-card-compacta .boton { font-size: 0.65rem; padding: 4px 10px; flex:1; }
  .badge-card-compacta .resumen-badge { background: rgba(255,255,255,0.04); border-radius: 8px;
             padding: 8px; margin-top: 6px; text-align: center; font-size: 0.65rem;
             border: 1px solid rgba(255,255,255,0.06); width: 100%; }
  .badge-card-compacta .resumen-badge .row { display: flex; justify-content: space-between;
             margin-bottom: 2px; }
  .badge-card-compacta .resumen-badge .label { color: var(--gris); }
  .badge-card-compacta .resumen-badge .valor { font-weight: 600; }
  .badge-card-compacta .temporizador { margin-top: 4px; padding: 4px 8px;
             background: rgba(30,58,138,0.15); border-radius: 6px;
             border: 1px solid rgba(30,58,138,0.3); width: 100%; }
  .badge-card-compacta .temporizador .label-temp { font-size: 0.6rem; color: var(--gris);
             margin-right: 4px; }
  .badge-card-compacta .temporizador .valor-temp { font-size: 0.7rem; font-weight: 700;
             color: var(--texto); font-family: monospace; }
  .tarjetas { display:grid; grid-template-columns:repeat(auto-fill,minmax(110px,1fr));
              gap:8px; margin-top:12px; }
  .tarjeta { background:var(--tarjeta); border-radius:10px; padding:10px;
             text-align:center; }
  .tarjeta .num { font-size:1.6rem; font-weight:700; }
  .tarjeta .etq { font-size:.7rem; color:var(--gris); text-transform:uppercase; }
  .ok { color:var(--verde); } .falta { color:var(--rojo); }
  .panel { background:var(--tarjeta); border-radius:10px; padding:14px; }
  .panel h2 { font-size:.95rem; margin:0 0 10px; color:var(--gris);
              text-transform:uppercase; }
  #log { max-height:420px; overflow-y:auto; font-size:.8rem; }
  .incidente { border-left:3px solid var(--rojo); padding:6px 10px;
               margin-bottom:8px; background:#0f172a; border-radius:6px; }
  .incidente .hora { color:var(--gris); font-size:.7rem; }
  .vacio { color:var(--gris); font-style:italic; }
  .estado-linea { font-size:.75rem; color:var(--gris); margin-top:10px; }
  .punto { display:inline-block; width:9px; height:9px; border-radius:50%;
           background:var(--verde); margin-right:6px; animation:pulso 1.5s infinite; }
  @keyframes pulso { 50%{opacity:.3;} }
  .controles { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; }
  .boton { background:var(--tarjeta); color:var(--texto);
           border:1px solid var(--gris); border-radius:8px; padding:8px 14px;
           cursor:pointer; font-size:.85rem; transition:border-color .15s; }
  .boton:hover { border-color:var(--verde); }
  .boton:disabled { opacity:.5; cursor:wait; }
  .boton.apagado { border-color:var(--rojo); color:var(--rojo); }
  .faltas-badge { font-size:.75rem; color:var(--rojo); align-self:center; }

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
  .alerta-jornada { border-left:4px solid var(--rojo); padding:8px 10px;
            margin-bottom:6px; background:#fef2f2; border-radius:6px; }
  .alerta-jornada .hora { color:var(--rojo); font-size:.7rem; font-weight:700; }
  .alerta-jornada .nombre { font-weight:700; color:var(--texto); }
  .alerta-jornada .detalle { font-size:.75rem; color:var(--gris); margin-top:4px; }
  .btn-forzar { background:var(--rojo); border-color:var(--rojo); color:#fff;
            font-size:.75rem; padding:4px 10px; border-radius:6px; cursor:pointer; }
  .btn-forzar:hover { background:#b91c1c; }

  /* ---------- estados Adentro/Afuera ---------- */
  .estado-adentro { color:var(--verde); font-weight:700; }
  .estado-afuera { color:var(--rojo); font-weight:700; }

  /* ---------- temporizador ---------- */
  .temporizador { margin-top:6px; padding:4px 8px; background:rgba(30,58,138,0.15);
            border-radius:6px; border:1px solid rgba(30,58,138,0.3); }
  .temporizador .label-temp { font-size:.7rem; color:var(--gris); margin-right:6px; }
  .temporizador .valor-temp { font-size:.85rem; font-weight:700; color:var(--texto); font-family:monospace; }
  .badge-card .sub { color:var(--gris); font-size:.8rem; margin-bottom:8px; }
  .badge-card .chip { display:inline-block; padding:4px 10px; border-radius:20px;
                font-size:.8rem; font-weight:700; margin:4px 2px; }
  .chip-activo { background:var(--verde); color:#fff; }
  .chip-bloqueado { background:var(--rojo); color:#fff; }
  .badge-actions { margin-top:10px; display:flex; gap:8px; justify-content:center;
                flex-wrap:wrap; }
  .badge-none { color:var(--gris); font-style:italic; text-align:center;
                padding:30px 10px; flex:1; }
  .resumen-badge { background:rgba(255,255,255,0.03); border-radius:8px;
                padding:10px; margin-top:10px; text-align:left; font-size:.8rem;
                border:1px solid rgba(255,255,255,0.08); }
  .resumen-badge .row { display:flex; justify-content:space-between; margin-bottom:3px; }
  .resumen-badge .label { color:var(--gris); }
  .resumen-badge .valor { font-weight:700; }
</style></head><body>
<h1>👷 SafeSite-Agent — Supervisión en vivo</h1>
<div class="sub" id="sub">conectando con la cámara…</div>
<div class="controles">
  <button id="btn-wa" class="boton" onclick="toggleWA()">⏸️ Pausar WhatsApp</button>
  <button id="btn-alerta" class="boton" onclick="alertaManual()">📨 Enviar alerta ahora</button>
  <span class="faltas-badge" id="faltas-badge"></span>
</div>

<div class="layout">
  <div class="izquierda">
    <img class="video" src="/video" alt="video en vivo">
    <div id="tarjetas-epp" style="display:none;">
      <div class="tarjetas" id="tarjetas"></div>
    </div>
  </div>

  <div class="derecha">
    <!-- ---------- contenedor scrollable de badges (Material Design) ---------- -->
    <div id="badge-contenedor">
      <div class="badge-none" id="badge-none" style="text-align:center; padding:40px 20px; color:var(--gris); font-style:italic;">
        ⏳ Esperando badge QR frente a la cámara…
      </div>
      <div id="badge-cards" style="display:none;">
        <!-- Aquí se insertan las cards de badges detectados dinámicamente -->
      </div>
    </div>

    <!-- ---------- incidentes confirmados (abajo) ---------- -->
    <div class="panel panel-incidentes">
      <h2>🚨 Incidentes confirmados</h2>
      <div id="log"><div class="vacio">sin incidentes todavía…</div></div>
      <div class="estado-linea" id="estado"></div>
    </div>

    <!-- ---------- alertas de jornada sin salida ---------- -->
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

    for (const b of badges) {
      const activo = b.activo === true;
      const chipClass = activo ? 'chip-activo' : 'chip-bloqueado';
      const chipText = activo ? 'ACTIVO' : 'BLOQUEADO';
      const dentro = b.dentro === true;

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
            <div class="row"><span class="label">Horas:</span><span class="valor" id="horas-${b.badge_id}">${b.horas_hoy||0}</span> h</div>
            <div class="row"><span class="label">Valor:</span><span class="valor" id="valor-${b.badge_id}">$${(b.valor_pagar||0).toLocaleString('es-CO')}</span></div>
            <div class="row"><span class="label">Estado:</span><span class="valor estado-${dentro?'adentro':'afuera'}">${estadoTexto}</span></div>
            ${temporizadorHtml}
          </div>`;
      }

      html += `
        <div class="badge-card-compacta">
          <div class="qr-placeholder">QR</div>
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
            const e = document.getElementById(`estado-${b.badge_id}`);
            const t = document.getElementById(`temp-${b.badge_id}`);
            if (h) h.textContent = s.horas_hoy || 0;
            if (v) v.textContent = '$' + (s.valor_pagar || 0).toLocaleString('es-CO');
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
  try {
    const r = await fetch('/badge/marcar/' + encodeURIComponent(badgeId) + '/' + accion, {method:'POST'});
    const e = await r.json();
    if (e.ok) {
      // Refrescar para mostrar el nuevo estado
      setTimeout(() => { refrescarBadge(); }, 800);
    } else {
      console.warn('Error marcando badge:', e.motivo || 'error');
    }
  } catch (err) {
    console.warn('Error de red marcando badge:', err);
  }
}

async function marcarBadge(accion) {
  const b = document.getElementById('badge-id');
  const badgeId = b.textContent;
  if (!badgeId || badgeId === '—') return;
  const btn = event.target;
  btn.disabled = true; btn.textContent = '⏳…';
  try {
    const r = await fetch('/badge/marcar/' + encodeURIComponent(badgeId) + '/' + accion, {method:'POST'});
    const e = await r.json();
    if (e.ok) {
      btn.textContent = accion === 'entrada' ? '✅ Entrada' : '🚪 Salida';
      setTimeout(() => { btn.disabled = false; }, 1500);
      refrescarBadge(); // actualizar estado
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
    const excede = a.excede_jornada_maxima ? ' (EXCEDE JORNADA MÁXIMA)' : '';
    return `
      <div class="alerta-jornada">
        <div class="hora">⚠️ ${a.nombre || 'Desconocido'} (${a.badge_id})${excede}</div>
        <div class="detalle">
          Entró: ${a.hora_entrada ? new Date(a.hora_entrada).toLocaleTimeString('es-CO') : '—'} ·
          Horas dentro: ${a.horas_dentro} h ·
          Turno: ${a.turno || '—'} ·
          Puesto: ${a.puesto || '—'}
        </div>
        ${a.excede_jornada_maxima
          ? `<button class="btn-forzar" onclick="forzarSalida('${a.badge_id}')">Forzar salida y cancelar nómina</button>`
          : '<span style="color:var(--gris); font-size:.7rem;">Aún dentro de la jornada máxima</span>'
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
</script></body></html>"""


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
        # ---------- lector de badges QR (hilo separado para >=30 FPS) ----------
        self.lector_qr = LectorBadgeQR(cooldown_segundos=2.0,
                                       detectar_cada_n_frames=10)
        self.lector_qr.iniciar()  # hilo separado: no bloquea el video
        self.ultima_lectura = None   # LecturaBadge más reciente
        self.badges_activos = {}     # badge_id -> {"datos": dict, "ultima_deteccion": float}
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
            ok, frame = cam.read()
            if not ok:
                time.sleep(0.01)
                continue

            # ---------- lectura de badge QR (hilo separado, no bloquea) ----------
            self.lector_qr.encolar_frame(frame)
            lecturas = self.lector_qr.obtener_lecturas()

            # Solo procesar EPP (YOLO) si hay un badge ACTIVO detectado
            hay_badge_activo = False
            if lecturas:
                lectura = lecturas[0]
                self.ultima_lectura = lectura
                if (lectura.badge and lectura.badge.valido
                        and lectura.badge.estado_badge == "activo"):
                    hay_badge_activo = True

            if hay_badge_activo:
                incidentes, filtradas = self.agente.procesar_frame(
                    frame, zona=self.zona, t_stamp=time.time())
                anotado = self.agente.percepcion.anotar(frame, filtradas)
                self._conteos = self._contar(filtradas)
                self._faltas = [d for d in filtradas
                                if d.cls_id in config.CLASES_INCUMPLIMIENTO]
            else:
                incidentes = []
                filtradas = []
                anotado = frame.copy()
                self._conteos = {}
                self._faltas = []

            # ---------- recuadro del QR (siempre visible al detectar) ----------
            if lecturas:
                lectura = lecturas[0]
                if lectura.caja:
                    x1, y1, x2, y2 = [int(v) for v in lectura.caja]
                    es_valido = (lectura.badge is not None
                                 and lectura.badge.valido)
                    color = (0, 200, 0) if es_valido else (0, 0, 200)
                    cv2.rectangle(anotado, (x1, y1), (x2, y2), color, 3)
                    etiqueta = "QR VALIDO" if es_valido else "QR"
                    cv2.putText(anotado, etiqueta, (x1, max(y1 - 10, 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            ahora_ts = time.time()

            with self.lock:
                self.ultimo_frame = anotado

                # ---------- gestionar múltiples badges activos (sin expiración por tiempo) ----------
                # Las cards se mantienen visibles hasta que el trabajador marque salida.
                if lecturas:
                    for lectura in lecturas:
                        if not lectura.badge:
                            continue
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
        }

    # ---------- endpoints de badges v2 ----------
    def badge_estado(self):
        """Devuelve solo badges detectados recientemente (cards dinámicas).
        Aparecen al escanear QR, desaparecen al marcar salida."""
        badges_lista = []
        for bid, d in self.badges_activos.items():
            datos = d["datos"].copy()
            ahora_ts = time.time()
            datos["detectado_recientemente"] = (ahora_ts - d["ultima_deteccion"]) < 8.0
            datos["tiempo_deteccion"] = d["ultima_deteccion"]
            badges_lista.append(datos)
        return badges_lista

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
