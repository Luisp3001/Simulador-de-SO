"""Diagnóstico del módulo USB (solo Windows).

    python diagnostico_usb.py        (o: uv run python diagnostico_usb.py)

Prueba el método nativo (cfgmgr32), lista lo que ve y vigila 20 s los cambios:
conecta y desconecta un USB mientras corre y copia TODA la salida.
"""
import platform
import sys
import time
import traceback

print(f"Windows: {platform.platform()} · Python {platform.python_version()} · {platform.architecture()[0]}")
if sys.platform != "win32":
    sys.exit("Este diagnóstico es solo para Windows.")

from os_simulator.hardware.usb import BackendCfgMgr, _CfgMgr

print("\n[1] cfgmgr32: IDs presentes en el bus USB")
try:
    t = time.perf_counter()
    ids = _CfgMgr().ids_presentes("USB")
    print(f"    {len(ids)} IDs en {(time.perf_counter() - t) * 1000:.1f} ms")
    for i in ids:
        print("     ", i)
except Exception:
    print("    ERROR (esto es lo que hay que mandar):")
    traceback.print_exc()
    sys.exit(1)

print("\n[2] Escaneo completo (nombre, tipo, driver)")
try:
    b = BackendCfgMgr()
    t = time.perf_counter()
    res = b.escanear()
    print(f"    {len(res)} dispositivos en {(time.perf_counter() - t) * 1000:.0f} ms ({b.detalle_tiempos})")
    for d in res.values():
        drv = d["driver"]
        print(f"     {d['icono']} {d['nombre']}  [{d['tipo_nombre']}]  {d['vid']}:{d['pid']}  fab={d['fabricante']}")
        print(f"          driver={drv['nombre']}  proveedor={drv['proveedor']}  versión={drv['version']}  fecha={drv['fecha']}  inf={drv['inf']}")
        for i in d["interfaces"]:
            print(f"          └ {i['nombre']} ({i['clase']}) → {i['driver']['nombre']} {i['driver']['version']}")
except Exception:
    print("    ERROR (esto es lo que hay que mandar):")
    traceback.print_exc()
    sys.exit(1)

print("\n[3] Vigilando cambios 20 s — conecta y desconecta un USB ahora...")
t0 = time.perf_counter()
while time.perf_counter() - t0 < 20:
    if b.esperar_cambio(1.0):
        nuevos = b.escanear()
        print(f"    {time.perf_counter() - t0:5.1f} s  cambio detectado → {len(nuevos)} dispositivos")
print("\nListo.")
