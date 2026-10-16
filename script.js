/* ═══════════════════════════════════════════════════════════════════
   BALJ OS — Frontend Client
   Conectado al backend Python (Flask) via REST API.
   ═══════════════════════════════════════════════════════════════════ */

'use strict';

const API = 'http://localhost:5000/api';

// ─── ESTADO LOCAL (solo UI) ────────────────────────────────────────────
let logOffset      = 0;
let pollTimer      = null;
let uptimeTimer    = null;
let uptimeSeconds  = 0;
let isRunning      = false;

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

    ramSummary:    $('ram-summary'),

    // Módulo de memoria (independiente)
    tabProcesses:  $('tab-processes'),
    tabMemory:     $('tab-memory'),
    viewProcesses: $('view-processes'),
    viewMemory:    $('view-memory'),
    tabIo:         $('tab-io'),
    viewIo:        $('view-io'),
    unitInput:     $('unit-input'),
    unitStatus:    $('unit-status'),
    btnSetUnit:    $('btn-set-unit'),
    btnResetMem:   $('btn-reset-memory'),
    ramFixed:      $('ram-fixed'),
    gridFormula:   $('grid-formula'),
    procFormula:   $('proc-formula'),
    memMessage:    $('mem-message'),
    memSetup:      $('mem-setup'),
    memProcTable:  $('mem-proc-table'),
    memWorkspace:  $('mem-workspace'),
    memLockedNote: $('mem-locked-note'),
    memGrid:       $('memory-grid'),
    memGridLabel:  $('memory-grid-label'),
    memLegend:     $('memory-legend'),
    memUsage:      $('mem-usage'),
    memTotal:      $('mem-total'),
    memAvail:      $('mem-available'),
    memRequested:  $('mem-requested'),
    memReserved:   $('mem-reserved'),
    memInternal:   $('mem-internal-frag'),
    memExternal:   $('mem-external-frag'),
    memLargest:    $('mem-largest-hole'),
    algoNav:       $('algo-nav'),
    secAlloc:      $('sec-alloc'),
    secPaging:     $('sec-paging'),
    fitNav:        $('fit-nav'),
    algoDesc:      $('algo-desc'),
    memSectionTitle: $('mem-section-title'),
    thPos:         $('th-pos'),

    // Reemplazo de páginas
    pgNav:         $('pg-nav'),
    pgDesc:        $('pg-desc'),
    pgRefs:        $('pg-refs'),
    pgFrames:      $('pg-frames'),
    pgInterval:    $('pg-interval'),
    pgNruBox:      $('pg-nru-box'),
    pgRun:         $('btn-pg-run'),
    pgMessage:     $('pg-message'),
    pgResult:      $('pg-result'),
    pgBadge:       $('pg-badge'),
    pgPrev:        $('pg-prev'),
    pgNext:        $('pg-next'),
    pgPlay:        $('pg-play'),
    pgAll:         $('pg-all'),
    pgSlider:      $('pg-slider'),
    pgStepLabel:   $('pg-step-label'),
    pgTable:       $('pg-table'),
    pgDetail:      $('pg-detail'),
    pgTotal:       $('pg-total'),
    pgFaults:      $('pg-faults'),
    pgHits:        $('pg-hits'),
    pgCompare:     $('pg-compare'),
    memProcName:   $('mem-proc-name'),
    memProcSize:   $('mem-proc-size'),
    btnMemAlloc:   $('btn-mem-alloc'),
    memProcTbody:  $('mem-proc-tbody'),

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

// ─── RESUMEN DE RAM (modo procesos) ────────────────────────────────────
function updateRamSummary(memData) {
    if (!memData || !dom.ramSummary) return;
    dom.ramSummary.textContent = `${memData.usada_mb} / ${memData.total_mb} MB`;
}

// ─── MÓDULO DE MEMORIA INDEPENDIENTE ───────────────────────────────────
let memLab = null;   // último estado recibido de /api/memlab

function memoryColor(pid) {          // solo para Lista enlazada / Buddy
    const hue = (Number(pid) * 67 + 185) % 360;
    return `hsl(${hue} 72% 48%)`;
}

function showMemMessage(msg, kind = 'info') {
    dom.memMessage.textContent = msg || '';
    dom.memMessage.dataset.kind = kind;
}

