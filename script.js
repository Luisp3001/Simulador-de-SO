/* ═══════════════════════════════════════════════════════════════════
   AETHELRED OS — Frontend Client
   Conectado al backend Python (Flask) via REST API.
   ═══════════════════════════════════════════════════════════════════ */

'use strict';

const API = 'http://localhost:5000/api';

// ─── ESTADO LOCAL (solo UI) ────────────────────────────────────────────
let logOffset      = 0;   // Último índice de log conocido del servidor
let pollTimer      = null;
let bubbleTimer    = null;
let uptimeTimer    = null;
let uptimeSeconds  = 0;
let isRunning      = false;
let memLevelHigh   = false;

// ─── DOM REFS ─────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const dom = {
    time:          $('system-time'),
    kernelDot:     $('kernel-dot'),
    kernelText:    $('kernel-status-text'),

    cpuNeedle:     $('cpu-needle'),
    cpuUsage:      $('cpu-usage-text'),
    cpuStatus:     $('cpu-status'),
    cpuProcess:    $('cpu-process'),
    cpuCycles:     $('cpu-cycles'),

    processList:   $('process-list'),
    processEmpty:  $('process-empty'),

    memGrid:       $('memory-grid'),
    memTotal:      $('mem-total'),
    memAvail:      $('mem-available'),
    memUsage:      $('mem-usage'),
    memLiquidFill: $('mem-liquid-fill'),
    memLiquidPct:  $('mem-liquid-pct'),
    memLiquid:     $('mem-liquid'),

    logOutput:     $('log-output'),

    btnStart:      $('btn-start'),
    btnStop:       $('btn-stop'),
    btnRestart:    $('btn-restart'),
    btnTick:       $('btn-tick'),
    btnNewProc:    $('btn-new-process'),

    modal:         $('modal-process'),
    inputName:     $('input-process-name'),
    inputMem:      $('input-process-mem'),
    inputPrio:     $('input-process-priority'),
    btnModalOk:    $('btn-modal-confirm'),
    btnModalCx:    $('btn-modal-cancel'),
};

