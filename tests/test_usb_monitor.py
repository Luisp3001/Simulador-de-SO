"""Pruebas del módulo de dispositivos USB (WMI simulado con objetos falsos, sysfs falso y backend simulado)."""

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from os_simulator.hardware.usb import (
    BackendSimulado, BackendSysfs, BackendWMI, MonitorUSB, clasificar, crear_backend, fecha_wmi,
)


class FakeWMI:
    """Imita lo mínimo del módulo ``wmi`` para probar la lógica de BackendWMI sin Windows."""
    class x_wmi_timed_out(Exception):
        pass

    def __init__(self, ents, discos, drivers):
        self.ents, self.discos, self.drivers = ents, discos, drivers
        self.consultas: list[str] = []
        self.eventos_pendientes = 0          # eventos que el watcher entregará antes de agotar el tiempo
        outer = self

        def _watcher(timeout_ms=-1):
            if outer.eventos_pendientes > 0:
                outer.eventos_pendientes -= 1
                return NS()
            raise outer.x_wmi_timed_out()
        self.watcher = _watcher

        class _C:
            def query(self, wql):
                outer.consultas.append(wql)
                if "FROM Win32_PnPEntity" in wql:
                    return outer.ents
                if "FROM Win32_DiskDrive" in wql:
                    return outer.discos
                if "FROM Win32_PnPSignedDriver" in wql:
                    raise AssertionError("Win32_PnPSignedDriver es lenta: no debe usarse en el camino crítico")
                raise AssertionError(wql)

            def watch_for(self, raw_wql):
                assert "Win32_DeviceChangeEvent" in raw_wql
                return outer.watcher
        self.WMI = _C


class FakePythonCom:
    def __init__(self):
        self.llamadas = []

    def CoInitialize(self):
        self.llamadas.append("init")

    def CoUninitialize(self):
        self.llamadas.append("uninit")


MOUSE = r"USB\VID_046D&PID_C077\6&2A3B4C&0&2"
FLASH = r"USB\VID_0951&PID_1666\60A44C4136E4F1A0F100001A"
DISCO = r"USBSTOR\DISK&VEN_KINGSTON&PROD_DATATRAVELER_3.0&REV_PMAP\60A44C4136E4F1A0F100001A&0"


def _wmi_falso():
    ents = [
        NS(PNPDeviceID=r"USB\ROOT_HUB30\4&1&0", Name="Concentrador raíz", PNPClass="USB", Service="USBHUB3", Manufacturer="MS", ConfigManagerErrorCode=0),
        NS(PNPDeviceID=MOUSE, Name="Dispositivo de entrada USB", PNPClass="HIDClass", Service="HidUsb", Manufacturer="(Estándar)", ConfigManagerErrorCode=0),
        NS(PNPDeviceID=r"HID\VID_046D&PID_C077\7&1&0&0000", Name="Mouse compatible con HID", PNPClass="Mouse", Service="mouhid", Manufacturer="Microsoft", ConfigManagerErrorCode=0),
        NS(PNPDeviceID=FLASH, Name="Dispositivo de almacenamiento masivo USB", PNPClass="USB", Service="USBSTOR", Manufacturer="Compatible", ConfigManagerErrorCode=0),
        NS(PNPDeviceID=r"PCI\VEN_8086&DEV_1234\3&0", Name="No es USB", PNPClass="System", Service="x", Manufacturer="x", ConfigManagerErrorCode=0),
    ]
    discos = [NS(PNPDeviceID=DISCO, Model="Kingston DataTraveler 3.0 USB Device", Size="32000000000", Service="disk")]
    drivers = {
        MOUSE: {"servicio": "HidUsb", "proveedor": "Microsoft", "version": "10.0.19041.1", "fecha": "21/06/2006", "inf": "input.inf", "descripcion": "Dispositivo de entrada USB"},
        r"HID\VID_046D&PID_C077\7&1&0&0000": {"servicio": "mouhid", "proveedor": "Microsoft", "version": "10.0.19041.2", "fecha": "21/06/2006", "inf": "msmouse.inf", "descripcion": "Mouse HID"},
        FLASH: {"servicio": "USBSTOR", "proveedor": "Microsoft", "version": "10.0.19041.1", "fecha": "21/06/2006", "inf": "usbstor.inf", "descripcion": "USB Mass Storage"},
        DISCO: {"servicio": "disk", "proveedor": "Microsoft", "version": "10.0.19041.1", "fecha": "21/06/2006", "inf": "disk.inf", "descripcion": "Disco"},
    }
    return FakeWMI(ents, discos, drivers)


