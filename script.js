/* ═══════════════════════════════════════════════════════════════════
   HEPHAESTUS CORE — Frontend Client
   Conectado al backend Python (Flask) via REST API.
   ═══════════════════════════════════════════════════════════════════ */

'use strict';

const API = 'http://localhost:5000/api';

// ─── ESTADO LOCAL (solo UI) ────────────────────────────────────────────
let logOffset      = 0;
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
    memGridLabel:  $('memory-grid-label'),
    memRequested:  $('mem-requested'),
    memReserved:   $('mem-reserved'),
    memInternal:   $('mem-internal-frag'),
    memExternal:   $('mem-external-frag'),
    memLargest:    $('mem-largest-hole'),
    memoryStrategySelect: $('memory-strategy-select'),
    btnApplyMemory: $('btn-apply-memory'),

    logOutput:     $('log-output'),

    btnStart:      $('btn-start'),
    btnStop:       $('btn-stop'),
    btnRestart:    $('btn-restart'),
    btnTick:       $('btn-tick'),
    btnNewProc:    $('btn-new-process'),

    // Scheduler controls
    schedulerSelect:      $('scheduler-select'),
    quantumControl:       $('quantum-control'),
    quantumInput:         $('quantum-input'),
    btnApplyScheduler:    $('btn-apply-scheduler'),

    // Modal
    modal:         $('modal-process'),
    inputName:     $('input-process-name'),
    inputMem:      $('input-process-mem'),
    inputBurst:    $('input-process-burst'),
    inputNice:     $('input-process-nice'),
    btnModalOk:    $('btn-modal-confirm'),
    btnModalCx:    $('btn-modal-cancel'),

    // Metrics panel
    metricsSchedulerName: $('metrics-scheduler-name'),
    metricsAverages:      $('metrics-averages'),
    avgWaiting:           $('avg-waiting'),
    avgTurnaround:        $('avg-turnaround'),
    metricsTbody:         $('metrics-tbody'),
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
    const circle = $('cpu-ring-fill');
    if (circle) {
        const circumference = 389.56; // 2 * PI * 62
        const offset = circumference - (pct / 100) * circumference;
        circle.style.strokeDashoffset = offset;
    }
    if (dom.cpuUsage) dom.cpuUsage.textContent = `${Math.round(pct)}%`;
}

// ─── MEMORIA ──────────────────────────────────────────────────────────
function memoryColor(pid) {
    const hue = (Number(pid) * 67 + 185) % 360;
    return `hsl(${hue} 72% 48%)`;
}

function renderMemoryBlocks(memData) {
    const bloques = memData.bloques || [];
    dom.memGrid.innerHTML = '';
    dom.memGrid.classList.toggle('memory-grid--cells', memData.tipo_vista === 'celdas');
    dom.memGrid.classList.toggle('memory-grid--segments', memData.tipo_vista !== 'celdas');

    bloques.forEach((item) => {
        const block = document.createElement('div');
        block.className = `mem-block ${item.libre ? 'free' : 'used'}`;
        if (memData.tipo_vista !== 'celdas') {
            block.style.flexGrow = String(item.tamaño);
        }
        if (!item.libre) {
            block.style.backgroundColor = memoryColor(item.pid);
            block.style.borderColor = memoryColor(item.pid);
        }
        const dueño = item.libre ? 'Libre' : `PID ${item.pid}`;
        block.title = `${dueño} · ${item.inicio}–${item.inicio + item.tamaño} MB · ${item.tamaño} MB`;
        if (memData.tipo_vista !== 'celdas' && item.tamaño >= 256) {
            block.textContent = item.libre ? `${item.tamaño} MB` : `PID ${item.pid} · ${item.tamaño} MB`;
        }
        dom.memGrid.appendChild(block);
    });
}