function setMode(mode) {
    const mem = mode === 'memory';
    const io  = mode === 'io';
    document.body.classList.toggle('mode-memory', mem || io);   // oculta CPU/planificador fuera de su módulo
    dom.viewProcesses.hidden = mem || io;
    dom.viewMemory.hidden = !mem;
    dom.viewIo.hidden = !io;
    dom.tabProcesses.classList.toggle('active', !mem && !io);
    dom.tabMemory.classList.toggle('active', mem);
    dom.tabIo.classList.toggle('active', io);
    if (mem) loadMemLab();
    if (window.UsbUI) window.UsbUI.activar(io);
}

async function loadMemLab() {
    const data = await apiGet('/memlab');
    if (data.ok) {
        if (secActual !== 'paginas') secActual = seccionDe(data.activo);
        renderMemLab(data);
        updateSectionUI();
    } else showMemMessage('No se pudo consultar el módulo de memoria. ¿Está corriendo server.py?', 'err');
}

// Mapa de bits: solo 0 y 1, sin colores por proceso.
function renderBitmap(mem, procesos) {
    const nombres = new Map(procesos.map(p => [p.pid, p.nombre]));
    const n = mem.mapa_bits.length;
    dom.memGrid.className = 'memory-grid memory-grid--bits';
    dom.memGrid.dataset.size = n <= 64 ? 'lg' : (n <= 256 ? 'md' : 'sm');
    dom.memGrid.innerHTML = '';
    mem.bloques.forEach((b, i) => {
        const cell = document.createElement('div');
        const bit = mem.mapa_bits[i];
        cell.className = `bit-cell ${bit ? 'one' : 'zero'}`;
        cell.textContent = String(bit);
        const dueño = bit ? `PID ${b.pid} (${nombres.get(b.pid) || '?'})` : 'Libre';
        cell.title = `Casilla ${i} · ${b.inicio}–${b.inicio + b.tamaño} MB · ${dueño}`;
        dom.memGrid.appendChild(cell);
    });
}

// Lista enlazada / Buddy: vista por segmentos (cada uno con su propio color).
function renderSegments(mem) {
    dom.memGrid.className = 'memory-grid memory-grid--segments';
    delete dom.memGrid.dataset.size;
    dom.memGrid.innerHTML = '';
    mem.bloques.forEach((item) => {
        const block = document.createElement('div');
        block.className = `mem-block ${item.libre ? 'free' : 'used'}`;
        block.style.flexGrow = String(item.tamaño);
        if (!item.libre) {
            block.style.backgroundColor = memoryColor(item.pid);
            block.style.borderColor = memoryColor(item.pid);
        }
        const dueño = item.libre ? 'Libre' : `PID ${item.pid}`;
        block.title = `${dueño} · ${item.inicio}–${item.inicio + item.tamaño} MB · ${item.tamaño} MB`;
        if (item.tamaño >= 256) {
            block.textContent = item.libre ? `${item.tamaño} MB` : `PID ${item.pid} · ${item.tamaño} MB`;
        }
        dom.memGrid.appendChild(block);
    });
}

function rangoCasillas(marcos) {
    if (!marcos || marcos.length === 0) return '—';
    return marcos.length === 1 ? `${marcos[0]}` : `${marcos[0]}–${marcos[marcos.length - 1]}`;
}

function renderMemProcs(data) {
    const esBitmap = data.memoria.algoritmo === 'bitmap';
    const u = data.unidad_mb;
    if (!data.procesos.length) {
        dom.memProcTbody.innerHTML = '<tr><td colspan="7" class="metrics-empty">Sin procesos en memoria.</td></tr>';
        return;
    }
    dom.memProcTbody.innerHTML = data.procesos.map(p => {
        const calculo = esBitmap ? `⌈${p.solicitada_mb} / ${u}⌉ = ${p.unidades}` : '—';
        const casillas = esBitmap ? rangoCasillas(p.marcos) : (p.inicio !== null && p.inicio !== undefined ? `${p.inicio} MB` : '—');
        return `<tr>
            <td>${p.pid}</td><td>${escapeHtml(p.nombre)}</td><td>${p.solicitada_mb} MB</td>
            <td class="font-mono">${calculo}</td><td>${p.reservada_mb} MB</td>
            <td class="font-mono">${casillas}</td>
            <td><button class="proc-kill" title="Liberar memoria" data-pid="${p.pid}">✕</button></td>
        </tr>`;
    }).join('');
}

