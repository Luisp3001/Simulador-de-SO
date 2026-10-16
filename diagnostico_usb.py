"""Mide cuánto tarda cada consulta de WMI/registro y cuántos eventos llegan por cada USB (solo Windows).

    uv run python diagnostico_usb.py
Conecta y desconecta un USB mientras corre (20 s) y copia la salida completa.
"""
import sys
import time

if sys.platform != "win32":
    sys.exit("Este diagnóstico es solo para Windows.")

import pythoncom
import wmi

from os_simulator.hardware.usb import BackendWMI, registro_windows


def medir(titulo, fn):
    t = time.perf_counter()
    try:
        r = fn()
        n = len(r) if hasattr(r, "__len__") else ""
        print(f"{time.perf_counter() - t:6.2f} s  {titulo}  {n}")
        return r
    except Exception as exc:
        print(f"{time.perf_counter() - t:6.2f} s  {titulo}  ERROR: {exc}")


pythoncom.CoInitialize()
c = medir("conectar a WMI", wmi.WMI)
medir("Win32_PnPEntity completa (SELECT *)  [forma anterior]", lambda: list(c.query("SELECT * FROM Win32_PnPEntity")))
nodos = medir("Win32_PnPEntity filtrada      [forma nueva]", lambda: list(c.query(BackendWMI._SQL_PNP)))
medir("Win32_DiskDrive USB", lambda: list(c.query("SELECT PNPDeviceID, Model, Size FROM Win32_DiskDrive WHERE InterfaceType = 'USB'")))
usb = [e for e in (nodos or []) if str(e.PNPDeviceID).upper().startswith("USB\\VID_") and "&MI_" not in str(e.PNPDeviceID).upper()]
if usb:
    did = usb[0].PNPDeviceID.replace("\\", "\\\\")
    medir("Win32_PnPSignedDriver (1 dispositivo)  [forma anterior]",
          lambda: list(c.query(f"SELECT * FROM Win32_PnPSignedDriver WHERE DeviceID = '{did}'")))
    medir("driver por registro (1 dispositivo)    [forma nueva]", lambda: registro_windows(usb[0].PNPDeviceID) or {})

print("\nEscaneo completo como lo hace el simulador:")
b = BackendWMI()
b.preparar()
medir("escanear()", b.escanear)
print("   desglose:", b.detalle_tiempos)

print("\nEventos durante 20 s — conecta y desconecta un USB ahora...")
w = c.watch_for(raw_wql="SELECT * FROM Win32_DeviceChangeEvent WHERE EventType = 2 OR EventType = 3")
t0, fin = time.perf_counter(), time.perf_counter() + 20
while time.perf_counter() < fin:
    try:
        e = w(timeout_ms=500)
        print(f"{time.perf_counter() - t0:6.2f} s  evento tipo {e.EventType} (2 = conectado, 3 = desconectado)")
    except wmi.x_wmi_timed_out:
        pass