function updateMemory(memData) {
    const { total_mb, usada_mb, disponible_mb, uso_pct } = memData;
    renderMemoryBlocks(memData);

    dom.memTotal.textContent = `${total_mb} MB`;
    dom.memAvail.textContent = `${disponible_mb} MB`;
    dom.memUsage.textContent = `${Math.round(uso_pct)}%`;
    dom.memRequested.textContent = `${memData.solicitada_mb} MB`;
    dom.memReserved.textContent = `${memData.reservada_mb} MB`;
    dom.memInternal.textContent = `${memData.fragmentacion_interna_mb} MB`;
    dom.memExternal.textContent = `${memData.fragmentacion_externa_mb} MB`;
    dom.memLargest.textContent = `${memData.mayor_hueco_libre_mb} MB`;
    dom.memGridLabel.textContent = `${memData.algoritmo_nombre} · mapa físico:`;
    dom.memoryStrategySelect.value = memData.algoritmo;

    dom.memLiquidFill.style.width = `${uso_pct}%`;
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

// Colores por nivel de cola
const QUEUE_LEVEL_COLOR = ['#c8a84b', '#b06a2f', '#666'];

function renderProcessList(procesos) {
    if (!procesos || procesos.length === 0) {
        dom.processList.querySelectorAll('.process-item').forEach(el => el.remove());
        dom.processEmpty.style.display = 'flex';
        return;
    }
    dom.processEmpty.style.display = 'none';

    const existentes = new Map();
    dom.processList.querySelectorAll('.process-item').forEach(el => {
        existentes.set(parseInt(el.dataset.pid, 10), el);
    });

    const nuevoPids = new Set(procesos.map(p => p.pid));

    existentes.forEach((el, pid) => {
        if (!nuevoPids.has(pid)) el.remove();
    });

    procesos.forEach((proc) => {
        const stateCss   = STATE_CSS[proc.estado]   || 'waiting';
        const stateLabel = STATE_LABEL[proc.estado]  || proc.estado;
        const niceStr    = proc.nice_value !== undefined ? `nice=${proc.nice_value}` : '';
        const remStr     = proc.remaining_time !== undefined ? `⏱${proc.remaining_time}` : '';

        if (existentes.has(proc.pid)) {
            const el   = existentes.get(proc.pid);
            const chip = el.querySelector('.proc-state');
            if (chip && chip.textContent !== stateLabel) {
                chip.textContent = stateLabel;
                chip.className   = `proc-state ${stateCss}`;
            }
            // Actualizar remaining time
            const remEl = el.querySelector('.proc-rem');
            if (remEl) remEl.textContent = remStr;

            if (el.nextSibling !== dom.processEmpty) {
                dom.processList.insertBefore(el, dom.processEmpty);
            }
        } else {
            const el = document.createElement('div');
            const niceClass = (proc.nice_value < 0) ? 'priority-alta' : (proc.nice_value > 0 ? 'priority-baja' : 'priority-media');
            el.className   = `process-item process-item--new ${niceClass}`;
            el.dataset.pid = proc.pid;
            el.innerHTML = `
                <span class="proc-id">PID ${proc.pid}</span>
                <span class="proc-name">${proc.nombre}</span>
                <span class="proc-mem">${proc.memoria}MB</span>
                <span class="proc-rem" title="Ciclos restantes">${remStr}</span>
                <span class="proc-nice" title="Nice value">${niceStr}</span>
                <span class="proc-state ${stateCss}">${stateLabel}</span>
                <button class="proc-kill" title="Terminar proceso" data-pid="${proc.pid}">✕</button>
            `;
            dom.processList.insertBefore(el, dom.processEmpty);
            el.addEventListener('animationend', () => el.classList.remove('process-item--new'), { once: true });
        }
    });
}

// ─── MÉTRICAS DE PROCESOS TERMINADOS ─────────────────────────────────
function updateMetrics(terminados, schedulerName) {
    // Nombre del scheduler
    if (dom.metricsSchedulerName) {
        dom.metricsSchedulerName.textContent = schedulerName || '—';
    }

    if (!terminados || terminados.length === 0) {
        if (dom.metricsAverages) dom.metricsAverages.style.display = 'none';
        if (dom.metricsTbody) {
            dom.metricsTbody.innerHTML = '<tr><td colspan="8" class="metrics-empty">Sin procesos terminados</td></tr>';
        }
        return;
    }

    // Calcular promedios
    const avgWait = terminados.reduce((s, p) => s + (p.waiting_time || 0), 0) / terminados.length;
    const avgTAT  = terminados.reduce((s, p) => s + (p.turnaround_time || 0), 0) / terminados.length;

    if (dom.metricsAverages) dom.metricsAverages.style.display = 'flex';
    if (dom.avgWaiting)    dom.avgWaiting.textContent    = avgWait.toFixed(2) + ' ciclos';
    if (dom.avgTurnaround) dom.avgTurnaround.textContent = avgTAT.toFixed(2) + ' ciclos';

    // Tabla de procesos terminados
    if (dom.metricsTbody) {
        dom.metricsTbody.innerHTML = terminados.map(p => `
            <tr>
                <td>${p.pid}</td>
                <td>${p.nombre}</td>
                <td>${p.burst_time}</td>
                <td>${p.arrival_time}</td>
                <td>${p.start_time >= 0 ? p.start_time : '—'}</td>
                <td>${p.completion_time}</td>
                <td class="metric-waiting">${p.waiting_time}</td>
                <td class="metric-tat">${p.turnaround_time}</td>
            </tr>
        `).join('');
    }
}

// ─── SCHEDULER ────────────────────────────────────────────────────────
const SCHEDULERS_WITH_QUANTUM = ['round_robin', 'dos_niveles'];

function onSchedulerChange() {
    const tipo = dom.schedulerSelect ? dom.schedulerSelect.value : 'fcfs';
    if (dom.quantumControl) {
        dom.quantumControl.style.display =
            SCHEDULERS_WITH_QUANTUM.includes(tipo) ? 'flex' : 'none';
    }
}

async function applyScheduler() {
    const tipo = dom.schedulerSelect ? dom.schedulerSelect.value : 'fcfs';
    const body = { tipo };
    if (SCHEDULERS_WITH_QUANTUM.includes(tipo) && dom.quantumInput) {
        body.quantum = parseInt(dom.quantumInput.value, 10) || 2;
    }
    const res = await apiPost('/scheduler', body);
    if (!res.ok) {
        appendLog(res.msg, 'err');
    } else {
        appendLog(`Planificador → ${res.scheduler}`, 'ok');
        await pollState();
    }
}

async function applyMemoryStrategy() {
    const tipo = dom.memoryStrategySelect.value;
    const res = await apiPost('/memory/strategy', { tipo });
    if (!res.ok) {
        appendLog(res.msg, 'err');
        await pollState();
        return;
    }
    appendLog(`Memoria → ${res.nombre}`, 'ok');
    await pollState();
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
    dom.btnApplyMemory.disabled = data.procesos.length > 0;
    dom.btnApplyMemory.title = data.procesos.length > 0
        ? 'Finaliza todos los procesos antes de cambiar el algoritmo'
        : 'Aplicar algoritmo de memoria';

    // Métricas
    updateMetrics(data.procesos_terminados, data.scheduler);
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
    await pollState();
}

async function handleStop() {
    const res = await apiPost('/stop');
    if (!res.ok) { appendLog(res.msg, 'err'); return; }
    setRunningUI(false);
    appendLog('Sistema detenido.', 'warn');
    await pollState();
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
    if (dom.inputName)  dom.inputName.value  = '';
    if (dom.inputMem)   dom.inputMem.value   = '128';
    if (dom.inputBurst) dom.inputBurst.value = '5';
    if (dom.inputNice)  dom.inputNice.value  = '0';
    dom.modal.classList.add('active');
    if (dom.inputName) dom.inputName.focus();
}

function closeModal() {
    dom.modal.classList.remove('active');
}

async function confirmNewProcess() {
    const nombre    = dom.inputName ? dom.inputName.value.trim() : '';
    const memoria   = parseInt(dom.inputMem ? dom.inputMem.value : '128', 10) || 128;
    const burst     = parseInt(dom.inputBurst ? dom.inputBurst.value : '5', 10) || 5;
    const nice      = parseInt(dom.inputNice ? dom.inputNice.value : '0', 10) || 0;
    const finalNombre = nombre || `proceso_${Date.now()}`;

    if (memoria < 1 || memoria > 4096) { alert('Memoria fuera de rango (1–4096 MB)'); return; }
    if (burst   < 1 || burst   > 100)  { alert('Ráfaga fuera de rango (1–100 ciclos)'); return; }

    const res = await apiPost('/process', {
        nombre:     finalNombre,
        memoria_mb: memoria,
        burst_time: burst,
        nice_value: nice,
    });
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
const btnModalCancelAlt = $('btn-modal-cancel-btn');
if (btnModalCancelAlt) btnModalCancelAlt.addEventListener('click', closeModal);
dom.modal.addEventListener('click', e => { if (e.target === dom.modal) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && dom.modal.classList.contains('active')) closeModal(); });
dom.processList.addEventListener('click', e => {
    const btn = e.target.closest('.proc-kill');
    if (btn) killProcess(parseInt(btn.dataset.pid, 10));
});
dom.inputName.addEventListener('keydown', e => { if (e.key === 'Enter') confirmNewProcess(); });
dom.inputMem.addEventListener('keydown',  e => { if (e.key === 'Enter') confirmNewProcess(); });

if (dom.schedulerSelect) {
    dom.schedulerSelect.addEventListener('change', onSchedulerChange);
}
if (dom.btnApplyScheduler) {
    dom.btnApplyScheduler.addEventListener('click', applyScheduler);
}
if (dom.btnApplyMemory) {
    dom.btnApplyMemory.addEventListener('click', applyMemoryStrategy);
}

// ─── INIT ─────────────────────────────────────────────────────────────
(async function init() {
    dom.time.textContent = '00:00:00';
    updateCpuGauge(0);
    renderProcessList([]);
    onSchedulerChange(); // sincronizar visibilidad del campo quantum

    try {
        const data = await apiGet('/state?log_offset=0');
        if (data.ok) {
            logOffset = data.log_offset;
            updateMemory(data.memoria);
            renderProcessList(data.procesos);
            updateMetrics(data.procesos_terminados, data.scheduler);
            dom.btnApplyMemory.disabled = data.procesos.length > 0;
            if (data.activo) {
                appendLog('Servidor activo detectado — reanudando sesión.', 'sys');
                setRunningUI(true);
                await pollState();
            } else {
                appendLog('Interfaz lista — Presiona "Iniciar SO" para arrancar el Kernel.', 'sys');
            }
        } else {
            appendLog('No se pudo consultar el estado del servidor.', 'err');
        }
    } catch {
        appendLog('No se pudo conectar al servidor. ¿Está corriendo server.py?', 'err');
    }
})();