function escapeHtml(t) {
    return String(t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function updateGridFormula(data) {
    if (data.unidad_definida) {
        const total = data.ram_mb / data.unidad_mb;
        dom.gridFormula.innerHTML =
            `Malla = RAM / unidad = <b>${data.ram_mb} MB / ${data.unidad_mb} MB = ${total} casillas</b>`;
    } else {
        dom.gridFormula.innerHTML =
            'Malla = RAM / unidad = <span class="mem-formula-dim">— define una unidad para calcularla</span>';
    }
}

// Vista previa de la fórmula de un proceso mientras se escribe el tamaño.
function updateProcFormula() {
    if (!memLab || !memLab.unidad_definida || memLab.memoria.algoritmo !== 'bitmap') {
        dom.procFormula.innerHTML = '';
        return;
    }
    const size = parseInt(dom.memProcSize.value, 10);
    if (!size || size < 1) { dom.procFormula.innerHTML = ''; return; }
    const u = memLab.unidad_mb;
    dom.procFormula.innerHTML =
        `Casillas del proceso = ⌈tamaño / unidad⌉ = <b>⌈${size} / ${u}⌉ = ${Math.ceil(size / u)}</b> bits en 1`;
}

function renderMemLab(data) {
    memLab = data;
    const mem = data.memoria;
    const definida = data.unidad_definida;

    // Unidad de asignación: SOLO existe en el mapa de bits
    const requiere = data.requiere_unidad;
    const listo = data.listo;
    dom.memSetup.hidden = !requiere;
    if (requiere) {
        dom.ramFixed.textContent = `${data.ram_mb} MB`;
        dom.unitStatus.textContent = definida ? `Unidad: ${data.unidad_mb} MB` : 'Sin definir';
        dom.unitStatus.className = `status-badge ${definida ? 'ready' : 'idle'}`;
        if (definida && document.activeElement !== dom.unitInput) dom.unitInput.value = data.unidad_mb;
        dom.unitInput.title = `Valores válidos: ${data.unidades_validas.join(', ')}`;
        updateGridFormula(data);
    }

    // La memoria se activa cuando termina la definición de la unidad (mapa de bits);
    // la lista ligada y el sistema de asociados no la necesitan.
    dom.memWorkspace.disabled = !listo;
    dom.memWorkspace.classList.toggle('is-locked', !listo);
    dom.memLockedNote.hidden = listo;
    dom.btnResetMem.disabled = !definida;
    dom.memProcTable.dataset.modo = mem.algoritmo === 'bitmap' ? 'bitmap' : 'otro';

    // Apartado activo (cada apartado conserva su propio estado)
    dom.memSectionTitle.textContent = mem.algoritmo_nombre;
    dom.algoDesc.textContent = ALGO_DESC[mem.algoritmo] || '';
    dom.fitNav.querySelectorAll('.fit-tab').forEach(b => b.classList.toggle('active', b.dataset.alg === mem.algoritmo));
    dom.thPos.textContent = mem.algoritmo === 'bitmap' ? 'Casillas' : 'Dirección';

    // Mapa
    const esBitmap = mem.algoritmo === 'bitmap';
    dom.memGridLabel.textContent = esBitmap
        ? `Mapa de bits · ${mem.total_unidades} casillas de ${mem.unidad_mb} MB:`
        : `${mem.algoritmo_nombre} · mapa físico:`;
    dom.memLegend.hidden = !esBitmap;
    if (esBitmap) renderBitmap(mem, data.procesos); else renderSegments(mem);

    // Estadísticas
    dom.memTotal.textContent = `${mem.total_mb} MB`;
    dom.memAvail.textContent = `${mem.disponible_mb} MB`;
    dom.memUsage.textContent = `${Math.round(mem.uso_pct)}%`;
    dom.memRequested.textContent = `${mem.solicitada_mb} MB`;
    dom.memReserved.textContent = `${mem.reservada_mb} MB`;
    dom.memInternal.textContent = `${mem.fragmentacion_interna_mb} MB`;
    dom.memExternal.textContent = `${mem.fragmentacion_externa_mb} MB`;
    dom.memLargest.textContent = `${mem.mayor_hueco_libre_mb} MB`;

    renderMemProcs(data);
    updateProcFormula();
}

async function memAction(promise) {
    const res = await promise;
    if (res.ok) {
        renderMemLab(res);
        showMemMessage(res.msg, 'ok');
    } else {
        showMemMessage(res.msg || 'Operación rechazada.', 'err');
    }
    return res;
}

const setUnit      = () => memAction(apiPost('/memlab/unit', { unidad: parseInt(dom.unitInput.value, 10) }));
const resetMemory  = () => memAction(apiPost('/memlab/reset'));
const freeMemProc  = (pid) => memAction(apiDelete(`/memlab/process/${pid}`));
async function allocMemProc() {
    const res = await memAction(apiPost('/memlab/process', {
        nombre: dom.memProcName.value.trim(),
        memoria_mb: parseInt(dom.memProcSize.value, 10),
    }));
    if (res.ok) dom.memProcName.value = '';
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


// ─── NAVEGACIÓN ENTRE APARTADOS ────────────────────────────────
const FITS = ['first_fit', 'next_fit', 'best_fit', 'worst_fit'];
let secActual = 'bitmap';

const ALGO_DESC = {
    bitmap:    'La RAM se divide en unidades de asignación y hay un bit por unidad: 0 = libre, 1 = ocupada. Un proceso necesita ⌈tamaño / unidad⌉ casillas contiguas en 0; se toma la primera secuencia disponible.',
    first_fit: 'Recorre la lista desde el inicio y usa el primer hueco donde cabe el proceso; el sobrante queda como un nuevo nodo libre.',
    next_fit:  'Igual que First Fit, pero la búsqueda continúa desde donde terminó la última asignación (lista circular).',
    best_fit:  'Revisa toda la lista y elige el hueco más pequeño en el que cabe el proceso (deja el menor sobrante).',
    worst_fit: 'Revisa toda la lista (toda la memoria libre) y siempre elige el hueco más grande, aunque otro se ajuste mejor; el sobrante queda como un nuevo hueco.',
    buddy:     'Los bloques son potencias de 2. Un bloque se parte en dos «asociados» hasta el tamaño justo; al liberar, se fusiona con su asociado si también está libre.',
};
const PG_DESC = {
    opt:  'Óptimo: reemplaza la página que tardará más en volver a usarse. No es implementable en la práctica (requiere conocer el futuro), pero sirve como referencia.',
    nru:  'No usada recientemente: cada página tiene bits R (referenciada) y M (modificada). Sale una de la clase más baja: 0 = R0M0, 1 = R0M1, 2 = R1M0, 3 = R1M1. R se limpia periódicamente. Desempate: la más antigua.',
    fifo: 'Primera en entrar, primera en salir: reemplaza la página que lleva más tiempo en memoria, sin importar cuánto se usa (puede sufrir la anomalía de Belady).',
    lru:  'Menos recientemente usada: reemplaza la página que lleva más tiempo sin referenciarse. Aproxima a OPT usando el pasado. La fila «Recencia» muestra el orden de menos a más reciente.',
};

const seccionDe = alg => FITS.includes(alg) ? 'lista' : alg;

function updateSectionUI() {
    dom.algoNav.querySelectorAll('.algo-tab').forEach(b => b.classList.toggle('active', b.dataset.sec === secActual));
    dom.secAlloc.hidden = secActual === 'paginas';
    dom.secPaging.hidden = secActual !== 'paginas';
    dom.fitNav.hidden = secActual !== 'lista';
    if (secActual === 'paginas') updatePagingHeader();
}

async function selectSection(sec) {
    secActual = sec;
    updateSectionUI();
    if (sec === 'paginas') return;
    const alg = sec === 'lista'
        ? (memLab && FITS.includes(memLab.activo) ? memLab.activo : 'first_fit')
        : sec;
    await selectAlgorithm(alg);
}

async function selectAlgorithm(alg) {
    const res = await apiPost('/memlab/strategy', { tipo: alg });
    if (res.ok) { renderMemLab(res); showMemMessage('', 'info'); }
    else showMemMessage(res.msg, 'err');
}

// ─── REEMPLAZO DE PÁGINAS ──────────────────────────────────────────────
let pgAlg = 'opt';
let pgData = null;      // resultado de /api/paging/simulate
let pgStep = 0;         // pasos visibles (0..n)
let pgTimer = null;

function updatePagingHeader() {
    dom.pgNav.querySelectorAll('.fit-tab').forEach(b => b.classList.toggle('active', b.dataset.alg === pgAlg));
    dom.pgDesc.textContent = PG_DESC[pgAlg];
    dom.pgNruBox.hidden = pgAlg !== 'nru';
}

function pgStop() {
    clearInterval(pgTimer);
    pgTimer = null;
    dom.pgPlay.textContent = '▶ Reproducir';
}

async function runPaging() {
    pgStop();
    const res = await apiPost('/paging/simulate', {
        algoritmo: pgAlg,
        referencias: dom.pgRefs.value,
        marcos: parseInt(dom.pgFrames.value, 10),
        intervalo_nru: parseInt(dom.pgInterval.value, 10) || 4,
    });
    if (!res.ok) {
        dom.pgMessage.textContent = res.msg;
        dom.pgMessage.dataset.kind = 'err';
        return;
    }
    dom.pgMessage.textContent = '';
    pgData = res.resultado;
    pgStep = pgData.pasos.length;
    dom.pgResult.hidden = false;
    renderPaging();
}

function renderPaging() {
    const r = pgData;
    if (!r) return;
    const n = r.pasos.length;
    dom.pgSlider.max = n;
    dom.pgSlider.value = pgStep;
    dom.pgStepLabel.textContent = `${pgStep} / ${n}`;

    const cabecera = r.pasos.map((p, i) =>
        `<th class="${colClass(i)}">${p.ref}${p.escritura ? '<sup>w</sup>' : ''}</th>`).join('');
    let html = `<thead><tr><th class="pg-rowhead">Referencia</th>${cabecera}</tr></thead><tbody>`;
    for (let m = 0; m < r.marcos; m++) {
        html += `<tr><th class="pg-rowhead">Marco ${m}</th>`;
        r.pasos.forEach((p, i) => {
            const c = p.marcos[m];
            const nuevo = p.falla && p.posicion === m;
            const rm = c && r.algoritmo === 'nru' ? `<span class="pg-rm">R${c.r} M${c.m}</span>` : '';
            html += `<td class="${colClass(i)}${nuevo ? ' pg-new' : ''}">${c ? c.pagina : ''}${rm}</td>`;
        });
        html += '</tr>';
    }
    if (r.algoritmo === 'lru') {
        html += '<tr class="pg-extra"><th class="pg-rowhead">Recencia (− → +)</th>' +
            r.pasos.map((p, i) => `<td class="${colClass(i)}">${p.recencia.join(' ')}</td>`).join('') + '</tr>';
    }
    html += '<tr class="pg-faultrow"><th class="pg-rowhead">Resultado</th>' +
        r.pasos.map((p, i) => `<td class="${colClass(i)} ${p.falla ? 'pg-fault' : 'pg-hit'}">${p.falla ? 'Falla' : 'Acierto'}</td>`).join('') +
        '</tr></tbody>';
    dom.pgTable.innerHTML = html;

    // Detalle del paso actual
    if (pgStep === 0) {
        dom.pgDetail.textContent = 'Pulsa «Siguiente» o «Reproducir» para avanzar referencia por referencia.';
    } else {
        const p = r.pasos[pgStep - 1];
        dom.pgDetail.innerHTML = `<b>Referencia ${pgStep}: página ${p.ref}${p.escritura ? ' (escritura)' : ''}.</b> ${escapeHtml(p.detalle)}`;
    }

    // Estadísticas (hasta el paso visible)
    const vistos = r.pasos.slice(0, pgStep);
    const fallas = vistos.filter(p => p.falla).length;
    dom.pgTotal.textContent = `${pgStep} / ${r.total}`;
    dom.pgFaults.textContent = `${fallas}` + (pgStep ? ` (${(fallas / pgStep * 100).toFixed(1)}%)` : '');
    dom.pgHits.textContent = `${pgStep - fallas}`;
    dom.pgBadge.textContent = `${r.fallas} fallas`;

    // Comparación de los 4 algoritmos
    const max = Math.max(...r.comparacion.map(c => c.fallas), 1);
    dom.pgCompare.innerHTML = r.comparacion.map(c => `
        <div class="pg-bar-row${c.algoritmo === r.algoritmo ? ' active' : ''}">
            <span class="pg-bar-name">${c.algoritmo.toUpperCase()}</span>
            <div class="pg-bar-track"><div class="pg-bar-fill" style="width:${c.fallas / max * 100}%"></div></div>
            <span class="pg-bar-val font-mono">${c.fallas}</span>
        </div>`).join('');
}

function colClass(i) {
    if (i >= pgStep) return 'pg-hidden';
    return i === pgStep - 1 ? 'pg-current' : '';
}

function pgGoto(n) {
    if (!pgData) return;
    pgStep = Math.max(0, Math.min(pgData.pasos.length, n));
    renderPaging();
}

function pgTogglePlay() {
    if (!pgData) return;
    if (pgTimer) { pgStop(); return; }
    if (pgStep >= pgData.pasos.length) pgStep = 0;
    dom.pgPlay.textContent = '⏸ Pausar';
    pgTimer = setInterval(() => {
        if (pgStep >= pgData.pasos.length) { pgStop(); return; }
        pgGoto(pgStep + 1);
    }, 700);
    pgGoto(pgStep + 1);
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

    // RAM (resumen; el detalle vive en el módulo de memoria)
    updateRamSummary(data.memoria);

    // Procesos
    renderProcessList(data.procesos);

    // Métricas
    updateMetrics(data.procesos_terminados, data.scheduler);
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
        uptimeTimer = setInterval(() => {
            uptimeSeconds++;
            dom.time.textContent = formatTime(uptimeSeconds);
        }, 1000);
    } else {
        clearInterval(pollTimer);
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

    if (memoria < 1 || memoria > 2048) { alert('Memoria fuera de rango (1–2048 MB)'); return; }
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

// Selector de módulo + módulo de memoria
dom.tabProcesses.addEventListener('click', () => setMode('processes'));
dom.tabMemory.addEventListener('click',    () => setMode('memory'));
dom.tabIo.addEventListener('click',        () => setMode('io'));
dom.btnSetUnit.addEventListener('click',   setUnit);
dom.unitInput.addEventListener('keydown',  e => { if (e.key === 'Enter') setUnit(); });
dom.btnResetMem.addEventListener('click',  resetMemory);
dom.algoNav.addEventListener('click', e => {
    const b = e.target.closest('.algo-tab');
    if (b) selectSection(b.dataset.sec);
});
dom.fitNav.addEventListener('click', e => {
    const b = e.target.closest('.fit-tab');
    if (b) selectAlgorithm(b.dataset.alg);
});
dom.pgNav.addEventListener('click', e => {
    const b = e.target.closest('.fit-tab');
    if (!b) return;
    pgAlg = b.dataset.alg;
    updatePagingHeader();
    runPaging();
});
dom.pgRun.addEventListener('click', runPaging);
dom.pgRefs.addEventListener('keydown', e => { if (e.key === 'Enter') runPaging(); });
dom.pgPrev.addEventListener('click', () => { pgStop(); pgGoto(pgStep - 1); });
dom.pgNext.addEventListener('click', () => { pgStop(); pgGoto(pgStep + 1); });
dom.pgAll.addEventListener('click',  () => { pgStop(); pgGoto(pgData ? pgData.pasos.length : 0); });
dom.pgPlay.addEventListener('click', pgTogglePlay);
dom.pgSlider.addEventListener('input', () => { pgStop(); pgGoto(parseInt(dom.pgSlider.value, 10)); });
dom.btnMemAlloc.addEventListener('click',  allocMemProc);
dom.memProcSize.addEventListener('input',  updateProcFormula);
dom.memProcSize.addEventListener('keydown', e => { if (e.key === 'Enter') allocMemProc(); });
dom.memProcName.addEventListener('keydown', e => { if (e.key === 'Enter') allocMemProc(); });
dom.memProcTbody.addEventListener('click', e => {
    const btn = e.target.closest('.proc-kill');
    if (btn) freeMemProc(parseInt(btn.dataset.pid, 10));
});

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
            updateRamSummary(data.memoria);
            renderProcessList(data.procesos);
            updateMetrics(data.procesos_terminados, data.scheduler);
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
