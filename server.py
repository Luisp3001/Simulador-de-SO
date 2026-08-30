"""
server.py
=========
Servidor Flask que expone el Kernel Python como API REST,
y sirve el frontend (index.html, style.css, script.js).

Ejecutar:
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
# server.py está en la raíz del proyecto; os_simulator/ es un subdirectorio.
sys.path.insert(0, os.path.dirname(__file__))

from os_simulator.core.kernel import Kernel
from os_simulator.processes.process import PrioridadProceso

# ══════════════════════════════════════════════════════════════════════
# Flask app y CORS
# ══════════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=BASE_DIR,   # sirve CSS / JS desde la raíz del proyecto
    static_url_path="",
)
CORS(app)   # permite peticiones fetch() desde cualquier origen

# ══════════════════════════════════════════════════════════════════════
# Kernel singleton — un solo kernel para toda la sesión del servidor
# ══════════════════════════════════════════════════════════════════════
kernel: Kernel = Kernel(nombre="Aethelred OS", version="0.1.0", ram_mb=4096)

# Contador para saber cuántas entradas de log ya conoce el cliente
_log_offset: int = 0

# Mapa de nombre → PrioridadProceso
_PRIORIDADES: dict[str, PrioridadProceso] = {
    "alta":  PrioridadProceso.ALTA,
    "media": PrioridadProceso.MEDIA,
    "baja":  PrioridadProceso.BAJA,
}


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
            "time": e.timestamp.strftime("%H:%M:%S"),
            "level": e.nivel,
            "msg": e.mensaje,
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
    global _log_offset
    if kernel.activo:
        return _err("El kernel ya está en ejecución.")
    try:
        kernel.arrancar()
        _log_offset = 0
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
    global _log_offset
    kernel.reiniciar()
    _log_offset = 0
    return _ok(msg="Kernel reiniciado.")


@app.route("/api/tick", methods=["POST"])
def api_tick():
    if not kernel.activo:
        return _err("El kernel está inactivo. Inicia el SO primero.")
    kernel.avanzar_ciclo()
    return _ok(msg=f"Ciclo #{kernel.ciclo_reloj} ejecutado.")


# ══════════════════════════════════════════════════════════════════════
# API — Procesos
# ══════════════════════════════════════════════════════════════════════
@app.route("/api/process", methods=["POST"])
def api_create_process():
    data = request.get_json(silent=True) or {}
    nombre    = data.get("nombre", "proceso")
    memoria   = int(data.get("memoria_mb", 128))
    prioridad = _PRIORIDADES.get(
        str(data.get("prioridad", "media")).lower(),
        PrioridadProceso.MEDIA,
    )

    if not kernel.activo:
        return _err("El kernel está inactivo. Inicia el SO primero.")

    proceso = kernel.crear_proceso(nombre, memoria, prioridad)
    if proceso is None:
        return _err(f"No hay memoria suficiente para '{nombre}' ({memoria} MB).")

    return _ok(
        {
            "pid":      proceso.pid,
            "nombre":   proceso.nombre,
            "estado":   proceso.estado.name,
            "memoria":  proceso.memoria_requerida,
            "prioridad": proceso.prioridad.name,
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
    
    # Incluir proceso en ejecución en la lista de procesos mostrada
    procesos_ui = []
    if not kernel.cpu.esta_libre:
        p = kernel.cpu.proceso_actual
        procesos_ui.append({
            "pid":      p.pid,
            "nombre":   p.nombre,
            "estado":   "EJECUTANDO",
            "prioridad": p.prioridad.name,
            "memoria":  p.memoria_requerida,
        })
    for p_data in estado["procesos_en_cola"]:
        # Buscar el objeto proceso para obtener más datos
        p_obj = next(
            (x for x in kernel.cola_procesos if x.pid == p_data["pid"]),
            None
        )
        procesos_ui.append({
            "pid":      p_data["pid"],
            "nombre":   p_data["nombre"],
            "estado":   p_data["estado"],
            "prioridad": p_obj.prioridad.name if p_obj else "MEDIA",
            "memoria":  p_obj.memoria_requerida if p_obj else 0,
        })

    # Log incremental
    client_offset = int(request.args.get("log_offset", 0))
    todas = kernel.log
    nuevas = _serializar_log(todas[client_offset:])
    nuevo_offset = len(todas)

    return jsonify({
        "ok":          True,
        "activo":      kernel.activo,
        "ciclo":       kernel.ciclo_reloj,
        "cpu":         estado["cpu"],
        "memoria":     estado["memoria"],
        "procesos":    procesos_ui,
        "dispositivos": estado["dispositivos"],
        "log_nuevas":  nuevas,
        "log_offset":  nuevo_offset,
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
    print("║   Aethelred OS — Servidor Flask           ║")
    print("║   http://localhost:5000                   ║")
    print("╚══════════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
