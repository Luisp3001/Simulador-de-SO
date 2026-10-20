"""Pruebas del método nativo de Windows (cfgmgr32) sin necesitar Windows:
   1) la lógica de BackendCfgMgr con un árbol de dispositivos falso,
   2) el envoltorio ctypes (_CfgMgr) contra una DLL falsa."""

import ctypes
import unittest

from os_simulator.hardware.usb import BackendCfgMgr, MonitorUSB, _CfgMgr, clasificar_multi


class FakeCfg:
    """Árbol PnP: nodos = {devinst: dict(id, desc, friendly, servicio, clase, mfg, bus, problema, hijos=[devinst])}."""

    def __init__(self):
        self.nodos: dict[int, dict] = {}
        self.presentes: list[str] = []

    def agregar(self, devinst, did, hijos=(), **kw):
        self.nodos[devinst] = {"id": did, "hijos": list(hijos), "desc": None, "friendly": None, "servicio": None,
                               "clase": None, "mfg": None, "bus": None, "problema": 0, **kw}

    def ids_presentes(self, enumerador="USB"):
        return list(self.presentes)

    def nodo(self, did):
        return next((k for k, v in self.nodos.items() if v["id"] == did), None)

    def id_de(self, d):
        return self.nodos[d]["id"]

    def hijo(self, d):
        h = self.nodos[d]["hijos"]
        return h[0] if h else None

    def hermano(self, d):
        for v in self.nodos.values():
            if d in v["hijos"]:
                i = v["hijos"].index(d)
                return v["hijos"][i + 1] if i + 1 < len(v["hijos"]) else None
        return None

    def propiedad(self, d, prop):
        campo = {1: "desc", 5: "servicio", 8: "clase", 0xC: "mfg", 0xD: "friendly"}[prop]
        return self.nodos[d][campo]

    def propiedad_dev(self, d, guid, pid):
        return self.nodos[d]["bus"]

    def problema(self, d):
        return self.nodos[d]["problema"]


REG = {"proveedor": "Microsoft", "version": "10.0.22621.1", "fecha": "21/06/2006", "inf": "input.inf", "descripcion": "d"}
RUEDA = r"USB\VID_046D&PID_C077\AAA"
RUEDA2 = r"USB\VID_046D&PID_C077\BBB"
FLASH = r"USB\VID_0951&PID_1666\60A44C"
HEAD = r"USB\VID_046D&PID_0A38\CCC"


def _arbol():
    c = FakeCfg()
    # root hub (se ignora) y dos mouse idénticos (mismo VID:PID) con su hijo HID
    c.agregar(1, r"USB\ROOT_HUB30\4&1", servicio="USBHUB3", clase="USB")
    c.agregar(10, RUEDA, hijos=[11], servicio="HidUsb", clase="HIDClass", desc="Dispositivo de entrada USB", bus="USB Optical Mouse", mfg="(Estándar)")
    c.agregar(11, r"HID\VID_046D&PID_C077\7&1", servicio="mouhid", clase="Mouse", desc="Mouse compatible con HID")
    c.agregar(20, RUEDA2, hijos=[21], servicio="HidUsb", clase="HIDClass", desc="Dispositivo de entrada USB", bus="USB Optical Mouse")
    c.agregar(21, r"HID\VID_046D&PID_C077\7&2", servicio="mouhid", clase="Mouse", desc="Mouse compatible con HID")
    # memoria USB: nodo → USBSTOR → disco
    c.agregar(30, FLASH, hijos=[31], servicio="USBSTOR", clase="USB", desc="Dispositivo de almacenamiento masivo USB", bus="DataTraveler 3.0")
    c.agregar(31, r"USBSTOR\DISK&VEN_KINGSTON\60A44C&0", servicio="disk", clase="DiskDrive", friendly="Kingston DataTraveler 3.0 USB Device")
    # audífonos compuestos: nodo (usbccgp) → interfaz MI_00 (usbaudio, MEDIA) + MI_03 (HID)
    c.agregar(40, HEAD, hijos=[41, 42], servicio="usbccgp", clase="USB", desc="@usb.inf,%composite%;Dispositivo compuesto USB", bus="Logitech USB Headset")
    c.agregar(41, r"USB\VID_046D&PID_0A38&MI_00\8&1", servicio="usbaudio", clase="MEDIA", desc="Dispositivo de audio USB")
    c.agregar(42, r"USB\VID_046D&PID_0A38&MI_03\8&2", servicio="HidUsb", clase="HIDClass", desc="Dispositivo de entrada USB")
    c.presentes = [r"USB\ROOT_HUB30\4&1", RUEDA, RUEDA2, FLASH, HEAD,
                   r"USB\VID_046D&PID_0A38&MI_00\8&1", r"USB\VID_046D&PID_0A38&MI_03\8&2"]
    return c


