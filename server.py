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
from os_simulator.memory.memory import ALGORITMOS_MEMORIA
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
kernel: Kernel = Kernel(nombre="Hephaestus Core", version="0.1.0", ram_mb=4096)


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
if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║   Hephaestus Core — Servidor Flask       ║")
    print("║   http://localhost:5000                   ║")
    print("╚══════════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
