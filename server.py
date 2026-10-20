"""
server.py
=========
Servidor Flask que expone el Kernel Python como API REST,
y sirve el frontend (index.html, style.css, script.js).

Ejecutar:
    uv run python server.py
    ó
    .venv/bin/python server.py

Luego abrir:
    http://localhost:5000
"""

from __future__ import annotations
import os
import sys

from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS

# ── Importar el paquete os_simulator ──────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from os_simulator.core.kernel import Kernel
from os_simulator.memory.memory import ALGORITMOS_MEMORIA, Memoria, unidades_validas
from os_simulator.memory.paginacion import ALGORITMOS_PAGINAS, comparar, parsear_referencias, simular
from os_simulator.filesystem.almacenamiento import ALGORITMOS_ARCHIVOS, ALGORITMOS_DISPONIBLES, crear_gestor
from os_simulator.hardware.usb import MonitorUSB, crear_backend
from os_simulator.processes.schedulers import SCHEDULERS_DISPONIBLES

# ══════════════════════════════════════════════════════════════════════
# Flask app y CORS
# ══════════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=BASE_DIR,
    static_url_path="",
)
CORS(app)

# ══════════════════════════════════════════════════════════════════════
# Kernel singleton — un solo kernel para toda la sesión del servidor
# ══════════════════════════════════════════════════════════════════════
RAM_MB = 2048  # La RAM del sistema es una constante: el usuario NO puede cambiarla.

kernel: Kernel = Kernel(nombre="BALJ OS", version="0.1.0", ram_mb=RAM_MB)

# ── Módulo de memoria INDEPENDIENTE ──────────────────────────────────
# Instancia propia de Memoria, separada del kernel: no necesita CPU,
# planificador ni que el SO esté iniciado. Arranca sin unidad de asignación
# definida y el módulo permanece bloqueado hasta que el usuario la define.
memoria_lab: Memoria = Memoria(capacidad_total=RAM_MB, algoritmo="bitmap")
_lab_nombres: dict[int, str] = {}
_lab_siguiente_pid = 1

# ── Módulo de archivos INDEPENDIENTE (Avance 5) ──────────────────────
# Disco de 20 bloques (0-19), igual al escenario del enunciado. Empieza
# en el Algoritmo 1 (asignación continua); los Algoritmos 2 y 3 todavía
# no tienen gestor (ver os_simulator/filesystem/almacenamiento.py).
TOTAL_BLOQUES_DISCO = 20
filelab_gestor = crear_gestor("continua", TOTAL_BLOQUES_DISCO)

# ── Dispositivos de E/S (USB) ────────────────────────────────────────
# El monitor corre en su propio hilo y detecta conexiones/desconexiones solo.
# USB_BACKEND = auto (por defecto) | wmi | sysfs | sim
monitor_usb: MonitorUSB = MonitorUSB(crear_backend(os.environ.get("USB_BACKEND", "auto")))
monitor_usb.iniciar()


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════
def _ok(data: dict | None = None, msg: str = "ok") -> tuple:
    payload = {"ok": True, "msg": msg}
    if data:
        payload.update(data)
    return jsonify(payload), 200


def _err(msg: str, code: int = 400) -> tuple:
    return jsonify({"ok": False, "msg": msg}), code


def _serializar_log(entradas) -> list[dict]:
    """Convierte EntradaLog en dicts JSON-serializables."""
    return [
        {
            "time":  e.timestamp.strftime("%H:%M:%S"),
            "level": e.nivel,
            "msg":   e.mensaje,
        }
        for e in entradas
    ]


# ══════════════════════════════════════════════════════════════════════
# Rutas estáticas
# ══════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    """Sirve el frontend principal."""
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename: str):
    """Sirve style.css, script.js y cualquier otro asset."""
    safe_path = os.path.join(BASE_DIR, filename)
    if not os.path.isfile(safe_path):
        abort(404)
    return send_from_directory(BASE_DIR, filename)


# ══════════════════════════════════════════════════════════════════════
# API — Ciclo de vida del Kernel
# ══════════════════════════════════════════════════════════════════════
@app.route("/api/start", methods=["POST"])
def api_start():
    if kernel.activo:
        return _err("El kernel ya está en ejecución.")
    try:
        kernel.arrancar()
        return _ok(msg="Kernel iniciado.")
    except Exception as e:
        return _err(str(e))