def _backend(fake, com, registro=None):
    reg = registro or (lambda pid: fake.drivers.get(pid))
    return BackendWMI(wmi=fake, pythoncom=com, registro=reg)


class BackendWMITests(unittest.TestCase):
    def test_lista_solo_dispositivos_usb_con_su_driver(self):
        com = FakePythonCom()
        b = _backend(_wmi_falso(), com)
        b.preparar()
        res = b.escanear()
        self.assertEqual(com.llamadas, ["init"])             # pywin32: COM inicializado en el hilo
        self.assertEqual(set(res), {MOUSE, FLASH})           # sin root hub ni dispositivos no USB
        mouse = res[MOUSE]
        self.assertEqual((mouse["tipo"], mouse["vid"], mouse["pid"]), ("mouse", "046D", "C077"))
        self.assertEqual(mouse["driver"]["nombre"], "HidUsb")
        self.assertEqual(mouse["driver"]["proveedor"], "Microsoft")
        self.assertEqual(mouse["driver"]["version"], "10.0.19041.1")
        self.assertEqual(mouse["driver"]["fecha"], "21/06/2006")
        self.assertEqual(mouse["driver"]["inf"], "input.inf")
        self.assertEqual(mouse["interfaces"][0]["driver"]["nombre"], "mouhid")
        flash = res[FLASH]
        self.assertEqual(flash["tipo"], "almacenamiento")
        self.assertEqual(flash["nombre"], "Kingston DataTraveler 3.0 USB Device")
        self.assertEqual(flash["detalle"], "32.0 GB")
        b.cerrar()
        self.assertEqual(com.llamadas, ["init", "uninit"])

    def test_espera_cambio_usa_el_evento_y_devuelve_false_al_agotar_el_tiempo(self):
        b = _backend(_wmi_falso(), FakePythonCom())
        b.preparar()
        self.assertFalse(b.esperar_cambio(0.01))             # x_wmi_timed_out → sin cambios


    def test_consulta_pnp_es_filtrada_y_no_usa_signed_driver(self):
        fake = _wmi_falso()
        b = _backend(fake, FakePythonCom())
        b.preparar()
        b.escanear()
        pnp = [q for q in fake.consultas if "Win32_PnPEntity" in q][0]
        self.assertIn("LIKE", pnp)                       # no trae todos los dispositivos del equipo
        self.assertNotIn("SELECT *", pnp)                # solo las columnas necesarias
        self.assertFalse(any("PnPSignedDriver" in q for q in fake.consultas))

    def test_no_consulta_discos_si_no_hay_almacenamiento(self):
        fake = _wmi_falso()
        fake.ents = [e for e in fake.ents if e.PNPDeviceID != FLASH]
        b = _backend(fake, FakePythonCom())
        b.preparar()
        b.escanear()
        self.assertFalse(any("Win32_DiskDrive" in q for q in fake.consultas))

    def test_driver_incompleto_no_se_guarda_y_se_completa_en_el_repaso(self):
        fake = _wmi_falso()
        estado = {"listo": False}
        reg = lambda pid: (fake.drivers.get(pid) if estado["listo"] else None)   # Windows aún no enlazó el driver
        b = _backend(fake, FakePythonCom(), registro=reg)
        b.preparar()
        self.assertIsNone(b.escanear()[MOUSE]["driver"]["version"])
        estado["listo"] = True
        self.assertEqual(b.escanear()[MOUSE]["driver"]["version"], "10.0.19041.1")

    def test_rafaga_de_eventos_se_agrupa_en_un_solo_aviso(self):
        fake = _wmi_falso()
        fake.eventos_pendientes = 5                      # Windows manda varios eventos por un solo USB
        b = _backend(fake, FakePythonCom())
        b.preparar()
        self.assertTrue(b.esperar_cambio(0.01))
        self.assertEqual(fake.eventos_pendientes, 0)     # todos consumidos en la misma espera
        self.assertFalse(b.esperar_cambio(0.01))         # y la siguiente espera ya no tiene nada


