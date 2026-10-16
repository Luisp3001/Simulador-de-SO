"""Dispositivos de E/S USB con actualización automática.

Un ``MonitorUSB`` corre en un hilo, mantiene el listado de dispositivos USB
conectados y la información del driver ligado a cada uno. Detecta
conexiones y desconexiones sin intervención del usuario.

Orígenes de datos (``crear_backend``):

* ``BackendWMI``   → Windows. Usa **WMI** (Win32_PnPEntity, Win32_DiskDrive) para listar
  los dispositivos y **pywin32** (``pythoncom``) para inicializar COM en el hilo. El driver
  se lee del registro de Windows (milisegundos): Win32_PnPSignedDriver tarda decenas de
  segundos aunque se filtre, así que NO se usa en el camino crítico.
  Los cambios se detectan por evento (Win32_DeviceChangeEvent), sin sondeo.
* ``BackendSysfs`` → Linux (lee /sys/bus/usb/devices).
* ``BackendSimulado`` → equipos sin USB accesible: permite conectar y
  desconectar dispositivos de prueba para demostrar el módulo.
"""

from __future__ import annotations

import os
import platform
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

TIPOS = {
    "mouse": ("Mouse", "🖱️"),
    "teclado": ("Teclado", "⌨️"),
    "almacenamiento": ("Memoria USB / almacenamiento", "💾"),
    "audio": ("Audio (parlantes / audífonos)", "🔊"),
    "camara": ("Cámara", "📷"),
    "impresora": ("Impresora", "🖨️"),
    "pantalla": ("Pantalla / proyector", "📽️"),
    "bluetooth": ("Bluetooth", "📶"),
    "concentrador": ("Concentrador USB", "🔀"),
    "hid": ("Dispositivo HID", "🎮"),
    "usb": ("Dispositivo USB", "🔌"),
}

_VID_PID = re.compile(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", re.I)


def clasificar(servicio: str | None, clases: set[str]) -> str:
    """Tipo de dispositivo a partir del servicio (driver) y las clases PnP relacionadas."""
    s = (servicio or "").lower()
    c = {x.lower() for x in clases if x}
    if "mouse" in c:
        return "mouse"
    if "keyboard" in c:
        return "teclado"
    if s in ("usbstor", "uaspstor") or c & {"diskdrive", "wpd", "cdrom", "scsiadapter"}:
        return "almacenamiento"
    if s.startswith("usbaudio") or c & {"media", "audioendpoint"}:
        return "audio"
    if s == "usbvideo" or c & {"camera", "image"}:
        return "camara"
    if s == "usbprint" or "printer" in c:
        return "impresora"
    if c & {"monitor", "display"}:
        return "pantalla"
    if s == "bthusb" or "bluetooth" in c:
        return "bluetooth"
    if s.startswith("usbhub"):
        return "concentrador"
    if "hidclass" in c or s == "hidusb":
        return "hid"
    return "usb"


def _tipo(clave: str) -> dict:
    etiqueta, icono = TIPOS[clave]
    return {"tipo": clave, "tipo_nombre": etiqueta, "icono": icono}


def driver_info(nombre=None, proveedor=None, version=None, fecha=None, inf=None,
                firmado=None, firmante=None, clase=None, descripcion=None) -> dict:
    return {"nombre": nombre, "proveedor": proveedor, "version": version, "fecha": fecha,
            "inf": inf, "firmado": firmado, "firmante": firmante, "clase": clase,
            "descripcion": descripcion}


def fecha_wmi(valor) -> str | None:
    """'20190618000000.******+***' → '18/06/2019'."""
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", str(valor or ""))
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else None


def fecha_registro(valor) -> str | None:
    """Registro de Windows guarda 'm-d-yyyy' ('6-21-2006') → '21/06/2006'."""
    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", str(valor or "").strip())
    return f"{int(m.group(2)):02d}/{int(m.group(1)):02d}/{m.group(3)}" if m else None


def registro_windows(pnp_id: str) -> dict | None:
    """Driver ligado a un nodo PnP, leído de HKLM\\SYSTEM\\CurrentControlSet (rápido)."""
    try:
        import winreg
    except ImportError:
        return None
    acceso = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            "SYSTEM\\CurrentControlSet\\Enum\\" + pnp_id, 0, acceso) as k:
            clase_drv = winreg.QueryValueEx(k, "Driver")[0]
            try:
                servicio = winreg.QueryValueEx(k, "Service")[0]
            except OSError:
                servicio = None
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            "SYSTEM\\CurrentControlSet\\Control\\Class\\" + clase_drv, 0, acceso) as k:
            def v(nombre):
                try:
                    return str(winreg.QueryValueEx(k, nombre)[0])
                except OSError:
                    return None
            return {"servicio": servicio, "proveedor": v("ProviderName"), "version": v("DriverVersion"),
                    "fecha": fecha_registro(v("DriverDate")), "inf": v("InfPath"),
                    "descripcion": v("DriverDesc")}
    except OSError:
        return None