@app.route("/api/stop", methods=["POST"])
def api_stop():
    if not kernel.activo:
        return _err("El kernel ya estaba detenido.")
    kernel.detener()
    return _ok(msg="Kernel detenido.")


@app.route("/api/restart", methods=["POST"])
def api_restart():
    kernel.reiniciar()
    return _ok(msg="Kernel reiniciado.")


@app.route("/api/tick", methods=["POST"])
def api_tick():
    if not kernel.activo:
        return _err("El kernel está inactivo. Inicia el SO primero.")
    kernel.avanzar_ciclo()
    return _ok(msg=f"Ciclo #{kernel.ciclo_reloj} ejecutado.")


# ══════════════════════════════════════════════════════════════════════
# API — Planificador
# ══════════════════════════════════════════════════════════════════════
@app.route("/api/scheduler", methods=["GET"])
def api_get_scheduler():
    """Devuelve el scheduler activo y la lista de schedulers disponibles."""
    return jsonify({
        "ok":          True,
        "scheduler":   kernel.scheduler.nombre,
        "disponibles": SCHEDULERS_DISPONIBLES,
    })


@app.route("/api/scheduler", methods=["POST"])
def api_set_scheduler():
    """
    Cambia el algoritmo de planificación del Kernel.

    Body JSON:
        {
          "tipo": "round_robin",   // clave del algoritmo
          "quantum": 3,            // opcional, para round_robin / dos_niveles
          "max_activos": 3         // opcional, para dos_niveles
        }
    """
    data = request.get_json(silent=True) or {}
    tipo = str(data.get("tipo", "fcfs")).lower().strip()

    # Parámetros opcionales
    kwargs: dict = {}
    if "quantum" in data:
        kwargs["quantum"] = max(1, int(data["quantum"]))
    if "quantum_interno" in data:
        kwargs["quantum_interno"] = max(1, int(data["quantum_interno"]))
    if "max_activos" in data:
        kwargs["max_activos"] = max(1, int(data["max_activos"]))

    try:
        kernel.cambiar_scheduler(tipo, **kwargs)
    except ValueError as e:
        return _err(str(e))

    return _ok(
        {"scheduler": kernel.scheduler.nombre},
        msg=f"Planificador cambiado a '{kernel.scheduler.nombre}'.",
    )


# ══════════════════════════════════════════════════════════════════════
# API — Administración de memoria
# ══════════════════════════════════════════════════════════════════════
@app.route("/api/memory/strategy", methods=["GET"])
def api_get_memory_strategy():
    """Devuelve el algoritmo de memoria activo y las opciones disponibles."""
    return jsonify({
        "ok": True,
        "algoritmo": kernel.memoria.algoritmo,
        "nombre": kernel.memoria.algoritmo_nombre,
        "disponibles": ALGORITMOS_MEMORIA,
    })


@app.route("/api/memory/strategy", methods=["POST"])
def api_set_memory_strategy():
    """Cambia el algoritmo si no existen procesos en CPU ni en la cola."""
    data = request.get_json(silent=True) or {}
    tipo = str(data.get("tipo", "bitmap")).lower().strip()
    try:
        kernel.cambiar_algoritmo_memoria(tipo)
    except (RuntimeError, ValueError) as exc:
        return _err(str(exc), 409 if isinstance(exc, RuntimeError) else 400)
    return _ok(
        {
            "algoritmo": kernel.memoria.algoritmo,
            "nombre": kernel.memoria.algoritmo_nombre,
        },
        msg=f"Gestor de memoria cambiado a '{kernel.memoria.algoritmo_nombre}'.",
    )