class ClasificacionTests(unittest.TestCase):
    def test_tipos(self):
        self.assertEqual(clasificar("HidUsb", {"Mouse"}), "mouse")
        self.assertEqual(clasificar("HidUsb", {"Keyboard"}), "teclado")
        self.assertEqual(clasificar("USBSTOR", {"USB"}), "almacenamiento")
        self.assertEqual(clasificar("usbaudio2", set()), "audio")
        self.assertEqual(clasificar(None, {"Monitor"}), "pantalla")
        self.assertEqual(clasificar("USBHUB3", {"USB"}), "concentrador")
        self.assertEqual(clasificar(None, set()), "usb")

    def test_fecha_wmi(self):
        self.assertEqual(fecha_wmi("20190618000000.******+***"), "18/06/2019")
        self.assertIsNone(fecha_wmi(None))


class SysfsTests(unittest.TestCase):
    def test_lee_dispositivo_e_interfaz_con_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "usb1").mkdir()                            # root hub: se ignora
            dev = raiz / "1-2"
            dev.mkdir()
            for nombre, valor in (("idVendor", "046d"), ("idProduct", "c077"), ("product", "USB Optical Mouse"),
                                  ("manufacturer", "Logitech"), ("version", " 2.00"), ("speed", "1.5")):
                (dev / nombre).write_text(valor + "\n")
            itf = raiz / "1-2:1.0"
            itf.mkdir()
            (itf / "bInterfaceClass").write_text("03\n")
            (itf / "bInterfaceProtocol").write_text("02\n")
            (itf / "driver").symlink_to("/sys/bus/usb/drivers/usbhid")
            # el escaneo busca "<dev>:*" dentro del directorio del dispositivo
            (dev / "1-2:1.0").symlink_to(itf)
            res = BackendSysfs(raiz).escanear()
            self.assertEqual(list(res), ["1-2"])
            d = res["1-2"]
            self.assertEqual((d["tipo"], d["vid"], d["nombre"]), ("mouse", "046D", "USB Optical Mouse"))
            self.assertEqual(d["interfaces"][0]["driver"]["nombre"], "usbhid")


def _esperar(cond, t=3.0):
    fin = time.time() + t
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.02)
    return False


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.backend = BackendSimulado()
        self.m = MonitorUSB(self.backend)
        self.m.iniciar()
        self.assertTrue(_esperar(lambda: self.m.estado()["listo"]))

    def tearDown(self):
        self.m.detener()

    def test_inicia_vacio(self):
        e = self.m.estado()
        self.assertEqual(e["dispositivos"], [])
        self.assertEqual(e["eventos"], [])

    def test_actualiza_solo_al_conectar_y_desconectar(self):
        v0 = self.m.estado()["version"]
        did = self.backend.conectar("memoria")
        self.assertTrue(_esperar(lambda: len(self.m.estado()["dispositivos"]) == 1))
        e = self.m.estado()
        self.assertGreater(e["version"], v0)
        self.assertEqual(e["dispositivos"][0]["driver"]["nombre"], "USBSTOR")
        self.assertFalse(e["dispositivos"][0]["preexistente"])
        self.assertEqual(e["eventos"][0]["accion"], "conectado")
        self.backend.desconectar(did)
        self.assertTrue(_esperar(lambda: self.m.estado()["dispositivos"] == []))
        self.assertEqual(self.m.estado()["eventos"][0]["accion"], "desconectado")

    def test_dispositivos_ya_conectados_al_iniciar_quedan_marcados(self):
        self.m.detener()
        b = BackendSimulado()
        b.conectar("mouse")
        m = MonitorUSB(b)
        m.iniciar()
        try:
            self.assertTrue(_esperar(lambda: m.estado()["listo"]))
            self.assertTrue(m.estado()["dispositivos"][0]["preexistente"])
            self.assertEqual(m.estado()["eventos"], [])        # no se anuncian como «conectado»
        finally:
            m.detener()

    def test_backend_no_disponible_informa_el_error(self):
        from os_simulator.hardware.usb import BackendNoDisponible
        m = MonitorUSB(BackendNoDisponible("WMI", "Faltan librerías"))
        m.iniciar()
        self.assertTrue(_esperar(lambda: m.estado()["listo"]))
        self.assertIn("Faltan", m.estado()["error"])
        m.detener()

    def test_crear_backend_sim(self):
        self.assertTrue(crear_backend("sim").simulado)


if __name__ == "__main__":
    unittest.main()