def _wql(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("'", "\\'")


# ═══════════════════════════ Windows: WMI + pywin32 ═══════════════════════════
class BackendWMI:
    nombre = "WMI + pywin32 (Windows)"
    simulado = False
    espera_tras_evento = 0.0
    # Windows termina de enlazar el driver unos segundos después de la conexión:
    # se repasa (barato) para completar la información sin esperar al sondeo periódico.
    repasos = (1.5, 4.0)

    _SQL_PNP = ("SELECT PNPDeviceID, Name, Manufacturer, PNPClass, Service, ConfigManagerErrorCode "
                "FROM Win32_PnPEntity WHERE PNPDeviceID LIKE 'USB\\\\%' OR PNPDeviceID LIKE 'HID\\\\VID%'")

    def __init__(self, wmi=None, pythoncom=None, registro="auto") -> None:
        if wmi is None:
            import wmi  # type: ignore
        if pythoncom is None:
            import pythoncom  # type: ignore  (pywin32)
        self._wmi, self._pythoncom = wmi, pythoncom
        # registro: función pnp_id → datos del driver (rápida). None → se usa Win32_PnPSignedDriver (lenta).
        self._registro = registro_windows if registro == "auto" else registro
        self._c = None
        self._watcher = None
        self._cache: dict[str, dict] = {}   # driver por nodo PnP (solo si la información está completa)
        self.detalle_tiempos: str = ""

    def preparar(self) -> None:
        self._pythoncom.CoInitialize()      # COM debe inicializarse en el hilo que usa WMI
        self._c = self._wmi.WMI()
        try:
            self._watcher = self._c.watch_for(
                raw_wql="SELECT * FROM Win32_DeviceChangeEvent WHERE EventType = 2 OR EventType = 3")
        except Exception:                   # sin eventos: se sondea
            self._watcher = None
        if self._watcher is None:
            self.repasos = ()

    def cerrar(self) -> None:
        try:
            self._pythoncom.CoUninitialize()
        except Exception:
            pass

    def esperar_cambio(self, timeout: float) -> bool:
        if self._watcher is None:
            time.sleep(min(timeout, 2.0))
            return True
        try:
            self._watcher(timeout_ms=int(timeout * 1000))
        except self._wmi.x_wmi_timed_out:
            return False
        except Exception:
            self._watcher = None
            self.repasos = ()
            return True
        # Conectar o quitar un USB dispara una ráfaga de eventos (uno por nodo y volumen):
        # se agrupan hasta que haya 0.3 s de calma para hacer UN solo escaneo.
        fin = time.monotonic() + 2.0
        while time.monotonic() < fin:
            try:
                self._watcher(timeout_ms=300)
            except self._wmi.x_wmi_timed_out:
                break
            except Exception:
                self._watcher = None
                self.repasos = ()
                break
        return True

    # ── lectura ──────────────────────────────────────────────────────────
    def _driver_de(self, pnp_id: str, servicio: str | None) -> dict:
        if pnp_id in self._cache:
            return self._cache[pnp_id]
        if self._registro is not None:
            datos = self._registro(pnp_id) or {}
            info = driver_info(nombre=servicio or datos.get("servicio"), proveedor=datos.get("proveedor"),
                               version=datos.get("version"), fecha=datos.get("fecha"), inf=datos.get("inf"),
                               descripcion=datos.get("descripcion"))
            if info["version"] or info["proveedor"]:      # completo → se guarda; si no, se reintenta
                self._cache[pnp_id] = info
            return info
        # Sin registro (solo desarrollo): Win32_PnPSignedDriver. LENTA (decenas de segundos).
        info = driver_info(nombre=servicio)
        try:
            filas = list(self._c.query(
                f"SELECT * FROM Win32_PnPSignedDriver WHERE DeviceID = '{_wql(pnp_id)}'"))
            if filas:
                f = filas[0]
                g = lambda a: getattr(f, a, None)
                info = driver_info(
                    nombre=servicio or g("DriverName"), proveedor=g("DriverProviderName"),
                    version=g("DriverVersion"), fecha=fecha_wmi(g("DriverDate")), inf=g("InfName"),
                    firmado=g("IsSigned"), firmante=g("Signer"), clase=g("DeviceClass"),
                    descripcion=g("Description"))
                self._cache[pnp_id] = info
        except Exception:
            pass
        return info

    def _entidades(self) -> list:
        try:
            return list(self._c.query(self._SQL_PNP))     # filtrada y con pocas columnas: mucho más rápida
        except Exception:
            return list(self._c.query("SELECT * FROM Win32_PnPEntity"))

    def escanear(self) -> dict[str, dict]:
        t0 = time.perf_counter()
        ents = self._entidades()
        t1 = time.perf_counter()

        def pid_(e) -> str:
            return str(getattr(e, "PNPDeviceID", "") or "")

        nodos = [e for e in ents
                 if pid_(e).upper().startswith("USB\\VID_") and "&MI_" not in pid_(e).upper()]
        discos: list = []
        if any(str(getattr(e, "Service", "") or "").lower() in ("usbstor", "uaspstor") for e in nodos):
            try:
                discos = list(self._c.query(
                    "SELECT PNPDeviceID, Model, Size FROM Win32_DiskDrive WHERE InterfaceType = 'USB'"))
            except Exception:
                discos = []
        t2 = time.perf_counter()

        repetidos: dict[str, int] = {}
        for e in nodos:
            m = _VID_PID.search(pid_(e))
            if m:
                k = f"{m.group(1)}:{m.group(2)}".upper()
                repetidos[k] = repetidos.get(k, 0) + 1

        resultado: dict[str, dict] = {}
        vistos: set[str] = set()
        for e in nodos:
            did = pid_(e)
            m = _VID_PID.search(did)
            vid, pid = (m.group(1).upper(), m.group(2).upper()) if m else (None, None)
            servicio = getattr(e, "Service", None)
            clases = {getattr(e, "PNPClass", None) or ""}
            nombre = getattr(e, "Name", None) or "Dispositivo USB"
            detalle = None
            interfaces: list[dict] = []
            vistos.add(did)

            # Interfaces hijas (MI_xx / HID\VID_...) — solo si el VID:PID es único
            if vid and repetidos.get(f"{vid}:{pid}") == 1:
                clave = f"VID_{vid}&PID_{pid}"
                for h in ents:
                    hid = pid_(h)
                    u = hid.upper()
                    if hid != did and clave in u and (u.startswith("USB\\") or u.startswith("HID\\")):
                        clases.add(getattr(h, "PNPClass", None) or "")
                        vistos.add(hid)
                        interfaces.append({
                            "nombre": getattr(h, "Name", None) or hid,
                            "clase": getattr(h, "PNPClass", None),
                            "driver": self._driver_de(hid, getattr(h, "Service", None)),
                        })

            # Memorias USB: el disco se enlaza por el número de serie
            serie = did.split("\\")[-1]
            for d in discos:
                ult = pid_(d).split("\\")[-1].rsplit("&", 1)[0]
                if serie and ult.upper() == serie.upper():
                    clases.add("DiskDrive")
                    nombre = getattr(d, "Model", None) or nombre
                    tam = getattr(d, "Size", None)
                    if tam:
                        detalle = f"{int(tam) / 1e9:.1f} GB"
                    vistos.add(pid_(d))
                    interfaces.append({
                        "nombre": getattr(d, "Model", None) or pid_(d), "clase": "DiskDrive",
                        "driver": self._driver_de(pid_(d), "disk")})

            code = getattr(e, "ConfigManagerErrorCode", 0) or 0
            resultado[did] = {
                "id": did, "nombre": nombre,
                "fabricante": getattr(e, "Manufacturer", None),
                **_tipo(clasificar(servicio, clases)),
                "vid": vid, "pid": pid, "serie": serie if "&" not in serie else None,
                "estado": "Funcionando correctamente" if code == 0 else f"Error de dispositivo (código {code})",
                "detalle": detalle,
                "driver": self._driver_de(did, servicio),
                "interfaces": interfaces,
            }
        self._cache = {k: v for k, v in self._cache.items() if k in vistos}
        t3 = time.perf_counter()
        self.detalle_tiempos = (f"PnP {t1 - t0:.2f}s · discos {t2 - t1:.2f}s · drivers {t3 - t2:.2f}s")
        return resultado


# ════════════════════════════════ Linux: sysfs ════════════════════════════════
class BackendSysfs:
    nombre = "sysfs (Linux)"
    simulado = False
    espera_tras_evento = 0.0

    def __init__(self, raiz: str | os.PathLike = "/sys/bus/usb/devices") -> None:
        self.raiz = Path(raiz)

    def preparar(self) -> None:
        pass

    def cerrar(self) -> None:
        pass

    def esperar_cambio(self, timeout: float) -> bool:
        time.sleep(min(timeout, 1.5))       # sondeo liviano (lectura de archivos pequeños)
        return True

    @staticmethod
    def _leer(ruta: Path) -> str | None:
        try:
            return ruta.read_text(encoding="utf-8", errors="replace").strip() or None
        except OSError:
            return None

    def _driver_de(self, ruta: Path) -> dict:
        try:
            nombre = os.path.basename(os.readlink(ruta / "driver"))
        except OSError:
            return driver_info(nombre="(sin driver enlazado)")
        mod = Path("/sys/module") / nombre.replace("-", "_")
        version = self._leer(mod / "version") or platform.release()
        return driver_info(nombre=nombre, proveedor="Kernel de Linux", version=version,
                           inf=str(mod) if mod.exists() else None, firmado=None)

    def escanear(self) -> dict[str, dict]:
        res: dict[str, dict] = {}
        if not self.raiz.is_dir():
            return res
        for dev in sorted(self.raiz.iterdir()):
            if ":" in dev.name or dev.name.startswith("usb"):      # interfaces y root hubs
                continue
            vid, pid = self._leer(dev / "idVendor"), self._leer(dev / "idProduct")
            if not vid:
                continue
            clases, servicio, interfaces = set(), None, []
            for itf in sorted(dev.glob(f"{dev.name}:*")):
                cls, proto = self._leer(itf / "bInterfaceClass"), self._leer(itf / "bInterfaceProtocol")
                drv = self._driver_de(itf)
                servicio = servicio or drv["nombre"]
                if cls == "03":
                    clases.add({"01": "Keyboard", "02": "Mouse"}.get(proto or "", "HIDClass"))
                elif cls == "08":
                    clases.add("DiskDrive")
                elif cls == "01":
                    clases.add("Media")
                elif cls == "0e":
                    clases.add("Camera")
                elif cls == "07":
                    clases.add("Printer")
                elif cls == "09":
                    servicio = "usbhub"
                elif cls == "e0":
                    clases.add("Bluetooth")
                interfaces.append({"nombre": f"Interfaz {itf.name.split(':')[-1]}",
                                   "clase": cls, "driver": drv})
            nombre = self._leer(dev / "product") or f"USB {vid}:{pid}"
            res[dev.name] = {
                "id": dev.name, "nombre": nombre, "fabricante": self._leer(dev / "manufacturer"),
                **_tipo(clasificar(servicio, clases)),
                "vid": vid.upper(), "pid": (pid or "").upper(), "serie": self._leer(dev / "serial"),
                "estado": "Funcionando correctamente",
                "detalle": f"USB {self._leer(dev / 'version') or '?'} · {self._leer(dev / 'speed') or '?'} Mb/s",
                "driver": self._driver_de(dev), "interfaces": interfaces,
            }
        return res


# ═══════════════════════════════ Simulado ═══════════════════════════════════
_MS = "Microsoft"
CATALOGO_SIM = {
    "mouse": dict(nombre="USB Optical Mouse", fab="Logitech", tipo="mouse", vid="046D", pid="C077",
                  driver=("HidUsb", _MS, "10.0.19041.1", "21/06/2006", "input.inf"),
                  itf=[("Mouse compatible con HID", "Mouse", ("mouhid", _MS, "10.0.19041.1", "21/06/2006", "msmouse.inf"))]),
    "teclado": dict(nombre="USB Keyboard", fab="Genius", tipo="teclado", vid="0458", pid="0186",
                    driver=("HidUsb", _MS, "10.0.19041.1", "21/06/2006", "input.inf"),
                    itf=[("Teclado HID", "Keyboard", ("kbdhid", _MS, "10.0.19041.1", "21/06/2006", "keyboard.inf"))]),
    "memoria": dict(nombre="Kingston DataTraveler 3.0", fab="Kingston", tipo="almacenamiento", vid="0951", pid="1666",
                    detalle="29.8 GB", driver=("USBSTOR", _MS, "10.0.19041.1", "21/06/2006", "usbstor.inf"),
                    itf=[("Kingston DataTraveler 3.0 USB Device", "DiskDrive", ("disk", _MS, "10.0.19041.1", "21/06/2006", "disk.inf"))]),
    "parlantes": dict(nombre="USB Audio Device (parlantes)", fab="C-Media", tipo="audio", vid="0D8C", pid="0014",
                      driver=("usbaudio", _MS, "10.0.19041.1", "21/06/2006", "wdma_usb.inf"),
                      itf=[("Altavoces (USB Audio Device)", "AudioEndpoint", ("usbaudio", _MS, "10.0.19041.1", "21/06/2006", "wdma_usb.inf"))]),
    "audifonos": dict(nombre="USB Headset (audífonos)", fab="Logitech", tipo="audio", vid="046D", pid="0A38",
                      driver=("usbaudio2", _MS, "10.0.19041.1", "21/06/2006", "usbaudio2.inf"),
                      itf=[("Auriculares (USB Headset)", "AudioEndpoint", ("usbaudio2", _MS, "10.0.19041.1", "21/06/2006", "usbaudio2.inf"))]),
    "proyector": dict(nombre="EPSON Projector", fab="SEIKO EPSON", tipo="pantalla", vid="04B8", pid="0535",
                      driver=("usbvideo", _MS, "10.0.19041.1", "21/06/2006", "usbvideo.inf"),
                      itf=[("Monitor genérico PnP", "Monitor", ("monitor", _MS, "10.0.19041.1", "21/06/2006", "monitor.inf"))]),
}


class BackendSimulado:
    nombre = "Simulado (sin acceso a USB reales)"
    simulado = True
    espera_tras_evento = 0.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._evento = threading.Event()
        self._devs: dict[str, dict] = {}
        self._n = 0

    def preparar(self) -> None:
        pass

    def cerrar(self) -> None:
        pass

    def esperar_cambio(self, timeout: float) -> bool:
        if self._evento.wait(timeout):
            self._evento.clear()
            return True
        return False

    def catalogo(self) -> list[dict]:
        return [{"clave": k, "nombre": v["nombre"]} for k, v in CATALOGO_SIM.items()]

    def conectar(self, clave: str) -> str:
        m = CATALOGO_SIM[clave]                      # KeyError si no existe
        with self._lock:
            self._n += 1
            did = f"SIM\\VID_{m['vid']}&PID_{m['pid']}\\{self._n:04d}"
            mk = lambda t: driver_info(nombre=t[0], proveedor=t[1], version=t[2], fecha=t[3], inf=t[4],
                                       firmado=True, firmante="Microsoft Windows")
            self._devs[did] = {
                "id": did, "nombre": m["nombre"], "fabricante": m["fab"], **_tipo(m["tipo"]),
                "vid": m["vid"], "pid": m["pid"], "serie": f"{self._n:04d}",
                "estado": "Funcionando correctamente", "detalle": m.get("detalle"),
                "driver": mk(m["driver"]),
                "interfaces": [{"nombre": n, "clase": c, "driver": mk(d)} for n, c, d in m["itf"]],
            }
        self._evento.set()
        return did

    def desconectar(self, did: str) -> bool:
        with self._lock:
            ok = self._devs.pop(did, None) is not None
        self._evento.set()
        return ok

    def escanear(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._devs.items()}


class BackendNoDisponible:
    """Se usa cuando no se puede leer USB (p. ej. faltan wmi/pywin32)."""
    simulado = False
    espera_tras_evento = 0.0

    def __init__(self, nombre: str, mensaje: str) -> None:
        self.nombre, self.mensaje = nombre, mensaje

    def preparar(self) -> None:
        raise RuntimeError(self.mensaje)

    def cerrar(self) -> None:
        pass

    def esperar_cambio(self, timeout: float) -> bool:
        return False

    def escanear(self) -> dict:
        return {}


def crear_backend(modo: str = "auto"):
    modo = (modo or "auto").lower()
    if modo == "auto":
        if sys.platform == "win32":
            modo = "wmi"
        elif Path("/sys/bus/usb/devices").is_dir():
            modo = "sysfs"
        else:
            modo = "sim"
    if modo == "wmi":
        try:
            return BackendWMI()
        except ImportError:
            return BackendNoDisponible(
                "WMI + pywin32 (Windows)",
                "Faltan las librerías WMI y pywin32. Instálalas con «pip install wmi pywin32» "
                "(o «uv add wmi pywin32») y reinicia el servidor.")
    if modo == "sysfs":
        return BackendSysfs()
    return BackendSimulado()


# ═════════════════════════════════ Monitor ══════════════════════════════════
class MonitorUSB:
    """Mantiene el listado y avisa de conexiones/desconexiones (versión incremental)."""

    def __init__(self, backend) -> None:
        self.backend = backend
        self._lock = threading.RLock()
        self._scan_lock = threading.Lock()
        self._dispositivos: dict[str, dict] = {}
        self._eventos: list[dict] = []
        self._version = 0
        self._listo = False
        self._error: str | None = None
        self._stop = threading.Event()
        self._hilo: threading.Thread | None = None
        self._t_evento: float | None = None
        self._escaneo_s: float | None = None
        self._debug = os.environ.get("USB_DEBUG") == "1"

    @property
    def simulado(self) -> bool:
        return bool(getattr(self.backend, "simulado", False))

    def iniciar(self) -> None:
        if self._hilo and self._hilo.is_alive():
            return
        self._stop.clear()
        self._hilo = threading.Thread(target=self._bucle, name="monitor-usb", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._stop.set()
        if self._hilo:
            self._hilo.join(timeout=5)

    def sincronizar(self) -> None:
        """Escaneo inmediato (solo modo simulado; WMI debe usarse desde su propio hilo)."""
        self._escanear()

    def _escanear(self) -> None:
        with self._scan_lock:
            t0 = time.perf_counter()
            try:
                actuales = self.backend.escanear()
                self._error = None
            except Exception as exc:     # no tumbar el hilo por un fallo puntual
                self._error = f"No se pudo leer la lista de dispositivos USB: {exc}"
                return
            self._escaneo_s = time.perf_counter() - t0
            self._aplicar(actuales)
            if self._debug:
                lat = f" · evento→lista {time.monotonic() - self._t_evento:.2f}s" if self._t_evento else ""
                print(f"[usb] escaneo {self._escaneo_s:.2f}s ({getattr(self.backend, 'detalle_tiempos', '')}){lat}",
                      flush=True)

    def _bucle(self) -> None:
        try:
            self.backend.preparar()
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
                self._listo = True
                self._version += 1
            return
        try:
            self._escanear()
            pendientes: list[float] = []
            ultimo = time.monotonic()
            while not self._stop.is_set():
                evento = self.backend.esperar_cambio(1.0)
                ahora = time.monotonic()
                if evento:
                    self._t_evento = ahora
                    espera = getattr(self.backend, "espera_tras_evento", 0.0)
                    if espera:
                        time.sleep(espera)
                    self._escanear()
                    ultimo = time.monotonic()
                    # repasos baratos: completan drivers que Windows enlaza unos segundos después
                    pendientes = [ahora + r for r in getattr(self.backend, "repasos", ())]
                elif (pendientes and ahora >= pendientes[0]) or ahora - ultimo > 15:
                    if pendientes and ahora >= pendientes[0]:
                        pendientes.pop(0)
                    self._escanear()
                    ultimo = time.monotonic()
        finally:
            try:
                self.backend.cerrar()
            except Exception:
                pass

    def _aplicar(self, actuales: dict[str, dict]) -> None:
        ahora = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            primera = not self._listo
            cambios = primera
            for did, d in actuales.items():
                previo = self._dispositivos.get(did)
                if previo is None:
                    self._dispositivos[did] = {**d, "conectado_en": ahora, "preexistente": primera}
                    if not primera:
                        self._evento("conectado", d)
                    cambios = True
                else:
                    nuevo = {**d, "conectado_en": previo["conectado_en"], "preexistente": previo["preexistente"]}
                    if nuevo != previo:
                        self._dispositivos[did] = nuevo
                        cambios = True
            for did in [k for k in self._dispositivos if k not in actuales]:
                self._evento("desconectado", self._dispositivos.pop(did))
                cambios = True
            self._listo = True
            if cambios:
                self._version += 1

    def _evento(self, accion: str, d: dict) -> None:
        self._eventos.append({"hora": datetime.now().strftime("%H:%M:%S"), "accion": accion,
                              "nombre": d["nombre"], "icono": d["icono"], "tipo_nombre": d["tipo_nombre"]})
        del self._eventos[:-40]

    def estado(self) -> dict:
        with self._lock:
            datos = {
                "ok": True, "version": self._version, "listo": self._listo,
                "backend": self.backend.nombre, "simulado": self.simulado, "error": self._error,
                "escaneo_s": None if self._escaneo_s is None else round(self._escaneo_s, 2),
                "dispositivos": sorted(self._dispositivos.values(), key=lambda d: d["conectado_en"]),
                "eventos": list(reversed(self._eventos)),
            }
        if self.simulado:
            datos["catalogo"] = self.backend.catalogo()
        return datos