# ══════════════════════════════════════════════════════════════════════
# API — Módulo de memoria independiente (/api/memlab)
# ══════════════════════════════════════════════════════════════════════
def _estado_memlab() -> dict:
    estado = memoria_lab.estado()
    procesos = []
    for pid, datos in sorted(estado["asignaciones"].items()):
        procesos.append({
            "pid": pid,
            "nombre": _lab_nombres.get(pid, f"proceso_{pid}"),
            "solicitada_mb": datos["solicitada_mb"],
            "reservada_mb": datos["reservada_mb"],
            "unidades": datos.get("unidades"),
            "marcos": datos.get("marcos"),
            "inicio": datos.get("inicio"),
        })
    return {
        "ok": True,
        "ram_mb": RAM_MB,
        "activo": memoria_lab.algoritmo,
        "requiere_unidad": memoria_lab.requiere_unidad,   # solo el mapa de bits
        "listo": memoria_lab.listo,
        "unidad_definida": memoria_lab.unidad_definida and memoria_lab.requiere_unidad,
        "unidad_mb": memoria_lab.unidad_asignacion if memoria_lab.requiere_unidad else None,
        "unidades_validas": unidades_validas(RAM_MB),
        "algoritmos": ALGORITMOS_MEMORIA,
        "memoria": estado,
        "procesos": procesos,
    }


@app.route("/api/memlab", methods=["GET"])
def api_memlab_estado():
    return jsonify(_estado_memlab())


@app.route("/api/memlab/unit", methods=["POST"])
def api_memlab_unidad():
    """Define o cambia la unidad de asignación (solo mapa de bits, con memoria vacía)."""
    if not memoria_lab.requiere_unidad:
        return _err("La unidad de asignación solo aplica al mapa de bits.", 409)
    data = request.get_json(silent=True) or {}
    try:
        unidad = int(data.get("unidad"))
    except (TypeError, ValueError):
        return _err("Ingresa un número entero para la unidad de asignación.")
    try:
        memoria_lab.configurar_unidad(unidad)
    except RuntimeError as exc:
        return _err(str(exc), 409)
    except ValueError as exc:
        return _err(str(exc))
    total = RAM_MB // unidad
    return _ok(_estado_memlab(), msg=f"Unidad definida: {unidad} MB → {RAM_MB} / {unidad} = {total} unidades.")


@app.route("/api/memlab/strategy", methods=["POST"])
def api_memlab_estrategia():
    """Cambia el algoritmo activo: bitmap, first/next/best/worst_fit o buddy."""
    data = request.get_json(silent=True) or {}
    try:
        memoria_lab.cambiar_algoritmo(str(data.get("tipo", "bitmap")))
    except RuntimeError as exc:
        return _err(str(exc), 409)
    except ValueError as exc:
        return _err(str(exc))
    return _ok(_estado_memlab(), msg=f"Administrador: {memoria_lab.algoritmo_nombre}.")


@app.route("/api/memlab/process", methods=["POST"])
def api_memlab_asignar():
    global _lab_siguiente_pid
    if not memoria_lab.listo:
        return _err("Define primero la unidad de asignación.", 409)
    data = request.get_json(silent=True) or {}
    try:
        memoria = int(data.get("memoria_mb"))
    except (TypeError, ValueError):
        return _err("El tamaño del proceso debe ser un número entero (MB).")
    if not 1 <= memoria <= RAM_MB:
        return _err(f"El tamaño debe estar entre 1 y {RAM_MB} MB.")
    pid = _lab_siguiente_pid
    nombre = str(data.get("nombre") or f"proceso_{pid}").strip()[:24]
    if not memoria_lab.asignar(pid, memoria):
        return _err(f"No hay espacio suficiente para '{nombre}' ({memoria} MB).", 409)
    _lab_siguiente_pid += 1
    _lab_nombres[pid] = nombre
    estado = _estado_memlab()
    decision = estado["memoria"].get("decision")
    return _ok(estado, msg=f"'{nombre}' asignado (PID {pid})." + (f" {decision}" if decision else ""))


@app.route("/api/memlab/process/<int:pid>", methods=["DELETE"])
def api_memlab_liberar(pid: int):
    if memoria_lab.liberar(pid) == 0:
        return _err(f"PID {pid} no tiene memoria asignada.", 404)
    _lab_nombres.pop(pid, None)
    return _ok(_estado_memlab(), msg=f"PID {pid} liberado.")