class BackendCfgMgrTests(unittest.TestCase):
    def setUp(self):
        self.cfg = _arbol()
        self.b = BackendCfgMgr(cfg=self.cfg, registro=lambda did: dict(REG, servicio="x"))
        self.res = self.b.escanear()

    def test_solo_dispositivos_ni_root_hub_ni_interfaces(self):
        self.assertEqual(set(self.res), {RUEDA, RUEDA2, FLASH, HEAD})

    def test_mouse_con_su_driver_y_nombre_que_reporta_el_usb(self):
        d = self.res[RUEDA]
        self.assertEqual((d["tipo"], d["nombre"], d["fabricante"]), ("mouse", "USB Optical Mouse", "Logitech"))
        self.assertEqual(d["driver"]["nombre"], "HidUsb")
        self.assertEqual(d["driver"]["version"], "10.0.22621.1")
        self.assertEqual(d["interfaces"][0]["driver"]["nombre"], "mouhid")

    def test_dos_dispositivos_iguales_tienen_cada_uno_sus_propias_interfaces(self):
        self.assertEqual(len(self.res[RUEDA]["interfaces"]), 1)
        self.assertEqual(len(self.res[RUEDA2]["interfaces"]), 1)
        self.assertNotEqual(self.res[RUEDA]["interfaces"][0]["nombre"] + RUEDA, RUEDA2)

    def test_memoria_usb_usa_el_nombre_del_disco(self):
        d = self.res[FLASH]
        self.assertEqual((d["tipo"], d["nombre"]), ("almacenamiento", "Kingston DataTraveler 3.0 USB Device"))
        self.assertEqual(d["interfaces"][0]["clase"], "DiskDrive")

    def test_audifonos_compuestos_se_clasifican_por_sus_interfaces(self):
        d = self.res[HEAD]
        self.assertEqual((d["tipo"], d["nombre"]), ("audio", "Logitech USB Headset"))
        self.assertEqual(len(d["interfaces"]), 2)

    def test_detecta_conexion_y_desconexion_por_cambio_en_la_lista_de_ids(self):
        self.assertFalse(self.b.esperar_cambio(0.05))            # nada cambió desde el último escaneo
        self.cfg.presentes.remove(FLASH)
        self.assertTrue(self.b.esperar_cambio(1.0))              # desconexión
        self.b.escanear()
        self.cfg.presentes.append(FLASH)
        self.assertTrue(self.b.esperar_cambio(1.0))              # conexión
        self.assertIn(FLASH, self.b.escanear())

    def test_codigo_de_problema_se_informa(self):
        self.cfg.nodos[30]["problema"] = 10
        self.assertIn("código 10", self.b.escanear()[FLASH]["estado"])

    def test_driver_incompleto_se_reintenta(self):
        listo = {"v": False}
        b = BackendCfgMgr(cfg=_arbol(), registro=lambda did: dict(REG) if listo["v"] else None)
        self.assertIsNone(b.escanear()[RUEDA]["driver"]["version"])
        listo["v"] = True
        self.assertEqual(b.escanear()[RUEDA]["driver"]["version"], "10.0.22621.1")

    def test_clasificar_multi(self):
        self.assertEqual(clasificar_multi(["usbccgp", "usbaudio"], {"USB"}), "audio")
        self.assertEqual(clasificar_multi(["usbhub3"], {"USB"}), "concentrador")
        self.assertEqual(clasificar_multi([None], {"HIDClass"}), "hid")


class MonitorConCfgMgrTests(unittest.TestCase):
    def test_el_monitor_publica_lista_y_bitacora(self):
        import time
        cfg = _arbol()
        m = MonitorUSB(BackendCfgMgr(cfg=cfg, registro=lambda did: dict(REG)))
        m.iniciar()
        try:
            fin = time.time() + 3
            while time.time() < fin and not m.estado()["listo"]:
                time.sleep(0.02)
            e = m.estado()
            self.assertEqual(len(e["dispositivos"]), 4)
            self.assertTrue(all(d["preexistente"] for d in e["dispositivos"]))
            self.assertIn("método", e["diagnostico"]["bitacora"][0])
            cfg.presentes.remove(FLASH)                           # desconectar
            fin = time.time() + 4
            while time.time() < fin and len(m.estado()["dispositivos"]) == 4:
                time.sleep(0.05)
            self.assertEqual(len(m.estado()["dispositivos"]), 3)
            self.assertEqual(m.estado()["eventos"][0]["accion"], "desconectado")
        finally:
            m.detener()