// ─── HELPERS DE FETCH ─────────────────────────────────────────────────
async function apiPost(endpoint, body = null) {
    const opts = { method: 'POST', headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    try {
        const res = await fetch(`${API}${endpoint}`, opts);
        return await res.json();
    } catch (e) {
        appendLog(e.message, 'err');
        return { ok: false, msg: e.message };
    }
}

async function apiDelete(endpoint) {
    try {
        const res = await fetch(`${API}${endpoint}`, { method: 'DELETE' });
        return await res.json();
    } catch (e) {
        appendLog(e.message, 'err');
        return { ok: false, msg: e.message };
    }
}

async function apiGet(endpoint) {
    try {
        const res = await fetch(`${API}${endpoint}`);
        return await res.json();
    } catch (e) {
        return { ok: false, msg: e.message };
    }
}

// ─── LOG ──────────────────────────────────────────────────────────────
function formatTime(secs) {
    const h = String(Math.floor(secs / 3600)).padStart(2, '0');
    const m = String(Math.floor((secs % 3600) / 60)).padStart(2, '0');
    const s = String(secs % 60).padStart(2, '0');
    return `${h}:${m}:${s}`;
}

function appendLog(msg, level = '', time = null) {
    const timeStr = time || dom.time.textContent;
    const entry = document.createElement('div');
    entry.className = `log-entry${level ? ' log-' + level.toLowerCase() : ''}`;
    entry.innerHTML = `<span class="log-time">[${timeStr}]</span><span class="log-msg">${msg}</span>`;
    dom.logOutput.appendChild(entry);
    dom.logOutput.scrollTop = dom.logOutput.scrollHeight;
    while (dom.logOutput.children.length > 120) {
        dom.logOutput.removeChild(dom.logOutput.firstChild);
    }
}

function processLogEntries(entries) {
    entries.forEach(e => appendLog(e.msg, e.level, e.time));
}

// Mapa nivel servidor → clase CSS
const LEVEL_MAP = { 'OK': 'ok', 'WARN': 'warn', 'ERR': 'err', 'SYS': 'sys', 'INFO': '' };

// ─── CPU GAUGE ────────────────────────────────────────────────────────
function updateCpuGauge(pct) {
    pct = Math.max(0, Math.min(100, pct));
    const angle = -135 + (pct / 100) * 270;
    dom.cpuNeedle.setAttribute('transform', `rotate(${angle}, 100, 100)`);
    dom.cpuUsage.textContent = `${Math.round(pct)}%`;
}

// ─── MEMORIA ──────────────────────────────────────────────────────────
const MEMORY_BLOCKS = 64;

function buildMemoryGrid() {
    dom.memGrid.innerHTML = '';
    for (let i = 0; i < MEMORY_BLOCKS; i++) {
        const block = document.createElement('div');
        block.className = 'mem-block';
        block.id = `mb-${i}`;
        dom.memGrid.appendChild(block);
    }
}

function updateMemory(memData) {
    const { total_mb, usada_mb, disponible_mb, uso_pct } = memData;
    const usedBlocks   = Math.round((usada_mb / total_mb) * MEMORY_BLOCKS);
    const highThreshold = MEMORY_BLOCKS * 0.8;

    for (let i = 0; i < MEMORY_BLOCKS; i++) {
        const block = $(`mb-${i}`);
        if (!block) continue;
        if (i < usedBlocks) {
            block.classList.add('used');
            block.classList.toggle('high', i >= highThreshold);
        } else {
            block.classList.remove('used', 'high');
        }
    }

    dom.memTotal.textContent = `${total_mb} MB`;
    dom.memAvail.textContent = `${disponible_mb} MB`;
    dom.memUsage.textContent = `${Math.round(uso_pct)}%`;

    dom.memLiquidFill.style.setProperty('--pb-liquid-level', `${uso_pct}%`);
    dom.memLiquidPct.textContent = `${Math.round(uso_pct)}%`;
    dom.memLiquid.setAttribute('aria-valuenow', Math.round(uso_pct));

    const high = uso_pct >= 80;
    dom.memLiquid.dataset.level = high ? 'high' : 'normal';
    memLevelHigh = high;
}

// ─── PROCESOS ─────────────────────────────────────────────────────────
const PRIORITY_CLASS = { ALTA: 'priority-alta', MEDIA: 'priority-media', BAJA: 'priority-baja' };
const STATE_LABEL    = { EJECUTANDO: 'Ejec.', LISTO: 'Listo', BLOQUEADO: 'Bloq.', NUEVO: 'Nuevo' };
const STATE_CSS      = { EJECUTANDO: 'running', LISTO: 'waiting', BLOQUEADO: 'waiting' };

function renderProcessList(procesos) {
    // ── Caso vacío ────────────────────────────────────────────────────
    if (!procesos || procesos.length === 0) {
        dom.processList.querySelectorAll('.process-item').forEach(el => el.remove());
        dom.processEmpty.style.display = 'flex';
        return;
    }
    dom.processEmpty.style.display = 'none';

    // ── Índice de lo que ya existe en el DOM ─────────────────────────
    const existentes = new Map();
    dom.processList.querySelectorAll('.process-item').forEach(el => {
        existentes.set(parseInt(el.dataset.pid, 10), el);
    });

    // ── PIDs que llegan del servidor ──────────────────────────────────
    const nuevoPids = new Set(procesos.map(p => p.pid));

    // 1. Eliminar los que ya no existen
    existentes.forEach((el, pid) => {
        if (!nuevoPids.has(pid)) el.remove();
    });

    // 2. Reconstruir el orden de referencia DESPUÉS de las eliminaciones
    //    para saber si un elemento ya está en la posición correcta.
    const getOrdenActual = () =>
        [...dom.processList.querySelectorAll('.process-item')]
            .map(el => parseInt(el.dataset.pid, 10));

    // 3. Añadir nuevos / actualizar existentes
    procesos.forEach((proc) => {
        const stateCss   = STATE_CSS[proc.estado]   || 'waiting';
        const stateLabel = STATE_LABEL[proc.estado]  || proc.estado;

        if (existentes.has(proc.pid)) {
            // ── Ya existe: parchar solo si el texto del estado cambió ──
            const el   = existentes.get(proc.pid);
            const chip = el.querySelector('.proc-state');
            if (chip && chip.textContent !== stateLabel) {
                chip.textContent = stateLabel;
                chip.className   = `proc-state ${stateCss}`;
            }
            // Solo mover en el DOM si la posición cambió realmente
            if (el.nextSibling !== dom.processEmpty) {
                dom.processList.insertBefore(el, dom.processEmpty);
            }
        } else {
            // ── Nuevo proceso: crear, animar UNA sola vez, insertar ────
            const el = document.createElement('div');
            el.className   = `process-item process-item--new ${PRIORITY_CLASS[proc.prioridad] || 'priority-media'}`;
            el.dataset.pid = proc.pid;
            el.innerHTML = `
                <span class="proc-id">PID ${proc.pid}</span>
                <span class="proc-name">${proc.nombre}</span>
                <span class="proc-mem">${proc.memoria}MB</span>
                <span class="proc-state ${stateCss}">${stateLabel}</span>
                <button class="proc-kill" title="Terminar proceso" data-pid="${proc.pid}">✕</button>
            `;
            dom.processList.insertBefore(el, dom.processEmpty);
            // Quitar la clase de animación cuando termine para no re-dispararla
            el.addEventListener('animationend', () => el.classList.remove('process-item--new'), { once: true });
        }
    });
}

// ─── POLLING: actualizar UI desde servidor ────────────────────────────
async function pollState() {
    const data = await apiGet(`/state?log_offset=${logOffset}`);
    if (!data.ok) return;

    // Log incremental
    if (data.log_nuevas && data.log_nuevas.length > 0) {
        data.log_nuevas.forEach(e => appendLog(e.msg, LEVEL_MAP[e.level] ?? '', e.time));
        logOffset = data.log_offset;
    }

    // CPU
    const cpu = data.cpu;
    updateCpuGauge(cpu.uso_porcentaje);
    dom.cpuCycles.textContent = data.ciclo;

    if (!cpu.libre) {
        dom.cpuProcess.textContent = cpu.proceso_actual || '—';
        dom.cpuStatus.textContent  = 'Ocupado';
        dom.cpuStatus.className    = 'stat-val status-chip busy';
    } else {
        dom.cpuProcess.textContent = 'Ninguno';
        dom.cpuStatus.textContent  = 'Libre';
        dom.cpuStatus.className    = 'stat-val status-chip idle';
    }

    // Memoria
    updateMemory(data.memoria);

    // Procesos
    renderProcessList(data.procesos);
}

// ─── BUBBLES ──────────────────────────────────────────────────────────
function spawnBubble() {
    if (!isRunning || !memLevelHigh) return;
    const bubble = document.createElement('div');
    bubble.className = 'pb-bubble';
    const size     = 3 + Math.random() * 8;
    const left     = 5 + Math.random() * 90;
    const duration = 0.8 + Math.random() * 1.5;
    bubble.style.width             = `${size}px`;
    bubble.style.height            = `${size}px`;
    bubble.style.left              = `${left}%`;
    bubble.style.animationDuration = `${duration}s`;
    dom.memLiquidFill.appendChild(bubble);
    setTimeout(() => { if (bubble.parentNode) bubble.remove(); }, duration * 1000);
}

// ─── CONTROLES ────────────────────────────────────────────────────────
function setRunningUI(running) {
    isRunning = running;
    dom.btnStart.disabled   = running;
    dom.btnStop.disabled    = !running;
    dom.btnRestart.disabled = !running;
    dom.kernelDot.classList.toggle('stopped', !running);
    dom.kernelText.textContent = running ? 'Ejecutando' : 'Detenido';

    if (running) {
        pollTimer   = setInterval(pollState, 1000);
        bubbleTimer = setInterval(spawnBubble, 150);
        uptimeTimer = setInterval(() => {
            uptimeSeconds++;
            dom.time.textContent = formatTime(uptimeSeconds);
        }, 1000);
    } else {
        clearInterval(pollTimer);
        clearInterval(bubbleTimer);
        clearInterval(uptimeTimer);
        uptimeSeconds = 0;
        dom.time.textContent = '00:00:00';
        updateCpuGauge(0);
        dom.cpuProcess.textContent = 'Ninguno';
        dom.cpuStatus.textContent  = 'Libre';
        dom.cpuStatus.className    = 'stat-val status-chip idle';
    }
}

async function handleStart() {
    const res = await apiPost('/start');
    if (!res.ok) { appendLog(res.msg, 'err'); return; }
    logOffset = 0;
    setRunningUI(true);
    await pollState();   // carga inicial inmediata
}

async function handleStop() {
    const res = await apiPost('/stop');
    if (!res.ok) { appendLog(res.msg, 'err'); return; }
    setRunningUI(false);
    appendLog('Sistema detenido.', 'warn');
    renderProcessList([]);
}

async function handleRestart() {
    appendLog('Reiniciando sistema…', 'warn');
    setRunningUI(false);
    const res = await apiPost('/restart');
    if (!res.ok) { appendLog(res.msg, 'err'); return; }
    logOffset = 0;
    uptimeSeconds = 0;
    dom.time.textContent = '00:00:00';
    setRunningUI(true);
    await pollState();
}

async function handleTick() {
    if (!isRunning) { appendLog('Sistema inactivo — inicia el SO primero.', 'warn'); return; }
    const res = await apiPost('/tick');
    if (!res.ok) appendLog(res.msg, 'err');
    await pollState();
}

// ─── MODAL NUEVO PROCESO ──────────────────────────────────────────────
function openModal() {
    dom.inputName.value = '';
    dom.inputMem.value  = '128';
    dom.inputPrio.value = 'media';
    dom.modal.classList.add('active');
    dom.inputName.focus();
}

function closeModal() {
    dom.modal.classList.remove('active');
}

async function confirmNewProcess() {
    const nombre    = dom.inputName.value.trim() || `proceso_${Date.now()}`;
    const memoria   = parseInt(dom.inputMem.value, 10) || 128;
    const prioridad = dom.inputPrio.value;

    if (memoria < 1 || memoria > 4096) { alert('Memoria fuera de rango (1–4096 MB)'); return; }

    const res = await apiPost('/process', { nombre, memoria_mb: memoria, prioridad });
    if (!res.ok) { appendLog(res.msg, 'err'); }
    closeModal();
    await pollState();
}

async function killProcess(pid) {
    const res = await apiDelete(`/process/${pid}`);
    if (!res.ok) appendLog(res.msg, 'err');
    await pollState();
}

// ─── EVENT LISTENERS ──────────────────────────────────────────────────
dom.btnStart.addEventListener('click',   handleStart);
dom.btnStop.addEventListener('click',    handleStop);
dom.btnRestart.addEventListener('click', handleRestart);
dom.btnTick.addEventListener('click',    handleTick);
dom.btnNewProc.addEventListener('click', openModal);
dom.btnModalOk.addEventListener('click', confirmNewProcess);
dom.btnModalCx.addEventListener('click', closeModal);
dom.modal.addEventListener('click', e => { if (e.target === dom.modal) closeModal(); });
dom.processList.addEventListener('click', e => {
    const btn = e.target.closest('.proc-kill');
    if (btn) killProcess(parseInt(btn.dataset.pid, 10));
});
dom.inputName.addEventListener('keydown', e => { if (e.key === 'Enter') confirmNewProcess(); });
dom.inputMem.addEventListener('keydown',  e => { if (e.key === 'Enter') confirmNewProcess(); });

// ─── INIT ─────────────────────────────────────────────────────────────
(async function init() {
    dom.time.textContent = '00:00:00';
    buildMemoryGrid();
    updateCpuGauge(0);
    renderProcessList([]);

    // Sincronizar con el estado real del servidor al cargar la página.
    // Si el kernel ya estaba corriendo (ej. recarga del navegador sin
    // reiniciar el servidor), retomar el polling sin llamar a /start de nuevo.
    try {
        const data = await apiGet('/state?log_offset=0');
        if (data.ok && data.activo) {
            appendLog('Servidor activo detectado — reanudando sesión.', 'sys');
            logOffset = data.log_offset;   // no repetir el log histórico
            setRunningUI(true);
            await pollState();
        } else {
            appendLog('Interfaz lista — Presiona "Iniciar SO" para arrancar el Kernel.', 'sys');
        }
    } catch {
        appendLog('No se pudo conectar al servidor. ¿Está corriendo server.py?', 'err');
    }
})();