@app.route("/api/memlab/reset", methods=["POST"])
def api_memlab_reset():
    """Vacía la memoria. En el mapa de bits además vuelve a pedir la unidad."""
    global _lab_siguiente_pid
    if memoria_lab.requiere_unidad:
        memoria_lab.olvidar_unidad()
        msg = "Memoria reiniciada. Define la unidad de asignación."
    else:
        memoria_lab.resetear()
        msg = "Memoria vaciada."
    _lab_nombres.clear()
    _lab_siguiente_pid = 1
    return _ok(_estado_memlab(), msg=msg)


# ══════════════════════════════════════════════════════════════════════
# API — Reemplazo de páginas (apartado independiente, sin estado)
# ══════════════════════════════════════════════════════════════════════
@app.route("/api/paging/simulate", methods=["POST"])
def api_paging_simular():
    data = request.get_json(silent=True) or {}
    try:
        refs = parsear_referencias(str(data.get("referencias", "")))
        marcos = int(data.get("marcos", 3))
        intervalo = int(data.get("intervalo_nru", 4))
        resultado = simular(str(data.get("algoritmo", "fifo")), refs, marcos, intervalo)
        resultado["comparacion"] = comparar(refs, marcos, intervalo)
    except (ValueError, TypeError) as exc:
        return _err(str(exc))
    return _ok({"resultado": resultado})


# ══════════════════════════════════════════════════════════════════════
# API — Módulo de archivos independiente (/api/filelab) — Avance 5
# ══════════════════════════════════════════════════════════════════════
def _rango_bloques(info: dict) -> str:
    inicio, longitud = info["bloque_inicio"], info["longitud"]
    if longitud == 1:
        return f"bloque {inicio}"
    return f"bloques {inicio}–{inicio + longitud - 1}"


def _estado_filelab() -> dict:
    estado = filelab_gestor.estado()
    archivos = [
        {"nombre": nombre, **datos}
        for nombre, datos in sorted(estado["archivos"].items())
    ]
    return {
        "ok": True,
        "total_bloques": TOTAL_BLOQUES_DISCO,
        "activo": filelab_gestor.clave,
        "algoritmos": ALGORITMOS_ARCHIVOS,
        "algoritmos_disponibles": list(ALGORITMOS_DISPONIBLES),
        "disco": estado,
        "archivos": archivos,
    }


@app.route("/api/filelab", methods=["GET"])
def api_filelab_estado():
    """4. Mostrar estado del disco / 5. Mostrar espacio disponible."""
    return jsonify(_estado_filelab())


@app.route("/api/filelab/strategy", methods=["POST"])
def api_filelab_estrategia():
    """Cambia el algoritmo activo (solo con el disco vacío)."""
    global filelab_gestor
    data = request.get_json(silent=True) or {}
    tipo = str(data.get("tipo", "continua")).lower().strip()
    if filelab_gestor.archivos:
        return _err("No se puede cambiar el algoritmo mientras haya archivos en el disco.", 409)
    try:
        nuevo_gestor = crear_gestor(tipo, TOTAL_BLOQUES_DISCO)
    except NotImplementedError as exc:
        return _err(str(exc), 409)
    except ValueError as exc:
        return _err(str(exc), 400)
    filelab_gestor = nuevo_gestor
    return _ok(_estado_filelab(), msg=f"Algoritmo activo: {filelab_gestor.nombre}.")


@app.route("/api/filelab/file", methods=["POST"])
def api_filelab_crear():
    """1. Crear archivo."""
    data = request.get_json(silent=True) or {}
    nombre = str(data.get("nombre", "")).strip()
    if not nombre:
        return _err("Ingresa un nombre de archivo.")
    try:
        bloques = int(data.get("bloques"))
    except (TypeError, ValueError):
        return _err("El tamaño debe ser un número entero de bloques.")
    if bloques <= 0:
        return _err("El tamaño debe ser mayor a 0 bloques.")

    try:
        info = filelab_gestor.crear_archivo(nombre, bloques)
    except (FileExistsError, RuntimeError) as exc:
        return _err(str(exc), 409)
    except ValueError as exc:
        return _err(str(exc))

    estado = _estado_filelab()
    return _ok(estado, msg=f"'{nombre}' creado en {_rango_bloques(info)}.")