# ───────────────────── envoltorio ctypes contra una DLL falsa ─────────────────────
class FakeDLL:
    """Imita cfgmgr32.dll: escribe en los buffers de ctypes igual que lo haría Windows."""

    def __init__(self):
        self.ids = ["USB\\VID_1&PID_2\\X", "USB\\ROOT_HUB30\\Y"]
        self.crece = False

    @staticmethod
    def _poner(buf, texto):
        # wchar_t mide 2 bytes en Windows (UTF-16) y 4 en Linux: la DLL falsa escribe como el sistema donde corre
        codec = "utf-16-le" if ctypes.sizeof(ctypes.c_wchar) == 2 else "utf-32-le"
        datos = texto.encode(codec)
        ctypes.memmove(buf, datos, len(datos))

    def CM_Get_Device_ID_List_SizeW(self, pn, filtro, flags):
        assert filtro == "USB" and flags == 0x101
        pn._obj.value = len("\0".join(self.ids)) + 2
        return 0

    def CM_Get_Device_ID_ListW(self, filtro, buf, n, flags):
        if self.crece:                                  # simula CR_BUFFER_SMALL una vez
            self.crece = False
            return 0x1A
        self._poner(buf, "\0".join(self.ids) + "\0\0")
        return 0

    def CM_Locate_DevNodeW(self, ph, did, flags):
        ph._obj.value = 77
        return 0 if did in self.ids else 13

    def CM_Get_Device_IDW(self, dev, buf, n, flags):
        self._poner(buf, "USB\\VID_1&PID_2\\X\0")
        return 0

    def CM_Get_Child(self, ph, dev, flags):
        if dev == 77:
            ph._obj.value = 88
            return 0
        return 0x25  # CR_NO_SUCH_DEVNODE

    def CM_Get_Sibling(self, ph, dev, flags):
        return 0x25

    def CM_Get_DevNode_Registry_PropertyW(self, dev, prop, ptipo, buf, pn, flags):
        texto = {1: "Dispositivo de entrada USB", 5: "HidUsb"}.get(prop)
        if texto is None:
            return 0x25
        bytes_ = (len(texto) + 1) * 2
        if buf is None:
            pn._obj.value = bytes_
            return 0x1A
        self._poner(buf, texto + "\0")
        return 0

    def CM_Get_DevNode_PropertyW(self, dev, pclave, ptipo, buf, pn, flags):
        texto = "USB Optical Mouse"
        bytes_ = (len(texto) + 1) * 2
        if buf is None:
            pn._obj.value = bytes_
            return 0x1A
        self._poner(buf, texto + "\0")
        return 0

    def CM_Get_DevNode_Status(self, pestado, pproblema, dev, flags):
        pproblema._obj.value = 0
        return 0


class EnvoltorioCtypesTests(unittest.TestCase):
    def setUp(self):
        self.dll = FakeDLL()
        self.cfg = _CfgMgr(dll=self.dll)

    def test_lista_de_ids(self):
        self.assertEqual(self.cfg.ids_presentes("USB"), ["USB\\VID_1&PID_2\\X", "USB\\ROOT_HUB30\\Y"])

    def test_reintenta_si_la_lista_crece_entre_llamadas(self):
        self.dll.crece = True
        self.assertEqual(len(self.cfg.ids_presentes("USB")), 2)

    def test_lista_vacia(self):
        self.dll.ids = []
        self.assertEqual(self.cfg.ids_presentes("USB"), [])

    def test_propiedades_y_arbol(self):
        n = self.cfg.nodo("USB\\VID_1&PID_2\\X")
        self.assertEqual(n, 77)
        self.assertIsNone(self.cfg.nodo("no existe"))
        self.assertEqual(self.cfg.id_de(n), "USB\\VID_1&PID_2\\X")
        self.assertEqual(self.cfg.propiedad(n, 1), "Dispositivo de entrada USB")
        self.assertEqual(self.cfg.propiedad(n, 5), "HidUsb")
        self.assertIsNone(self.cfg.propiedad(n, 8))              # propiedad inexistente
        self.assertEqual(self.cfg.propiedad_dev(n, "540b947e-8b40-45bc-a8a2-6a0b894cbda2", 4), "USB Optical Mouse")
        self.assertEqual(self.cfg.hijo(n), 88)
        self.assertIsNone(self.cfg.hermano(88))
        self.assertEqual(self.cfg.problema(n), 0)

    def test_backend_completo_sobre_la_dll_falsa(self):
        b = BackendCfgMgr(cfg=self.cfg, registro=lambda did: None)
        res = b.escanear()
        self.assertEqual(list(res), ["USB\\VID_1&PID_2\\X"])
        self.assertEqual(res["USB\\VID_1&PID_2\\X"]["nombre"], "USB Optical Mouse")


if __name__ == "__main__":
    unittest.main()
