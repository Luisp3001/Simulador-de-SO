/* Dispositivos de E/S (USB): listado + driver, con actualización automática.
 * Consulta /api/usb cada 1.5 s mientras la pestaña está abierta; el servidor detecta
 * las conexiones por evento (WMI) y solo sube «version» cuando algo cambia. */
(function () {
    'use strict';

    const $ = (id) => document.getElementById(id);
    const esc = (t) => String(t ?? '').replace(/[&<>"']/g,
        c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const BASE = API;              // misma URL base que script.js

    let timer = null;
    let estado = null;
    let versionPintada = -1;
    let previosPintados = null;
    let conocidos = new Set();     // para resaltar lo recién conectado
    let primeraVez = true;

    async function pedir(ruta, opciones) {
        try {
            const r = await fetch(BASE + ruta, opciones);
            return await r.json();
        } catch (e) {
            return { ok: false, msg: 'No se pudo contactar con el servidor.' };
        }
    }

    function filaDriver(etiqueta, valor) {
        if (valor === null || valor === undefined || valor === '') return '';
        return `<div class="drv-row"><span>${etiqueta}</span><b>${esc(valor)}</b></div>`;
    }

    function bloqueDriver(d, titulo) {
        if (!d) return '';
        const firmado = d.firmado === true ? 'Sí' : (d.firmado === false ? 'No' : null);
        return `<div class="drv">
            ${titulo ? `<div class="drv-title">${esc(titulo)}</div>` : ''}
            ${filaDriver('Driver', d.nombre)}
            ${filaDriver('Proveedor', d.proveedor)}
            ${filaDriver('Versión', d.version)}
            ${filaDriver('Fecha', d.fecha)}
            ${filaDriver('Archivo INF', d.inf)}
            ${filaDriver('Firmado', firmado)}
            ${filaDriver('Firmante', d.firmante)}
            ${filaDriver('Descripción', d.descripcion)}
        </div>`;
    }

    function tarjeta(d, nuevo, simulado) {
        const vidpid = d.vid ? `${d.vid}:${d.pid}` : '';
        const itfs = (d.interfaces || []).map(i =>
            bloqueDriver(i.driver, `${i.nombre}${i.clase ? ' · ' + i.clase : ''}`)).join('');
        const ok = (d.estado || '').startsWith('Funcionando');
        return `<article class="usb-card${nuevo ? ' usb-new' : ''}" data-id="${esc(d.id)}">
            <div class="usb-head">
                <span class="usb-icon">${d.icono}</span>
                <div class="usb-title">
                    <strong>${esc(d.nombre)}</strong>
                    <small>${esc(d.fabricante || 'Fabricante desconocido')}${vidpid ? ' · ' + esc(vidpid) : ''}</small>
                </div>
                <span class="usb-type">${esc(d.tipo_nombre)}</span>
                <span class="status-chip ${ok ? 'ok' : 'warn'}">${ok ? 'OK' : 'Revisar'}</span>
                ${simulado ? `<button class="btn btn-secondary btn-sm usb-unplug" type="button" data-id="${esc(d.id)}">Desconectar</button>` : ''}
            </div>
            <div class="usb-meta">
                <span>Conectado a las ${esc(d.conectado_en)}</span>
                ${d.detalle ? `<span>${esc(d.detalle)}</span>` : ''}
                <span>${esc(d.estado)}</span>
            </div>
            <div class="usb-drivers">
                ${bloqueDriver(d.driver, 'Driver del dispositivo')}
                ${itfs}
            </div>
        </article>`;
    }

    function pintar() {
        if (!estado) return;
        const incluir = $('usb-incluir-previos').checked;
        const visibles = estado.dispositivos.filter(d => incluir || !d.preexistente);
        const ocultos = estado.dispositivos.length - visibles.length;

        // fuente / errores / modo simulado
        $('usb-source').textContent = `Origen: ${estado.backend}` +
            (estado.escaneo_s != null ? ` · último escaneo: ${estado.escaneo_s} s` : '');
        const err = $('usb-error');
        err.hidden = !estado.error;
        err.textContent = estado.error || '';
        $('usb-sim').hidden = !estado.simulado;
        if (estado.simulado && !$('usb-sim-modelo').options.length) {
            $('usb-sim-modelo').innerHTML = (estado.catalogo || [])
                .map(m => `<option value="${esc(m.clave)}">${esc(m.nombre)}</option>`).join('');
        }

        // lista
        const lista = $('usb-list');
        if (!estado.listo) {
            lista.innerHTML = '<div class="usb-empty"><span>⏳</span><p>Buscando dispositivos…</p></div>';
        } else if (!visibles.length) {
            lista.innerHTML = `<div class="usb-empty"><span>🔌</span>
                <p>No se ha conectado ningún dispositivo</p>
                ${ocultos ? `<small>${ocultos} dispositivo(s) ya estaban conectados al abrir el simulador; marca «Incluir los dispositivos ya conectados» para verlos.</small>` : ''}
            </div>`;
        } else {
            lista.innerHTML = visibles.map(d =>
                tarjeta(d, !primeraVez && !conocidos.has(d.id), estado.simulado)).join('');
        }
        conocidos = new Set(estado.dispositivos.map(d => d.id));
        primeraVez = false;

        // actividad
        const ev = $('usb-events');
        ev.innerHTML = estado.eventos.length
            ? estado.eventos.map(e => `<li class="${e.accion}"><time>${esc(e.hora)}</time>
                <span>${e.icono}</span> ${e.accion === 'conectado' ? 'Conectado' : 'Desconectado'}: <b>${esc(e.nombre)}</b>
                <small>${esc(e.tipo_nombre)}</small></li>`).join('')
            : '<li class="vacio">Sin actividad: conecta o desconecta un dispositivo USB.</li>';
    }

    async function refrescar(forzar) {
        const datos = await pedir('/usb');
        if (!datos.ok) return;
        const incluir = $('usb-incluir-previos').checked;
        if (!forzar && datos.version === versionPintada && incluir === previosPintados) return;
        versionPintada = datos.version;
        previosPintados = incluir;
        estado = datos;
        pintar();
    }

    async function accionSim(ruta, cuerpo) {
        const r = await pedir(ruta, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo),
        });
        if (r.ok) { versionPintada = -1; await refrescar(true); }
    }

    function activar(abierto) {
        clearInterval(timer);
        timer = null;
        if (!abierto) return;
        refrescar(true);
        timer = setInterval(() => refrescar(false), 1500);
    }

    $('usb-incluir-previos').addEventListener('change', () => { versionPintada = -1; pintar(); });
    $('usb-sim-conectar').addEventListener('click',
        () => accionSim('/usb/sim/connect', { modelo: $('usb-sim-modelo').value }));
    $('usb-list').addEventListener('click', (e) => {
        const b = e.target.closest('.usb-unplug');
        if (b) accionSim('/usb/sim/disconnect', { id: b.dataset.id });
    });

    window.UsbUI = { activar };
})();