@app.route("/api/filelab/disco", methods=["GET"])
def api_filelab_disco():
    """4. Mostrar estado del disco: cada bloque ocupado o libre."""
    estado = _estado_filelab()
    ocupados = [b["indice"] for b in estado["disco"]["bloques"] if not b["libre"]]
    libres = estado["disco"]["bloques_libres"]
    return _ok(
        estado,
        msg=(
            f"Disco de {estado['total_bloques']} bloques (0–{estado['total_bloques'] - 1}). "
            f"Ocupados: {len(ocupados)}. Libres: {len(libres)}."
        ),
    )


@app.route("/api/filelab/espacio", methods=["GET"])
def api_filelab_espacio():
    """5. Mostrar espacio disponible."""
    estado = _estado_filelab()
    disco = estado["disco"]
    return _ok(
        {
            **estado,
            "espacio": {
                "bloques_disponibles": disco["bloques_disponibles"],
                "bloques_libres": disco["bloques_libres"],
                "huecos_libres": disco["huecos_libres"],
                "mayor_hueco_libre": disco["mayor_hueco_libre"],
            },
        },
        msg=(
            f"Espacio disponible: {disco['bloques_disponibles']} de "
            f"{disco['total_bloques']} bloques. "
            f"Mayor hueco contiguo: {disco['mayor_hueco_libre']} bloques."
        ),
    )


@app.route("/api/filelab/file/<path:nombre>", methods=["GET"])
def api_filelab_consultar(nombre: str):
    """2. Consultar archivo: bloques asignados y estructura de control."""
    try:
        info = filelab_gestor.consultar_archivo(nombre)
    except FileNotFoundError as exc:
        return _err(str(exc), 404)
    return _ok(
        {"archivo": {"nombre": nombre, **info}},
        msg=f"'{nombre}' ocupa {_rango_bloques(info)} (inicio={info['bloque_inicio']}, longitud={info['longitud']}).",
    )


@app.route("/api/filelab/file/<path:nombre>", methods=["DELETE"])
def api_filelab_eliminar(nombre: str):
    """3. Eliminar archivo."""
    try:
        filelab_gestor.eliminar_archivo(nombre)
    except FileNotFoundError as exc:
        return _err(str(exc), 404)
    return _ok(_estado_filelab(), msg=f"'{nombre}' eliminado.")


@app.route("/api/filelab/reset", methods=["POST"])
def api_filelab_reset():
    filelab_gestor.resetear()
    return _ok(_estado_filelab(), msg="Disco vaciado.")


# ══════════════════════════════════════════════════════════════════════
# API — Procesos
# ══════════════════════════════════════════════════════════════════════
@app.route("/api/process", methods=["POST"])
def api_create_process():
    """
    Crea un nuevo proceso.

    Body JSON:
        {
          "nombre":     "calc.exe",
          "memoria_mb": 128,
          "burst_time": 5,          // ciclos de CPU requeridos
          "nice_value": 0           // prioridad numérica (-20 urgente a +19)
        }
    """
    data = request.get_json(silent=True) or {}
    nombre     = data.get("nombre", "proceso")
    memoria    = int(data.get("memoria_mb", 128))
    burst_time = max(1, int(data.get("burst_time", 5)))
    nice_value = int(data.get("nice_value", 0))

    if not kernel.activo:
        return _err("El kernel está inactivo. Inicia el SO primero.")

    proceso = kernel.crear_proceso(
        nombre,
        memoria_mb=memoria,
        burst_time=burst_time,
        nice_value=nice_value,
    )
    if proceso is None:
        return _err(f"No hay memoria suficiente para '{nombre}' ({memoria} MB).")

    return _ok(
        {
            "pid":        proceso.pid,
            "nombre":     proceso.nombre,
            "estado":     proceso.estado.name,
            "memoria":    proceso.memoria_requerida,
            "burst_time": proceso.burst_time,
            "nice_value": proceso.nice_value,
        },
        msg=f"Proceso '{nombre}' creado con PID {proceso.pid}.",
    )


@app.route("/api/process/<int:pid>", methods=["DELETE"])
def api_kill_process(pid: int):
    if not kernel.terminar_proceso(pid):
        return _err(f"PID {pid} no encontrado.", 404)
    return _ok(msg=f"Proceso PID {pid} terminado.")


# ══════════════════════════════════════════════════════════════════════
# API — Estado y Log
# ══════════════════════════════════════════════════════════════════════
@app.route("/api/state", methods=["GET"])
def api_state():
    """
    Devuelve el estado completo del sistema + nuevas entradas de log.
    El cliente envía el parámetro `log_offset` para recibir solo
    las entradas nuevas desde la última consulta.
    """
    estado = kernel.estado()

    # Construir lista de procesos para la UI: CPU + cola
    procesos_ui = []
    if not kernel.cpu.esta_libre:
        p = kernel.cpu.proceso_actual
        procesos_ui.append({
            "pid":           p.pid,
            "nombre":        p.nombre,
            "estado":        "EJECUTANDO",
            "memoria":       p.memoria_requerida,
            "burst_time":    p.burst_time,
            "remaining_time": p.remaining_time,
            "nice_value":    p.nice_value,
            "queue_level":   p.queue_level,
        })
    for p_data in estado["procesos_en_cola"]:
        procesos_ui.append({
            "pid":           p_data["pid"],
            "nombre":        p_data["nombre"],
            "estado":        p_data["estado"],
            "memoria":       p_data["memoria"],
            "burst_time":    p_data["burst_time"],
            "remaining_time": p_data["remaining_time"],
            "nice_value":    p_data["nice_value"],
            "queue_level":   p_data["queue_level"],
        })

    # Log incremental
    client_offset = int(request.args.get("log_offset", 0))
    todas = kernel.log
    nuevas = _serializar_log(todas[client_offset:])
    nuevo_offset = len(todas)

    return jsonify({
        "ok":                  True,
        "activo":              kernel.activo,
        "ciclo":               kernel.ciclo_reloj,
        "scheduler":           estado["kernel"]["scheduler"],
        "cpu":                 estado["cpu"],
        "memoria":             estado["memoria"],
        "procesos":            procesos_ui,
        "procesos_terminados": estado["procesos_terminados"],
        "dispositivos":        estado["dispositivos"],
        "log_nuevas":          nuevas,
        "log_offset":          nuevo_offset,
    })


@app.route("/api/log", methods=["GET"])
def api_log():
    n = int(request.args.get("n", 50))
    return jsonify({
        "ok":  True,
        "log": _serializar_log(kernel.ultimo_log(n)),
    })


# ══════════════════════════════════════════════════════════════════════
# Punto de entrada
# ══════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════
# API — Dispositivos de E/S (USB)
# ══════════════════════════════════════════════════════════════════════
@app.route("/api/usb", methods=["GET"])
def api_usb_estado():
    """Listado actual de dispositivos USB + driver. «version» cambia con cada conexión/desconexión."""
    return jsonify(monitor_usb.estado())


@app.route("/api/usb/sim/connect", methods=["POST"])
def api_usb_sim_conectar():
    if not monitor_usb.simulado:
        return _err("El modo simulado no está activo: se están leyendo dispositivos USB reales.", 409)
    clave = str((request.get_json(silent=True) or {}).get("modelo", ""))
    try:
        monitor_usb.backend.conectar(clave)
    except KeyError:
        return _err(f"Modelo de dispositivo desconocido: '{clave}'.")
    monitor_usb.sincronizar()
    return _ok(monitor_usb.estado(), msg="Dispositivo simulado conectado.")


@app.route("/api/usb/sim/disconnect", methods=["POST"])
def api_usb_sim_desconectar():
    if not monitor_usb.simulado:
        return _err("El modo simulado no está activo: se están leyendo dispositivos USB reales.", 409)
    did = str((request.get_json(silent=True) or {}).get("id", ""))
    if not monitor_usb.backend.desconectar(did):
        return _err("Ese dispositivo ya no está conectado.", 404)
    monitor_usb.sincronizar()
    return _ok(monitor_usb.estado(), msg="Dispositivo simulado desconectado.")



if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║   BALJ OS — Servidor Flask       ║")
    print("║   http://localhost:5000                   ║")
    print("╚══════════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
